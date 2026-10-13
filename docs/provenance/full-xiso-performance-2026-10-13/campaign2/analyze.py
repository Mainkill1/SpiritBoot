import re,json,csv,hashlib,statistics as st
from pathlib import Path
ROOT=Path(__file__).resolve().parent
runs={}
identities={}
for p in (ROOT/'results').glob('probe-*'):
 r=json.loads((p/'result.json').read_text(encoding='utf-8-sig'))
 log=(p/'serial.log').read_text(errors='replace')
 launch=json.loads((p/'launch.json').read_text(encoding='utf-8-sig'))
 runs[p.name]={'result':r,'log':log,'launch':launch}
 if p.name.startswith(('probe-leaf-','probe-paired-')):
  side='complex' if '-complex-' in p.name else 'candidate'
  expected={'complex':'1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f','candidate':'1ed234ebaf8e95937225c3002b6eac26257b0f3d1ff8f3d6a3aabd464955fb0b'}[side]
  assert launch['biosSha256'].lower()==expected,p.name
  assert launch['exeSha256'].lower()=='14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d',p.name
  assert launch['session']!=0,p.name
  fixture='api-leaf-performance' if p.name.startswith('probe-leaf-') else re.match(r'probe-paired-(.*)-[0-6]-(complex|candidate)-',p.name)[1]
  identities.setdefault(fixture,set()).add(launch['probeSha256'].lower())
for fixture,hashes in identities.items():
 assert len(hashes)==1,(fixture,hashes)
 iso={'api-leaf-performance':ROOT/'fixtures/api-leaf-performance/nxkrnl-api-regression.iso','kernel-performance-portable':ROOT/'fixtures/kernel-performance-portable/kernel-performance.iso'}.get(fixture,ROOT/(fixture+'.iso'))
 if not iso.exists() and fixture=='kernel-performance-portable': iso=next((ROOT/'fixtures/kernel-performance-portable').glob('*.iso'))
 assert hashlib.sha256(iso.read_bytes()).hexdigest() in hashes,fixture
(ROOT/'artifact-identities.json').write_text(json.dumps({k:next(iter(v)) for k,v in identities.items()},indent=2)+'\n')
def csvout(name,rows):
 if rows:
  with (ROOT/name).open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
def stats(a,b):
 ma,mb=st.median(a),st.median(b)
 ratios=[y/x for x,y in zip(a,b) if x]
 faster=sum(y<x for x,y in zip(a,b));slower=sum(y>x for x,y in zip(a,b))
 return {'complex_median_us':ma,'spiritboot_median_us':mb,'ratio_spiritboot_over_complex':mb/ma if ma else None,'complex_min_us':min(a),'complex_max_us':max(a),'spiritboot_min_us':min(b),'spiritboot_max_us':max(b),'faster_pairs':faster,'slower_pairs':slower,'direction':('faster' if max(b)<min(a) else 'slower' if min(b)>max(a) else 'overlapping ranges')}
leaves={};skips=json.loads((ROOT/'fixtures/api-leaf-performance/disabled-leaves.json').read_text())
for name,r in runs.items():
 m=re.match(r'probe-leaf-(\d+)-(complex|candidate)-',name)
 if not m:continue
 pair,side=int(m[1]),m[2]
 assert r['result']['exited'] and r['result']['exitCode']==0,name
 assert re.search(r'== api-regression end (PASS|FAIL) ==',r['log']),name
 freq=int(re.search(r'LEAF-META version=1 frequency=(\d+)',r['log'])[1])
 entries={n:(int(t)*1e6/freq,int(ok),int(todo)) for n,t,ok,todo in re.findall(r'# LEAF name=(\S+) ticks=(\d+) ok=(\d) todo=(\d)',r['log'])}
 assert len(entries)==634,(name,len(entries))
 assert set(re.findall(r'^ok \d+ - (\S+) # SKIP ',r['log'],re.M))==set(skips),name
 if leaves: assert set(entries)==set(next(iter(leaves.values()))),name
 assert (pair,side) not in leaves,('duplicate trial',name)
 leaves[pair,side]=entries
