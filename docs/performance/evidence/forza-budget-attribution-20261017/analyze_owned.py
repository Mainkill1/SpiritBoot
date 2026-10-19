# SPDX-License-Identifier: MIT
# Independently authored scalar observation analysis; no firmware implementation.
import argparse
import hashlib
import json
import re
import statistics
from collections import Counter
from pathlib import Path
import analyze

PHASES=9
HEX={'thread','handle','status'}
BASE=set('host_ns virtual_ns thread handle bytes total_ns status info reentry bad'.split())
FIELDS=BASE|{f'p{i}_{suffix}'for i in range(PHASES)for suffix in ('ns','count','open')}


def verify_observer(source,sites):
    source=re.sub(r'\s+','',source)
    for condition in ('spirit_read32(env,esp+16)!=0x001103e0',
                      'spirit_read32(env,esp)!=0x0026741a','r->esp=esp+36'):
        if condition not in source:raise ValueError('Unverified native callback/return ABI filter')
    if len(sites)!=PHASES:raise ValueError('Wrong phase count')
    for i,s in enumerate(sites):
        if f'case0x{s["entry"]:08x}:phase={i};entering=true;break;'not in source:
            raise ValueError('Entry site mismatch')
        for ret in s['returns']:
            if f'case0x{ret:08x}:phase={i};break;'not in source:raise ValueError('Return site mismatch')


def parse_log(text):
    rows=[];meta=None
    for line in text.splitlines():
        if not line.strip():continue
        parts=line.split();d={}
        expected={'rows','overflow','lost'}if parts[0]=='owned_meta'else FIELDS
        for token in parts[1:]:
            if token.count('=')!=1:raise ValueError('Malformed field')
            k,v=token.split('=')
            if k not in expected or k in d:raise ValueError('Unknown or duplicate field')
            if not re.fullmatch(r'[0-9a-fA-F]{8}'if k in HEX else r'\d+',v):raise ValueError('Malformed scalar')
            d[k]=int(v,16 if k in HEX else 10)
        if set(d)!=expected:raise ValueError('Missing fields')
        if parts[0]=='owned_meta'and meta is None and not rows:meta=d
        elif parts[0]=='owned_read'and meta is not None:rows.append(d)
        else:raise ValueError('Unexpected record')
    if meta is None or meta['rows']!=len(rows):raise ValueError('Missing header/truncated capture')
    return meta,rows


def validation(meta,rows,start):
    return {'header_matches':True,'overflow':meta['overflow'],'lost_global':meta['lost'],
            'reentry_selected':sum(r['reentry']for r in rows),'bad_selected':sum(r['bad']for r in rows),
            'open_phase_depths':sum(r[f'p{i}_open']for r in rows for i in range(PHASES)),
            'phase_exceeds_total':sum(r[f'p{i}_ns']>r['total_ns']for r in rows for i in range(PHASES)),
            'duration_without_entry':sum(r[f'p{i}_count']==0 and r[f'p{i}_ns']!=0 for r in rows for i in range(PHASES)),
            'zero_total_duration':sum(r['total_ns']==0 for r in rows),
            'potential_start_boundary_overlap':sum(r['host_ns']-r['total_ns']<start for r in rows)}


def distribution(v):
    result=analyze.distribution(v)
    if result['n']:result['mean']=result['sum']/result['n']
    return result


def summarize(rows,sites):
    total=sum(r['total_ns']for r in rows);phases={}
    for i,site in enumerate(sites):
        values=[r[f'p{i}_ns']for r in rows];present=[r for r in rows if r[f'p{i}_count']]
        phases[site['name']]={'index':i,'all_reads_ns':distribution(values),
            'present_read_ns':distribution([r[f'p{i}_ns']for r in present]),
            'entry_count':sum(r[f'p{i}_count']for r in rows),'reads_with_phase':len(present),
            'weighted_fraction_of_total_inclusive':sum(values)/total,
            'median_per_read_fraction_inclusive':statistics.median(r[f'p{i}_ns']/r['total_ns']for r in rows)}
    bounds=[]
    for r in rows:
        values=[r[f'p{i}_ns']for i in range(PHASES)]
        bounds.append((max(0,r['total_ns']-sum(values)),r['total_ns']-max(values)))
    partitions={}
    for name,pop in [('dpc_absent',[r for r in rows if not r['p1_count']]),
                     ('dpc_present',[r for r in rows if r['p1_count']])]:
        partitions[name]={'reads':len(pop),'total_api_ns':distribution([r['total_ns']for r in pop]),
            'adapter_ns':distribution([r['p3_ns']for r in pop]),
            'dpc_ns':distribution([r['p1_ns']for r in pop]),
            'run_pump_counts':dict(Counter(r['p7_count']for r in pop))}
    return {'total_api_ns':distribution([r['total_ns']for r in rows]),'phases':phases,'partitions':partitions,
            'unobserved_time_bounds_ns':{'aggregate_lower':sum(v[0]for v in bounds),
                'aggregate_upper':sum(v[1]for v in bounds),
                'meaning':'Bounds on time outside the union of observed scopes, not CPU execution. Lower subtracts all inclusive phases and clips at zero; upper subtracts the largest phase per read. Unknown overlap prevents a unique residual.'}}


def run(log,receipts,observer,sites):
    paths=[Path(p)for p in (log,receipts,observer,sites)]
    log,receipts,observer,site_path=paths;sites=json.loads(site_path.read_text())
    verify_observer(observer.read_text(),sites)
    meta,rows=parse_log(log.read_text());start,end=analyze.replay_bounds(receipts.read_text())
    selected=analyze.select(rows,start,end)
    if not selected:raise ValueError('No replay reads; an empty probe is not evidence of firmware behavior')
    checks=validation(meta,selected,start)
    if any(checks[k]for k in checks if k not in ('header_matches','potential_start_boundary_overlap')):
        raise ValueError('Capture is not valid for phase attribution: '+str(checks))
    result={'scope':'Completed observed callback-filtered native reads with host-end inside the saved-scene replay window. Warmup excluded.',
            'host_start_ns':start,'host_end_ns':end,'window_seconds':(end-start)/1e9,
            'meta':meta,'selected_rows':len(selected),'excluded_rows':len(rows)-len(selected),'validation':checks,
            'population':{k:dict(Counter(f'{r[k]:08x}'if k in HEX else r[k]for r in selected))for k in ['thread','handle','bytes','status','info']},
            'interpretation':['status is IOSB.Status sampled at native return, not EAX/NtReadFile return status.',
                'Same-phase recursion is measured once at outermost depth. Distinct phases can nest or overlap; their fractions are not additive.',
                'Scope time includes interruptions, scheduling and emulator/host effects; it is not CPU-only or blocked-I/O time.',
                'Active calls that never reach the observed return are not emitted. This is a completed-call population.',
                'Host start is not captured; possible boundary overlap is estimated from virtual duration.'],
            'sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in paths}}
    result.update(summarize(selected,sites));return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for arg in ('log','receipts','observer','sites'):parser.add_argument(arg)
    parser.add_argument('--output');a=parser.parse_args()
    result=json.dumps(run(a.log,a.receipts,a.observer,a.sites),indent=2,sort_keys=True)+'\n'
    if a.output:Path(a.output).write_text(result)
    else:print(result,end='')


if __name__=='__main__':main()
