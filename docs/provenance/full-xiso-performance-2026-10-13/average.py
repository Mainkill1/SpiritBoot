import csv,json,re,statistics as st,collections,subprocess,sys,argparse
from pathlib import Path
P=Path(__file__).resolve().parent
parser=argparse.ArgumentParser()
parser.add_argument('--first',type=Path,default=P.parent/'full-xiso-comparison-20261013')
parser.add_argument('--second',type=Path,default=P)
parser.add_argument('--output',type=Path,default=P.parent.parent/'reports/full-xiso-performance-20261013')
args=parser.parse_args();A=args.first.resolve();B=args.second.resolve();OUT=args.output.resolve();OUT.mkdir(parents=True,exist_ok=True)
def load(root):
 subprocess.run([sys.executable,str(root/'analyze.py')],check=True,capture_output=True)
 summary=json.loads((root/'summary.json').read_text());assert summary['leaf_runs']==16 and summary['overall']['pairs']==list(range(1,8)),root
 assert not summary['supplementary_failures'],root
 seen=set();checksums=collections.defaultdict(set)
 expected_workloads=set(re.findall(r'\{"([^"]+)",',(root/'fixtures/kernel-performance-portable/main.c').read_text().split('static const WORK')[1].split('};')[0]))
 assert len(expected_workloads)==40,expected_workloads
 for p in (root/'results').glob('probe-paired-*'):
  match=re.match(r'probe-paired-(kernel-performance-portable|stream-timing|sync-cost)-(\d+)-(complex|candidate)-',p.name)
  assert match,p
  fixture,pair,side=match[1],int(match[2]),match[3]
  assert (fixture,pair,side) not in seen,('duplicate supplementary run',p)
  seen.add((fixture,pair,side))
  result=json.loads((p/'result.json').read_text(encoding='utf-8-sig'));assert result['exited'] and result['exitCode']==0,p
  log=(p/'serial.log').read_text();assert not re.search(r'^not ok',log,re.M),p
  if fixture=='kernel-performance-portable':
   entries=re.findall(r'PERF workload=(\S+) sample=(\d+) iterations=(\d+) ticks=(\d+) correct=(\d) checksum=(\S+)',log)
   assert set(e[0] for e in entries)==expected_workloads,p
   assert all(e[4]=='1' for e in entries),p
   for e in entries:checksums[e[0]].add(e[5])
   assert len({(e[0],e[1]) for e in entries})==len(entries)==118,p
   assert 'workloads=40 failures=0' in log,p
  elif fixture=='stream-timing':
   assert set(re.findall(r'stream phase=(\d+) .*?reads=1024',log))=={'0','1'},p
   assert '# checks=1034 failures=0' in log,p
  else:
   entries=re.findall(r'sync mode=(\d+) sample=(\d+) count=(\d+).*?successes=(\d+)',log)
   assert {(e[0],e[1]) for e in entries}=={(str(m),str(s)) for m in range(4) for s in range(8)},p
   assert len(entries)==32 and all(e[2]==e[3]=='32768' for e in entries),p
   assert '# checks=36 failures=0' in log,p
 assert seen=={(f,p,s) for f in ['kernel-performance-portable','stream-timing','sync-cost'] for p in range(7) for s in ['complex','candidate']},root
 vals={};fails={};ids=json.loads((root/'artifact-identities.json').read_text())
 for p in (root/'results').glob('probe-leaf-*'):
  m=re.match(r'probe-leaf-(\d+)-(complex|candidate)-',p.name);pair=int(m[1]);side=m[2]
  if pair==0:continue
  assert (pair,side) not in vals,p
  log=(p/'serial.log').read_text();freq=int(re.search(r'LEAF-META version=1 frequency=(\d+)',log)[1]);v={};f={}
  for n,t,ok,todo in re.findall(r'LEAF name=(\S+) ticks=(\d+) ok=(\d) todo=(\d)',log):
   assert n not in v,p
   v[n]=int(t)*1e6/freq;f[n]=int(ok)
  assert len(v)==634,p
  vals[pair,side]=v;fails[pair,side]=f
 assert len(vals)==14,root
 assert all(len(h)==1 for h in checksums.values()),('checksum disagreement',root)
 summary['workload_checksums']={n:next(iter(h)) for n,h in checksums.items()}
 return vals,fails,ids,summary