pairs=[p for p in range(1,8) if (p,'complex') in leaves and (p,'candidate') in leaves]
rows=[];groups={};totals={};failures=[]
if pairs:
 names=list(leaves[pairs[0],'complex'])
 common=[n for n in names if all(leaves[p,s][n][1] for p in pairs for s in ['complex','candidate'])]
 for n in names:
  a=[leaves[p,'complex'][n][0] for p in pairs];b=[leaves[p,'candidate'][n][0] for p in pairs]
  ca=sum(leaves[p,'complex'][n][1] for p in pairs);cb=sum(leaves[p,'candidate'][n][1] for p in pairs)
  row={'leaf':n,'complex_passes':ca,'spiritboot_passes':cb,'trials':len(pairs),'eligible':n in common,'skip_reason':'',**stats(a,b)}
  if n not in common:failures.append(n);row['direction']='excluded: correctness mismatch'
  rows.append(row)
 for n,reason in skips.items():rows.append(dict.fromkeys(rows[0],'')|{'leaf':n,'eligible':False,'skip_reason':reason})
 csvout('all-leaves.csv',rows)
 grows=[]
 for group in sorted(set(n.rsplit('/',1)[0] for n in common)):
  ns=[n for n in common if n.rsplit('/',1)[0]==group]
  a=[sum(leaves[p,'complex'][n][0] for n in ns) for p in pairs];b=[sum(leaves[p,'candidate'][n][0] for n in ns) for p in pairs]
  grows.append({'group':group,'leaves':len(ns),**stats(a,b)})
 csvout('groups.csv',grows)
 a=[sum(leaves[p,'complex'][n][0] for n in common) for p in pairs];b=[sum(leaves[p,'candidate'][n][0] for n in common) for p in pairs]
 totals=stats(a,b)|{'common_passing':len(common),'timed':len(names),'skips':len(skips),'pairs':pairs,'failures':failures}
perf={};streams={};sync={};suppfails=[]
for name,r in runs.items():
 m=re.match(r'probe-paired-(kernel-performance-portable|stream-timing|sync-cost)-(\d+)-(complex|candidate)-',name)
 if not m:continue
 fixture,pair,side=m[1],int(m[2]),m[3]
 assert r['result']['exited'] and r['result']['exitCode']==0,name
 failures_in_log=re.findall(r'^not ok.*$',r['log'],re.M)
 if failures_in_log:
  suppfails.append({'run':name,'failures':failures_in_log})
  continue
 if fixture=='kernel-performance-portable':
  assert 'end PASS' in r['log'],name
  freq=int(re.search(r'PERF-META.*?frequency=(\d+)',r['log'])[1]);values={}
  for n,s,i,t,c,h in re.findall(r'PERF workload=(\S+) sample=(\d+) iterations=(\d+) ticks=(\d+) correct=(\d+) checksum=(\S+)',r['log']):
   assert c=='1',name
   values.setdefault(n,[]).append(int(t)*1e6/freq/int(i))
  for n,v in values.items():perf[n,pair,side]=st.median(v)
 elif fixture=='stream-timing':
  for phase,elapsed,submit,sp50,sp95,smax,completion,cp50,cp95,cmax in re.findall(r'stream phase=(\d+).*?elapsed_ms=(\d+) submit_us_total=(\d+) p50=(\d+) p95=(\d+) max=(\d+) completion_us_total=(\d+) p50=(\d+) p95=(\d+) max=(\d+)',r['log']):
   for key,val in [('elapsed',int(elapsed)*1000),('submit_total',int(submit)),('completion_total',int(completion)),('submit_p50',int(sp50)),('completion_p50',int(cp50))]:streams[f'phase{phase}/{key}',pair,side]=val
 else:
  values={}
  for mode,s,count,t,us,success in re.findall(r'sync mode=(\d+) sample=(\d+) count=(\d+) ticks=(\d+) us=(\d+) successes=(\d+)',r['log']):
   assert count==success,name
   values.setdefault(mode,[]).append(int(us)/int(count))
  for n,v in values.items():sync[n,pair,side]=st.median(v)
for file,data in [('microbenchmarks.csv',perf),('streaming.csv',streams),('synchronization.csv',sync)]:
 out=[]
 for n in sorted({k[0] for k in data}):
  ps=[p for p in range(7) if (n,p,'complex') in data and (n,p,'candidate') in data]
  if ps:out.append({'workload':n,'pairs':len(ps),**stats([data[n,p,'complex'] for p in ps],[data[n,p,'candidate'] for p in ps])})
 csvout(file,out)
summary={'overall':totals,'supplementary_failures':suppfails,'completed_runs':len(runs),'leaf_runs':len(leaves)}
(ROOT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
