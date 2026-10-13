import json,re,statistics as st
from pathlib import Path
CONTRACT=json.loads((Path(__file__).parent/"contracts.json").read_text())

def need(ok, message):
    if not ok: raise ValueError(message)

def one(pattern, log):
    found = re.findall(pattern, log, re.M)
    need(len(found)==1, 'missing/duplicate '+pattern)
    return found[0]

def parse_micro(log):
    need(sum(line.startswith('# PERF') for line in log.splitlines())==120,'surplus or missing PERF record')
    need(log.count('== kernel-performance-portable begin ==')==1 and log.count('== kernel-performance-portable end PASS ==')==1,'duplicate boundaries')
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
