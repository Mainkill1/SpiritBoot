# SPDX-License-Identifier: MIT
"""Control pre-bind comparisons by size, mapping, completion timing and gap."""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import analyze_identity as identity
import analyze_timeline as timeline


def gap_bin(gap):
    if gap is None:return 'first_selected_call'
    if gap < 0:raise ValueError('Overlapping selected native calls')
    if gap < 100:return 'under_100us'
    if gap < 1000:return '100us_to_1ms'
    if gap < 10000:return '1ms_to_10ms'
    return 'at_least_10ms'


def enrich(rows, events):
    begins={e['api']:e for e in events if e['kind']==1}
    returns={e['api']:e for e in events if e['kind']==2}
    ready=defaultdict(list)
    for e in events:
        if e['kind']==12:ready[e['api']].append(e)
    output=[]
    for row in rows:
        api=row['api'];begin=begins[api];ret=returns[api]
        if len(row['lifecycle'])!=1:raise ValueError('This comparison requires one lower dispatch per read')
        match=[e for e in ready[api] if e['iosb']==begin['iosb']]
        if len(match)!=1:raise ValueError('This comparison requires one matching mapping-ready event')
        mapping=match[0];binding=row['lifecycle'][0]['bind']
        if not begin['seq']<mapping['seq']<binding['seq']<ret['seq']:
            raise ValueError('Mapping-ready is outside expected pre-bind interval')
        prev=row['previous_selected_read_api']
        gap=(begin['virtual_ns']-returns[prev]['virtual_ns'])/1000 if prev is not None else None
        to_ready=(mapping['virtual_ns']-begin['virtual_ns'])/1000
        prebind=binding['from_entry_us']
        if not 0<=to_ready<=prebind:raise ValueError('Invalid pre-bind time boundaries')
        previous_seq=row['previous_last_child_completion_seq']
        crossing='not_during_prebind'
        if previous_seq is not None and begin['seq']<previous_seq<binding['seq']:
            crossing='entry_to_mapping_ready' if previous_seq<mapping['seq'] else 'mapping_ready_to_bind'
        output.append({'api':api,'bytes':row['bytes'],'extent_hit':row['extent_ready_flags']==[True],
          'partition':row['queue_start_partition'],'previous_completion':row['previous_child_completion'],
          'previous_completion_prebind_segment':crossing,'intercall_gap_us':gap,'gap_bin':gap_bin(gap),
          'entry_to_bind_us':prebind,'entry_to_mapping_ready_us':to_ready,
          'mapping_ready_to_bind_us':prebind-to_ready,'api_us':row['api_us']})
    return output


def grouped(rows, dimensions):
    groups=defaultdict(list)
    for row in rows:groups[tuple(row[k]for k in dimensions)].append(row)
    result=[]
    for key, subset in sorted(groups.items()):
        result.append({**dict(zip(dimensions,key)),'calls':len(subset),
          **{name:timeline.stats([r[name]for r in subset if r[name]is not None]) for name in
             ['entry_to_bind_us','entry_to_mapping_ready_us','mapping_ready_to_bind_us','intercall_gap_us','api_us']}})
    return result


def analyze(events,start,end):
    trace=timeline.timeline(events,start,end)
    selected=[e for e in events if start<=e['host_ns']<=end]
    rows=enrich(trace['reads'],selected)
    return {'reads':rows,'selected_reads':len(rows),'tables':{
      'size_extent_partition':grouped(rows,['bytes','extent_hit','partition']),
      'size_extent_previous_partition':grouped(rows,['bytes','extent_hit','previous_completion','partition']),
      'size_extent_gap_partition':grouped(rows,['bytes','extent_hit','gap_bin','partition']),
      'size_extent_gap_previous_partition':grouped(rows,['bytes','extent_hit','gap_bin','previous_completion','previous_completion_prebind_segment','partition'])},
      'limitations':[
       'Gap means current entry minus previous selected same-thread native return; it is not an exact pump or frame marker.',
       'These are observational cohorts, not randomized or paired interventions. Missing overlap prevents causal comparison.',
       'Inclusive instrumented intervals include observer, scheduling, interrupts and work not separately observed; they are not exclusive CPU times.',
       'Prior completion means matching child-completion entry, not device-tag release, actual device completion or callback completion.',
       'No mapper call is assumed from timing alone: extent-hit classification uses the mapping-ready scalar and the validated direct dispatch.',
       'Medians of interval components are not additive.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('receipts',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();_,events=identity.parse(args.log.read_text());start,end=identity.bounds(args.receipts.read_text())
    result=analyze(events,start,end);result['sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in [args.log,args.receipts]}
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')

if __name__=='__main__':main()
