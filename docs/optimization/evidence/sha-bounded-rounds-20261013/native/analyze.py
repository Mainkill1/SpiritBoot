"""Reanalyze the frozen native SHA receipts; no Windows connection is used."""
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import statistics as st
import zipfile

ROOT = Path(__file__).resolve().parent
CONTRACT = json.loads((ROOT/'contracts.json').read_text())
BIOS = dict(baseline='62edb78f3ac8dd5739c2b6b9d1a838a4447f3c7662db4e4166e3c795081db027', sha='33fc537ff03946fe5a48bd27e40a4e51928a9e23244d9d8f6609c9aa9c244f71', complex='1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f')
EXE = '14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d'
ISO = dict(micro='65da3568167cd7e25eec3da4baaffbe65c7fae931078659885297e657412a705', api='099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33')
EEPROM = '67412e911568a47719ef0b3e0c6396e70996c2f7c29a4e48441bf9cc3d585642'

def need(ok, message):
    if not ok: raise ValueError(message)

def one(pattern, log):
    found = re.findall(pattern, log, re.M)
    need(len(found)==1, 'missing/duplicate '+pattern)
    return found[0]

def parse_micro(log):
    need(log.splitlines()[0]=='== kernel-performance-portable begin ==' and log.splitlines()[-1]=='== kernel-performance-portable end PASS ==','micro terminal')
    need(one(r'^1\.\.(\d+)$',log)=='41','micro TAP plan')
    need(one(r'^TAP version (\d+)$',log)=='14','micro TAP version')
    rows=re.findall(r'^(not ok|ok) (\d+) - (.+)$',log,re.M)
    names=list(dict.fromkeys(k.split('/')[0] for k in CONTRACT['EXPECTED_MICRO']))
    need(rows==[('ok',str(i+1),n) for i,n in enumerate(['public-known-answers']+names)],'micro TAP sequence')
    need(one(r'^# PERF-SUMMARY workloads=(\d+) failures=(\d+)$',log)==('40','0'),'micro summary')
    frequency,samples=one(r'^# PERF-META version=1 clock=KeQueryPerformanceCounter frequency=(\d+) samples=(\d+)$',log)
    need(int(frequency)>0 and samples=='3','micro clock')
    entries=re.findall(r'^# PERF workload=(\S+) sample=(\d+) iterations=(\d+) ticks=(\d+) correct=(\d+) checksum=(\S+)$',log,re.M)
    need(len(entries)==118,'micro sample count')
    need(sum(l.startswith('# PERF workload=') for l in log.splitlines())==118,'malformed sample')
    got={}; values={}
    for name,sample,it,ticks,correct,checksum in entries:
        k=name+'/'+sample
        need(k not in got and correct=='1' and int(it)>0 and 0<int(ticks)<2**64,'sample value')
        got[k]=[int(it),checksum]
        values.setdefault(name,[]).append(int(ticks)*1e6/int(frequency)/int(it))
    need(list(got)==list(CONTRACT['EXPECTED_MICRO']) and got==CONTRACT['EXPECTED_MICRO'],'micro order/iterations/checksums')
    return {name:st.median(v) for name,v in values.items()}

def parse_api(log):
    need(log.splitlines()[0]=='== api-regression begin ==' and log.splitlines()[-1]=='== api-regression end PASS ==','API terminal')
    need(one(r'^1\.\.(\d+)$',log)=='639','API plan')
    rows=re.findall(r'^(not ok|ok) (\d+) - (.+)$',log,re.M)
    need(len(rows)==639 and [int(r[1]) for r in rows]==list(range(1,640)),'API numbering')
    todos=set();skips=set();passing=set()
    for status,_,desc in rows:
        name=desc.split(' # ')[0]
        if ' # TODO ' in desc: need(status=='not ok','unexpected TODO pass'); todos.add(name)
        elif ' # SKIP ' in desc: need(status=='ok','failed SKIP'); skips.add(name)
        else: need(status=='ok','unexpected API failure'); passing.add(name)
    need(todos==set(CONTRACT['TODOS']) and skips==set(CONTRACT['SKIPS']),'API TODO/SKIP set')
    entries=re.findall(r'^# LEAF name=(\S+) ticks=(\d+) ok=(\d+) todo=(\d+)$',log,re.M)
    need(len(entries)==634 and len({e[0] for e in entries})==634,'API leaf count')
    need(set(e[0] for e in entries)==set(CONTRACT['EXPECTED_LEAVES']),'API leaf set')
    for name,ticks,ok,todo in entries: need((ok,todo)==(('0','1') if name in todos else ('1','0')),'API leaf semantics')
    need(passing==set(CONTRACT['EXPECTED_LEAVES'])-todos,'API passing names')
    need(one(r'^# tests=(\d+) passed=(\d+) failed=(\d+) skipped=(\d+)$',log)==('639','634','0','5'),'API summary')
    return dict(plan=639,ordinary_passes=630,todo_failures=sorted(todos),skips=sorted(skips),unexpected_failures=0)

