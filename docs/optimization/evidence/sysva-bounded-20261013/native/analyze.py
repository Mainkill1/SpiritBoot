#!/usr/bin/env python3
"""Validate all frozen native microbenchmark receipts and retain every workload."""
import argparse
import csv
import datetime as dt
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import re
import statistics
import tomllib

FIXTURE = '65da3568167cd7e25eec3da4baaffbe65c7fae931078659885297e657412a705'
SOURCE = 'c5a6f925eba08cba3ecf067aa42fbad8aab137721ed5e35e350a3cc82dd40499'
EXE = '14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d'
BASELINE = 'be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827'
PREFIX = 'probe-sysva-micro-'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v, why):
    if not v: raise ValueError(why)
def document(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def parse_log(log, contract):
    lines=log.splitlines()
    require(lines.count('== kernel-performance-portable begin ==')==1 and
            lines[-1]=='== kernel-performance-portable end PASS ==', 'missing unique portable terminal')
    require(not any('not ok' in x or '# SKIP' in x or '# TODO' in x for x in lines), 'nonpassing workload')
    require(lines.count('# PERF-SUMMARY workloads=40 failures=0')==1, 'wrong workload summary')
    tap=re.findall(r'^ok (\d+) - (\S+)$',log,re.M)
    require(tap==[(str(i+1),n) for i,n in enumerate(['public-known-answers',*contract])], 'TAP order/count mismatch')
    meta=re.findall(r'^# PERF-META version=1 clock=KeQueryPerformanceCounter frequency=(\d+) samples=3$',log,re.M)
    require(len(meta)==1 and int(meta[0])>0, 'invalid clock metadata')
    rows=re.findall(r'^# PERF workload=(\S+) sample=(\d+) iterations=(\d+) ticks=(\d+) correct=(\d+) checksum=([0-9a-f]{8})$',log,re.M)
    want=[(n,str(s),str(iterations)) for n,(iterations,count) in contract.items() for s in range(count)]
    require([(n,s,i) for n,s,i,t,c,h in rows]==want, 'missing/duplicate/reordered sample')
    require(all(c=='1' for n,s,i,t,c,h in rows), 'incorrect sample')
    return int(meta[0]), rows
def capture(p, side, bios, contract):
    launch=document(p/'launch.json'); inputs=document(p/'inputs.json'); result=document(p/'result.json')
    require(launch['biosSha256'].lower()==bios and launch['exeSha256'].lower()==EXE and
            launch['probeSha256'].lower()==FIXTURE and launch['session']>0, f'{p}: launch identity')
    require(inputs['memoryMiB']==64 and result['exited'] is True and result['exitCode']==0, f'{p}: profile/exit')
    require(sha(p/'launch-xemu.toml')==inputs['configSha256'].lower(), f'{p}: frozen config hash')
    config=tomllib.loads((p/'launch-xemu.toml').read_text(encoding='utf-8-sig'))
    require(config['display']['renderer']=='VULKAN' and config['display']['window']['vsync'] is False,
            f'{p}: rendering profile')
    for key in ['flashrom_path','eeprom_path','hdd_path','dvd_path']: config['sys']['files'][key]='<per-run-file>'
    frequency,rows=parse_log((p/'serial.log').read_text(),contract)
    finished=dt.datetime.fromisoformat(result['utc'].replace('Z','+00:00'))
    started=finished-dt.timedelta(seconds=result['elapsedSeconds'])
    return dict(path=p,side=side,frequency=frequency,rows=rows,config=config,inputs=inputs,
                started=started,finished=finished,hashes={n:sha(p/n) for n in ['serial.log','launch.json','inputs.json','result.json','launch-xemu.toml']})
def analyze(root, candidate, contract):
    captures={}
    for p in sorted(root.glob(PREFIX+'*')):
        match=re.fullmatch(PREFIX+r'(\d+)-(baseline|sysva)-\d{8}-\d{6}',p.name)
        require(match is not None, f'{p}: malformed pair name')
        pair,side=int(match[1]),match[2]
        require((pair,side) not in captures, f'{p}: duplicate capture')
        captures[pair,side]=capture(p,side,BASELINE if side=='baseline' else candidate,contract)
    require(set(captures)=={(p,s) for p in range(7) for s in ['baseline','sysva']},'exactly seven complete pairs required')
    reference=captures[0,'baseline']; chronological=[]
    for pair in range(7):
        a,b=captures[pair,'baseline'],captures[pair,'sysva']
        expected=['sysva','baseline'] if pair%2 else ['baseline','sysva']
        ordered=sorted([a,b],key=lambda c:c['started'])
        require([c['side'] for c in ordered]==expected, f'pair {pair}: BIOS order must alternate')
        chronological.extend(ordered)
    for before,after in zip(chronological,chronological[1:]):
        require(before['finished']<=after['started'],'overlapping native captures')
    invariant=['memoryMiB','bootromSha256','backingSha256','backingLength','backingModified','eepromSha256']
    for c in chronological:
        require(c['frequency']==reference['frequency'] and c['config']==reference['config'],f'{c["path"]}: clock/config mismatch')
        require(all(c['inputs'][k]==reference['inputs'][k] for k in invariant),f'{c["path"]}: runtime inputs mismatch')
        require([r[-1] for r in c['rows']]==[r[-1] for r in reference['rows']],f'{c["path"]}: semantic checksum mismatch')
    values={}
    for key,c in captures.items():
        workloads={n:[] for n in contract}
        for n,s,i,t,ok,h in c['rows']: workloads[n].append(Fraction(int(t)*1000000,c['frequency']*int(i)))
        values[key]={n:statistics.median(v) for n,v in workloads.items()}
    results=[]
    for n in contract:
        a=[values[p,'baseline'][n] for p in range(7)];b=[values[p,'sysva'][n] for p in range(7)]
        ma,mb=statistics.median(a),statistics.median(b)
        results.append(dict(workload=n,baseline_median_us=float(ma),candidate_median_us=float(mb),
                            baseline_min_us=float(min(a)),baseline_max_us=float(max(a)),
                            candidate_min_us=float(min(b)),candidate_max_us=float(max(b)),
                            candidate_over_baseline=float(mb/ma),faster_pairs=sum(y<x for x,y in zip(a,b)),
                            slower_pairs=sum(y>x for x,y in zip(a,b)),
                            direction='faster' if max(b)<min(a) else 'slower' if min(b)>max(a) else 'overlapping ranges'))
    return dict(pair_count=7,workload_count=40,all_correct=True,frequency=reference['frequency'],
                baseline=BASELINE,candidate=candidate,fixture=FIXTURE,fixture_source=SOURCE,
                analyzer_sha256=sha(Path(__file__)),runtime_inputs={k:reference['inputs'][k] for k in invariant},
                captures=[dict(path=str(c['path']),side=c['side'],started=c['started'].isoformat(),finished=c['finished'].isoformat(),hashes=c['hashes']) for c in chronological],
                workloads=results,limits='Descriptive seven-pair ranges; not a significance test or game/FPS prediction.')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('results',type=Path);parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--candidate',default='1cdd25e24514076b77686689bf68e1438006da381b09cf47a742ed7f5eb645ea')
    args=parser.parse_args();require(sha(args.source)==SOURCE,'portable source identity mismatch')
    text=args.source.read_text(); table=text[text.index('static const WORK workloads[]='):text.index('\n};',text.index('static const WORK workloads[]='))]
    rows=re.findall(r'\{"([^"]+)",([A-Z_]+),(\d+),(\d+),(\d+)\}',table)
    contract={name:(int(iterations),1 if kind=='OBJECT' and arg=='64' else 3) for name,kind,size,arg,iterations in rows}
    require(len(contract)==40,'portable source workload count changed')
    result=analyze(args.results,args.candidate,contract);args.output.mkdir(parents=True,exist_ok=True)
    (args.output/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    with (args.output/'workloads.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(result['workloads'][0]));writer.writeheader();writer.writerows(result['workloads'])
    for row in result['workloads']:
        if row['workload'].startswith('sysva-'): print(row)
    print('Validated 14 immutable 64-MiB native captures, seven alternating pairs, all 40 workloads and all checksums.')
if __name__=='__main__':main()
