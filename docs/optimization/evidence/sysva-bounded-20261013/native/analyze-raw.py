#!/usr/bin/env python3
"""Strict seven-triplet analysis; all forty frozen portable workloads retained."""
import argparse
import csv
import importlib.util
import json
from pathlib import Path
import re
import statistics
from fractions import Fraction

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('batch_analyzer',HERE/'analyze.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
HASHES={'baseline':m.BASELINE,
        'raw':'342b530dd0dc87baf4bbaa79c2a958fb8b5e9f643aadda4b52c2db0b29ac6f2a',
        'complex':'1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f'}
def stats(a,b):
    ma,mb=statistics.median(a),statistics.median(b)
    return dict(baseline_median_us=float(ma),candidate_median_us=float(mb),
                baseline_min_us=float(min(a)),baseline_max_us=float(max(a)),
                candidate_min_us=float(min(b)),candidate_max_us=float(max(b)),
                candidate_over_baseline=float(mb/ma),faster_pairs=sum(y<x for x,y in zip(a,b)),
                slower_pairs=sum(y>x for x,y in zip(a,b)),
                direction='faster' if max(b)<min(a) else 'slower' if min(b)>max(a) else 'overlapping ranges')
def analyze(root,contract):
    captures={}
    for p in sorted(root.glob('probe-sysva-raw-micro-*')):
        hit=re.fullmatch(r'probe-sysva-raw-micro-(\d+)-(baseline|raw|complex)-\d{8}-\d{6}',p.name)
        m.require(hit is not None,f'{p}: invalid triplet name')
        pair,side=int(hit[1]),hit[2]
        m.require((pair,side) not in captures,f'{p}: duplicate triplet capture')
        captures[pair,side]=m.capture(p,side,HASHES[side],contract)
    m.require(set(captures)=={(i,s) for i in range(7) for s in HASHES},'exactly seven complete triplets required')
    chronological=[]
    for pair in range(7):
        ordered=sorted([captures[pair,s] for s in HASHES],key=lambda c:c['started'])
        wanted=['baseline','raw','complex'] if pair%2==0 else ['complex','raw','baseline']
        m.require([c['side'] for c in ordered]==wanted,f'triplet{pair}: baseline/reference order must alternate')
        chronological.extend(ordered)
    for a,b in zip(chronological,chronological[1:]): m.require(a['finished']<=b['started'],'overlapping captures')
    reference=captures[0,'baseline'];keys=['memoryMiB','bootromSha256','backingSha256','backingLength','backingModified','eepromSha256']
    for c in chronological:
        m.require(c['frequency']==captures[0,c['side']]['frequency'],f'{c["path"]}: clock frequency changed')
        m.require(c['config']==reference['config'],f'{c["path"]}: hardware/rendering configuration changed')
        m.require(all(c['inputs'][k]==reference['inputs'][k] for k in keys),f'{c["path"]}: runtime inputs changed')
        m.require([r[-1] for r in c['rows']]==[r[-1] for r in reference['rows']],f'{c["path"]}: semantic checksum differs')
    values={}
    for key,c in captures.items():
        values[key]={n:statistics.median([Fraction(int(t)*1000000,c['frequency']*int(i))
                             for name,s,i,t,ok,h in c['rows'] if name==n]) for n in contract}
    results=[]
    for name in contract:
        per={s:[values[i,s][name] for i in range(7)] for s in HASHES}
        results.append({'workload':name,'raw_vs_baseline':stats(per['baseline'],per['raw']),
                        'raw_vs_complex':stats(per['complex'],per['raw']),
                        'baseline_vs_complex':stats(per['complex'],per['baseline'])})
    totals={s:[float(sum(Fraction(int(row[3]),captures[i,s]['frequency'])
                  for row in captures[i,s]['rows'])) for i in range(7)] for s in HASHES}
    return dict(triplets=7,workloads=40,all_correct=True,hashes=HASHES,fixture=m.FIXTURE,fixture_source=m.SOURCE,
                clock_frequencies={s:captures[0,s]['frequency'] for s in HASHES},
                runtime_inputs={k:reference['inputs'][k] for k in keys},
                analyzer_sha256=m.sha(Path(__file__)),shared_analyzer_sha256=m.sha(HERE/'analyze.py'),
                captures=[dict(path=str(c['path']),side=c['side'],started=c['started'].isoformat(),
                               finished=c['finished'].isoformat(),hashes=c['hashes']) for c in chronological],
                measured_body_totals_seconds={s:dict(values=v,median=statistics.median(v),min=min(v),max=max(v)) for s,v in totals.items()},
                results=results,limits='Seven-triplet ranges are descriptive, not significance tests or game/FPS predictions.')
def main():
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    source=HERE/'portable-main.c';m.require(m.sha(source)==m.SOURCE,'frozen portable source mismatch')
    s=source.read_text();start=s.index('static const WORK workloads[]=');s=s[start:s.index('\n};',start)]
    rows=re.findall(r'\{"([^"]+)",([A-Z_]+),(\d+),(\d+),(\d+)\}',s)
    contract={n:(int(i),1 if k=='OBJECT' and arg=='64' else 3) for n,k,size,arg,i in rows}
    m.require(len(contract)==40,'workload contract changed')
    report=analyze(a.results,contract);a.output.mkdir(parents=True,exist_ok=True)
    (a.output/'report-raw.json').write_text(json.dumps(report,indent=2)+'\n')
    for comparison in ['raw_vs_baseline','raw_vs_complex','baseline_vs_complex']:
        data=[{'workload':r['workload'],**r[comparison]} for r in report['results']]
        with (a.output/(comparison+'.csv')).open('w') as f:
            writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(data)
    for r in report['results']:
        if r['workload'].startswith('sysva-'): print(r)
    print('Validated 21 matching 64-MiB native captures, seven alternating triplets, all forty workloads and checksums.')
if __name__=='__main__':main()