def main():
    values={}; records=[]; contexts=[]; timeline=[]
    with zipfile.ZipFile(ROOT/'receipts.zip') as archive:
        dirs=sorted({Path(n).parts[0] for n in archive.namelist()})
        need(len(dirs)==22,'need 21 micro runs and one API')
        api=None
        for d in dirs:
            match=re.fullmatch(r'probe-sha-micro-([0-6])-(baseline|sha|complex)-\d{8}-\d{6}',d)
            if match: pair,arm=int(match[1]),match[2];kind='micro'
            else: need(bool(re.fullmatch(r'probe-sha-api-\d{8}-\d{6}',d)),'unexpected run');pair=None;arm='sha';kind='api'
            raw={n:archive.read(d+'/'+n) for n in ['inputs.json','launch.json','result.json','serial.log','stdout.log','stderr.log']}
            inp,launch,result=[json.loads(raw[n].decode('utf-8-sig')) for n in ['inputs.json','launch.json','result.json']]
            need(result['exited'] is True and result['exitCode']==0,'process completion')
            need(type(result['elapsedSeconds']) in (int,float) and 0<result['elapsedSeconds']<180,'elapsed')
            need(launch['session']>0 and launch['pid']>0,'interactive process')
            for field,want in [('biosSha256',BIOS[arm]),('probeSha256',ISO[kind]),('exeSha256',EXE)]:need(launch[field].lower()==want,field)
            need(inp['memoryMiB']==64 and inp['eepromSha256'].lower()==EEPROM,'memory/EEPROM')
            need(bool(re.fullmatch('[0-9a-fA-F]{64}',inp['configSha256'])),'config hash')
            contexts.append((inp['backing'],inp['backingLength'],inp['backingModified']))
            end=datetime.fromisoformat(result['utc'].replace('Z','+00:00'));start=end-timedelta(seconds=result['elapsedSeconds']);timeline.append((start,end,d))
            log=raw['serial.log'].decode('utf-8-sig')
            if kind=='micro':
                need((pair,arm) not in values,'duplicate arm');values[pair,arm]=parse_micro(log)
            else: need(api is None,'duplicate API');api=parse_api(log)
            records.append(dict(path=d,pair=pair,arm=arm,kind=kind,started_utc=start.isoformat(),ended_utc=end.isoformat(),hashes={n:hashlib.sha256(b).hexdigest() for n,b in raw.items()},launch=launch,inputs=inp,result=result))
    need(len(set(contexts))==1,'HDD backing metadata changed')
    timeline.sort()
    need(all(a[1]<=b[0] for a,b in zip(timeline,timeline[1:])),'runs overlap')
    need(set(values)=={(p,a) for p in range(7) for a in BIOS},'incomplete triplets')
    for pair in range(7):
        order=[next(r['arm'] for r in records if r['path']==d) for _,_,d in timeline if f'micro-{pair}-' in d]
        need(order==(['baseline','sha','complex'] if pair%2==0 else ['complex','sha','baseline']),'triplet order')
    rows=[]
    for name in values[0,'sha']:
        arms={arm:[values[p,arm][name] for p in range(7)] for arm in BIOS}
        med={arm:st.median(v) for arm,v in arms.items()}
        change=[100*(s/b-1) for s,b in zip(arms['sha'],arms['baseline'])]
        rows.append(dict(workload=name,baseline_us=med['baseline'],sha_us=med['sha'],complex_us=med['complex'],median_change_percent=100*(med['sha']/med['baseline']-1),candidate_over_complex=med['sha']/med['complex'],faster_pairs=sum(x<0 for x in change),slower_pairs=sum(x>0 for x in change),paired_change_min_percent=min(change),paired_change_max_percent=max(change),baseline_boot_us=arms['baseline'],sha_boot_us=arms['sha'],complex_boot_us=arms['complex']))
    report=dict(validated=True,micro_runs=21,micro_samples=2478,api=api,method='Per-boot median of three samples (one for object-cold-64), normalized by guest frequency and iteration count; median of seven boots. Pair ranges are descriptive, not confidence intervals. No empty-loop subtraction.',limitations='Receipts attest executable/Complex hashes; their remote bytes are not locally rehashed. Full HDD backing content/config bytes are not exported: invariant backing path/length/mtime, memory and EEPROM hash are verified. Runner creates a fresh overlay per run.',identities=dict(bios=BIOS,exe=EXE,fixtures=ISO),workloads=rows,receipts=records)
    (ROOT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (ROOT/'workloads.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    print(json.dumps(dict(validated=True,runs=22,samples=2478,api=api),indent=2))

if __name__=='__main__':main()
