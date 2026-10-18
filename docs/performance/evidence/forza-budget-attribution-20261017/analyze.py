# SPDX-License-Identifier: MIT
# Independently authored value-only trace analysis. No title implementation.
"""Validate buffered observations and summarize only the saved-scene replay.

All time scopes remain inclusive: callback and delay durations overlap.
The script deliberately does not manufacture an exclusive CPU-time residual.
"""
import argparse
import calendar
import datetime
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path

HEX_FIELDS = {'thread', 'queue', 'deadline_pc'}
FIELDS = set('host_ns virtual_ns thread queue budget limit outstanding_start outstanding_end reads bytes callbacks checks deadline_pc empty first_elapsed_ticks elapsed_ticks total_ns initial_ns read_ns wait_ns callback_ns read_open wait_open callback_open'.split())
TIMES = ('total_ns','initial_ns','read_ns','wait_ns','callback_ns')


def utc_ns(value):
    match = re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\.(\d{1,9})(?:\+00:00|Z)',value)
    if not match:
        raise ValueError('Expected a UTC timestamp with fractional seconds')
    dt=datetime.datetime.strptime(match[1],'%Y-%m-%dT%H:%M:%S')
    return calendar.timegm(dt.timetuple())*10**9 + int(match[2].ljust(9,'0'))


def replay_bounds(text):
    records=[json.loads(line)for line in text.splitlines() if line.strip()]
    if not all(isinstance(r,dict)for r in records):
        raise ValueError('Expected JSONL receipt objects')
    def one(suffix,field):
        found=[r for r in records if str(r.get('Id','')).endswith(suffix)]
        if len(found)!=1 or found[0].get('Status')!='completed':
            raise ValueError('Need exactly one completed '+suffix+' receipt')
        return utc_ns(found[0][field])
    start,end=one('-resume','EndedUtc'),one('-pause','StartedUtc')
    if start>=end:raise ValueError('Replay bounds are reversed or empty')
    return start,end


def decode_fields(parts,expected):
    result={}
    for item in parts:
        if item.count('=')!=1:raise ValueError('Malformed field')
        key,value=item.split('=')
        if key in result or key not in expected:raise ValueError('Duplicate or unknown field: '+key)
        pattern=r'[0-9a-fA-F]{8}' if key in HEX_FIELDS else r'\d+'
        if not re.fullmatch(pattern,value):raise ValueError('Malformed value: '+key)
        result[key]=int(value,16 if key in HEX_FIELDS else 10)
    if set(result)!=expected:raise ValueError('Missing fields: '+str(expected-set(result)))
    return result


def validate_rows(rows,start):
    checks=dict(open_spans=0,initial_exceeds_total=0,wait_exceeds_initial=0,
                callback_exceeds_wait=0,read_plus_wait_exceeds_total=0,
                empty_and_deadline=0,deadline_below_budget=0,
                potential_start_boundary_overlap=0)
    for r in rows:
        checks['open_spans']+=any(r[k]for k in ('read_open','wait_open','callback_open'))
        checks['initial_exceeds_total']+=r['initial_ns']>r['total_ns']
        checks['wait_exceeds_initial']+=r['wait_ns']>r['initial_ns']
        checks['callback_exceeds_wait']+=r['callback_ns']>r['wait_ns']
        checks['read_plus_wait_exceeds_total']+=r['read_ns']+r['wait_ns']>r['total_ns']
        checks['empty_and_deadline']+=bool(r['empty']and r['deadline_pc'])
        checks['deadline_below_budget']+=bool(r['deadline_pc'])and r['elapsed_ticks']<r['budget']
        checks['potential_start_boundary_overlap']+=r['host_ns']-r['total_ns']<start
    return checks