v1,f1,id1,s1=load(A);v2,f2,id2,s2=load(B);assert id1==id2,(id1,id2)
assert s1['workload_checksums']==s2['workload_checksums'],'Semantic checksums differ across campaigns'
names=list(v1[1,'complex']);assert all(set(v)==set(names) for vals in [v1,v2] for v in vals.values())
common=[n for n in names if all(f[p,side][n] for f in [f1,f2] for p in range(1,8) for side in ['complex','candidate'])]
def measures(ns):
 arrays={(c,side):[sum(v[p,side][n] for n in ns) for p in range(1,8)] for c,v in [(1,v1),(2,v2)] for side in ['complex','candidate']}
 out={}
 for c in [1,2]:
  for side in ['complex','candidate']:
   x=arrays[c,side];prefix=f'campaign{c}_{side}'
   out[prefix+'_mean_us']=st.mean(x);out[prefix+'_median_us']=st.median(x);out[prefix+'_min_us']=min(x);out[prefix+'_max_us']=max(x)
 for side in ['complex','candidate']:
  out[side+'_average_mean_us']=st.mean([out[f'campaign{c}_{side}_mean_us'] for c in [1,2]])
  out[side+'_average_median_us']=st.mean([out[f'campaign{c}_{side}_median_us'] for c in [1,2]])
 a,b=out['complex_average_mean_us'],out['candidate_average_mean_us'];out['ratio_of_average_means']=b/a if a else ''
 a,b=out['complex_average_median_us'],out['candidate_average_median_us'];out['ratio_of_average_medians']=b/a if a else ''
 dirs=[]
 for c in [1,2]:
  a,b=arrays[c,'complex'],arrays[c,'candidate']
  dirs.append('faster' if max(b)<min(a) else 'slower' if min(b)>max(a) else 'overlapping ranges')
 out['campaign1_direction'],out['campaign2_direction']=dirs
 out['repeat_direction']=dirs[0] if dirs[0]==dirs[1] else 'not confirmed in both campaigns'
 return out
def save(file,rows):
 with (OUT/file).open('w',newline='') as h:
  w=csv.DictWriter(h,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
rows=[]
for n in names:
 row={'leaf':n,'enabled':True,'eligible_in_both_campaigns':n in common,'skip_reason':'',**measures([n])}
 for c,f in [(1,f1),(2,f2)]:
  for side in ['complex','candidate']:row[f'campaign{c}_{side}_passes']=sum(f[p,side][n] for p in range(1,8))
 if n not in common:row['repeat_direction']='excluded: correctness mismatch'
 rows.append(row)
skips=json.loads((A/'fixtures/api-leaf-performance/disabled-leaves.json').read_text())
assert skips==json.loads((B/'fixtures/api-leaf-performance/disabled-leaves.json').read_text())
assert set(skips).isdisjoint(names)
for n,reason in skips.items(): rows.append(dict.fromkeys(rows[0],'')|{'leaf':n,'enabled':False,'eligible_in_both_campaigns':False,'skip_reason':reason})
assert len(rows)==639
save('averaged-all-leaves.csv',rows)
groups=[]
for group in sorted({n.rsplit('/',1)[0] for n in common}):
 ns=[n for n in common if n.rsplit('/',1)[0]==group]
 groups.append({'group':group,'leaves':len(ns),**measures(ns)})
save('averaged-groups.csv',groups)
overall=measures(common)|{'common_passing_leaves':len(common),'enabled':634,'skipped':5,'measured_pairs_per_campaign':7,'directions':dict(collections.Counter(r['repeat_direction'] for r in rows if r['eligible_in_both_campaigns'])),'failures':[n for n in names if n not in common]}
(OUT/'averaged-summary.json').write_text(json.dumps(overall,indent=2)+'\n')
for file in ['microbenchmarks.csv','streaming.csv','synchronization.csv']:
 a={r['workload']:r for r in csv.DictReader((A/file).open())};b={r['workload']:r for r in csv.DictReader((B/file).open())};assert a.keys()==b.keys(),file
 expected={'microbenchmarks.csv':set(re.findall(r'\{"([^"]+)",',(A/'fixtures/kernel-performance-portable/main.c').read_text().split('static const WORK')[1].split('};')[0])), 'streaming.csv':{f'phase{p}/{m}' for p in range(2) for m in ['elapsed','submit_total','completion_total','submit_p50','completion_p50']}, 'synchronization.csv':{'0','1','2','3'}}[file]
 assert set(a)==expected,(file,set(a))
 out=[]
 for name in a:
  ra,rb=a[name],b[name];assert ra['pairs']==rb['pairs']=='7',(file,name)
  row={'workload':name}
  for c,r in [(1,ra),(2,rb)]:
   for side in ['complex','spiritboot']:
    for measure in ['median_us','min_us','max_us']:row[f'campaign{c}_{side}_{measure}']=float(r[side+'_'+measure])
  for side in ['complex','spiritboot']:row[side+'_average_median_us']=st.mean([float(r[side+'_median_us']) for r in [ra,rb]])
  row['ratio_of_average_medians']=row['spiritboot_average_median_us']/row['complex_average_median_us']
  row['campaign1_direction']=ra['direction'];row['campaign2_direction']=rb['direction'];row['repeat_direction']=ra['direction'] if ra['direction']==rb['direction'] else 'not confirmed in both campaigns';out.append(row)
 save('averaged-'+file,out)
print(json.dumps(overall,indent=2))