def parse_log(text):
    rows=[];meta=None
    for line_number,line in enumerate(text.splitlines(),1):
        if not line.strip():continue
        parts=line.split()
        if parts[0]=='forza_budget_meta' and meta is None and not rows:
            meta=decode_fields(parts[1:],{'rows','overflow','reentry'})
        elif parts[0]=='forza_budget' and meta is not None:
            r=decode_fields(parts[1:],FIELDS)
            if not r['budget'] or not r['limit']:raise ValueError('Zero budget/limit')
            if r['empty']not in (0,1):raise ValueError('Invalid empty flag')
            if r['deadline_pc']not in (0,0x110d9f,0x110dce):raise ValueError('Unknown deadline observation')
            if r['first_elapsed_ticks']>r['elapsed_ticks']:raise ValueError('Elapsed ticks regress')
            if r['reads']==0 and r['read_ns']!=0:raise ValueError('Read duration without reads')
            rows.append(r)
        else:raise ValueError(f'Unexpected record at line {line_number}')
    if meta is None or meta['rows']!=len(rows):raise ValueError('Missing header or truncated row count')
    if meta['overflow']or meta['reentry']:raise ValueError('Capture overflow/reentry prevents exact accounting')
    validation=validate_rows(rows,0)
    # Containment checks are validation diagnostics, not proof of every nested
    # API intersection. Only unequivocally inconsistent/unfinished spans fail.
    for key in ('open_spans','initial_exceeds_total','empty_and_deadline','deadline_below_budget'):
        if validation[key]:raise ValueError('Invalid capture: '+key)
    return meta,rows


def select(rows,start,end):
    return [r for r in rows if start<=r['host_ns']<=end]


def reason(r):
    if r['empty']:return 'empty_work'
    if r['deadline_pc']and r['elapsed_ticks']>=r['budget']:
        return 'initial_budget' if r['first_elapsed_ticks']>=r['budget'] else 'loop_budget'
    if r['outstanding_end']>=r['limit']:return 'outstanding_limit'
    return 'unclassified'


def distribution(values):
    values=sorted(values)
    if not values:return {'n':0}
    return dict(n=len(values),sum=sum(values),median=statistics.median(values),
                p95=values[int((len(values)-1)*.95)],max=max(values))


def summarize(rows):
    result={'pumps':len(rows),'reasons':dict(Counter(reason(r)for r in rows)),
            'reads':sum(r['reads']for r in rows),'bytes':sum(r['bytes']for r in rows),
            'callbacks':sum(r['callbacks']for r in rows),
            'reads_per_pump':dict(Counter(r['reads']for r in rows))}
    for key in (*TIMES,'first_elapsed_ticks','elapsed_ticks'):
        result[key]=distribution([r[key]for r in rows])
    result['native_read_ns_per_call_weighted']=sum(r['read_ns']for r in rows)/result['reads'] if result['reads']else None
    result['median_per_pump_mean_read_ns']=statistics.median(r['read_ns']/r['reads']for r in rows if r['reads']) if result['reads']else None
    for key in ('outstanding_start','outstanding_end'):
        result[key]=dict(Counter(r[key]for r in rows))
    return result


def analyze(log_path,receipt_path):
    log_path,receipt_path=Path(log_path),Path(receipt_path)
    meta,rows=parse_log(log_path.read_text())
    start,end=replay_bounds(receipt_path.read_text())
    selected=select(rows,start,end)
    sizes=sorted(set(r['bytes']for r in selected if r['reads']==1))
    return {'scope':'Saved-scene replay; inclusive host-end bounds, not full-run warmup.',
            'host_start_ns':start,'host_end_ns':end,'window_seconds':(end-start)/1e9,
            'meta':meta,'all_file_rows':len(rows),'excluded_rows':len(rows)-len(selected),
            'validation':validate_rows(selected,start),
            'population':{k:dict(Counter(f'{r[k]:08x}'if k in HEX_FIELDS else r[k]for r in selected))for k in ('thread','queue','budget','limit')},
            'all_replay':summarize(selected),'productive':summarize([r for r in selected if r['reads']]),
            'by_reason':{why:summarize([r for r in selected if reason(r)==why])for why in sorted(set(reason(r)for r in selected))},
            'single_read_pump_sizes':{size:distribution([r['read_ns']for r in selected if r['reads']==1 and r['bytes']==size])for size in sizes},
            'accounting':'Inclusive scopes. initial_ns contains setup and the initial wrapper; callback_ns overlaps wait_ns. No exclusive CPU residual is inferred. Final alertable wait is outside the measurement. Host start was not captured: potential boundary overlap uses virtual duration as an estimate.',
            'read_scope':'All native reads returning at title callsite 0x26741a inside the pump; callback/file identity is not captured.',
            'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in (log_path,receipt_path)}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log');parser.add_argument('receipts');parser.add_argument('--output')
    args=parser.parse_args()
    result=json.dumps(analyze(args.log,args.receipts),indent=2,sort_keys=True)+'\n'
    if args.output:Path(args.output).write_text(result)
    else:print(result,end='')


if __name__=='__main__':main()
