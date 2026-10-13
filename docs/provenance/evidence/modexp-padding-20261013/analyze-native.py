#!/usr/bin/env python3
"""Strict immutable guest/metadata validation and exact counter comparison."""
import argparse,csv,hashlib,json,re,shutil,sys,tomllib
from datetime import datetime,timedelta
from fractions import Fraction
from pathlib import Path
from statistics import median
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT))
from tools.firmware import grade_tap
from tools.kernel_performance import WORKLOADS,META,SAMPLE
p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('output',type=Path);args=p.parse_args()
args.output.mkdir(parents=True,exist_ok=True)
WORK={k:v for k,v in WORKLOADS.items() if k!='pool-fragmented-fail-4'}
BIOS={'complex':'1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f','baseline':'be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827','crypto':'d0e907d32d12d950dbcf97d9678079bc81e3dead5c8f5d66079cbd30621d5cc2'}
EXE='14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d';ISO='65da3568167cd7e25eec3da4baaffbe65c7fae931078659885297e657412a705';CONTRACT='859e5e1220d2dfa70075ce40fdcbf9fbf6ff3e21200f0507030e0bfb99988f26'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def need(ok,label):
 if not ok:raise ValueError(label)
def normconfig(p):
 c=tomllib.loads(p.read_text(encoding='utf-8-sig'));f=c['sys']['files']
 for k in ['flashrom_path','eeprom_path','hdd_path','dvd_path']:f[k]='<'+k+'>'
 return c
inputs_reference=None;config_reference=None;manifest=[]
def validate(d,side,iso):
 global inputs_reference,config_reference
 launch=read(d/'launch.json');result=read(d/'result.json');inputs=read(d/'inputs.json');serial=(d/'serial.log').read_text()
 need(result['exited'] is True and result['exitCode']==0 and result['elapsedSeconds']>0,d.name+': exit status')
 need(launch['session']==1 and launch['pid']>0 and launch['exeSha256'].lower()==EXE,d.name+': interactive executable')
 need(launch['biosSha256'].lower()==BIOS[side] and launch['probeSha256'].lower()==iso,d.name+': firmware/guest identity')
 need(inputs['memoryMiB']==64,d.name+': memory layout')
 need(set(inputs)=={'backing','backingLength','eepromSha256','memoryMiB','bootromSha256','backingModified','configSha256','backingSha256'},d.name+': input record shape')
 need(inputs['configSha256'].lower()==sha(d/'launch-xemu.toml'),d.name+': launch config bytes differ')
 seeds={k:v for k,v in inputs.items() if k!='configSha256'}
 if inputs_reference is None:inputs_reference=seeds
 need(seeds==inputs_reference,d.name+': input seed/record differs')
 config=normconfig(d/'launch-xemu.toml');need(config==normconfig(d/'xemu.toml'),d.name+': launch/runtime config differs')
 if config_reference is None:config_reference=config
 need(config==config_reference,d.name+': normalized configuration differs')
 need(config['display']['renderer']=='VULKAN' and config['display']['window']['vsync'] is False and config['perf']['cache_shaders'] is False,d.name+': timing configuration')
 local=args.output/'native'/d.name;local.mkdir(parents=True,exist_ok=True)
 names=['serial.log','launch.json','inputs.json','result.json','launch-xemu.toml','xemu.toml']
 for n in names:shutil.copy2(d/n,local/n)
 manifest.append({'run':d.name,'side':side,'bios':launch['biosSha256'].lower(),'probe':iso,'inputs':inputs,'files':{n:sha(d/n) for n in names},'result':result})
 return serial,result
contracts=[]
for side in BIOS:
 ds=list(args.results.glob('probe-crypto-contract-'+side+'-*'));need(len(ds)==1,'contract run cardinality '+side)
 serial,result=validate(ds[0],side,CONTRACT);tap=grade_tap(serial)
 failures=re.findall(r'^not ok (\d+) - (.*)$',serial,re.M)
 expected=[str(i) for i in range(282,307,4)] if side=='complex' else []
 need([x[0] for x in failures]==expected,side+': unexpected contract failure')
 need(tap['plan']==364 and tap['ran']==364 and tap['ok']==364-len(expected) and tap['failed']==len(expected) and tap['todo']==tap['skipped']==0 and not tap['errors'],side+': contract TAP')
 records=re.findall(r'^# modexp vector=(\d+) words=(\d+) alias=(\d+) status=(\d+) result=([0-9a-f]{8}):([0-9a-f]{8})$',serial,re.M)
 need(len(records)==91 and [(int(x[0]),int(x[2])) for x in records]==[(v,a) for v in range(13) for a in range(7)],side+': vector ordering')
 need(all(x[3]=='1' for x in records),side+': vector return status')
 contracts.append({'run':ds[0].name,'side':side,'tap':tap,'failures':failures,'vector10':[list(x) for x in records if x[0]=='10']})
trials={};frequencies={};ordered=[];checksum_reference=None
for pair in range(7):
 for side in BIOS:
  ds=list(args.results.glob(f'probe-crypto-seven-{pair}-{side}-*'));need(len(ds)==1,f'pair cardinality {pair}/{side}')
  d=ds[0];serial,result=validate(d,side,ISO);tap=grade_tap(serial)
  need(tap['passed'] and tap['plan']==41 and tap['ok']==tap['ran']==41 and tap['failed']==tap['todo']==tap['skipped']==0 and not tap['errors'],d.name+': TAP')
  lines=serial.splitlines();need(lines[0]=='== kernel-performance-portable begin ==' and lines[-1]=='== kernel-performance-portable end PASS ==',d.name+': boundaries')
  need(lines.count(lines[0])==lines.count(lines[-1])==1,d.name+': duplicate boundaries')
  perf=[l for l in lines if 'PERF' in l];meta=META.fullmatch(perf[0]);need(meta is not None and meta[1]=='KeQueryPerformanceCounter' and 0<int(meta[2])<2**64,d.name+': clock metadata')
  freq=int(meta[2]);frequencies.setdefault(side,freq);need(frequencies[side]==freq,d.name+': frequency changed within BIOS')
  need(perf[-1]=='# PERF-SUMMARY workloads=40 failures=0' and len(perf)==120,d.name+': complete summary')
  expected=[(n,s) for n in WORK for s in range(1 if n=='object-cold-64' else 3)];actual=[];values={n:[] for n in WORK};checksums={n:[] for n in WORK};total=Fraction(0)
  for line in perf[1:-1]:
   m=SAMPLE.fullmatch(line);need(m is not None,d.name+': malformed PERF line')
   n,s,i,t,h=m.groups();i,t,s=int(i),int(t),int(s);need(n in WORK and i==WORK[n] and 0<=t<2**64,d.name+': workload dimensions')
   actual.append((n,s));values[n].append(Fraction(t*1000000,freq*i));checksums[n].append(h);total+=Fraction(t*1000000,freq)
  need(actual==expected,d.name+': missing/duplicate/out-of-order samples')
  need(re.findall(r'^ok \d+ - (.+)$',serial,re.M)==['public-known-answers']+list(WORK),d.name+': TAP names')
  need(all(len(set(v))==1 for v in checksums.values()),d.name+': within-run checksum changes')
  if checksum_reference is None:checksum_reference=checksums
  need(checksums==checksum_reference,d.name+': cross-run checksum changes')
  end=datetime.fromisoformat(result['utc'].replace('Z','+00:00'));start=end-timedelta(seconds=result['elapsedSeconds'])
  ordered.append((start,end,pair,side,d.name))
  trials[pair,side]={'values':{n:median(v) for n,v in values.items()},'raw':values,'total':total,'elapsed':result['elapsedSeconds']}
ordered.sort();previous=None
for start,end,pair,side,name in ordered:
 need(previous is None or start>=previous,name+': overlapping process intervals');previous=end
for pair in range(7):need([x[3] for x in ordered if x[2]==pair]==(['baseline','crypto','complex'] if pair%2==0 else ['complex','crypto','baseline']),f'pair {pair}: nonalternating triplet order')
def record(f):return {'numerator':f.numerator,'denominator':f.denominator}
def metrics(a,b):
 delta=median(a)-median(b);direction='lower disjoint ranges' if max(b)<min(a) else 'higher disjoint ranges' if min(b)>max(a) else 'overlapping ranges'
 return {'median_change_percent':float((median(b)/median(a)-1)*100),'lower_pairs':sum(y<x for x,y in zip(a,b)),'higher_pairs':sum(y>x for x,y in zip(a,b)),'range_class':direction,'exact_median_difference_us':record(delta)}
rows=[]
for n in WORK:
 vals={s:[trials[k,s]['values'][n] for k in range(7)] for s in BIOS}
 row={'workload':n}
 for s,a in vals.items():row.update({s+'_median_us':float(median(a)),s+'_min_us':float(min(a)),s+'_max_us':float(max(a))})
 m=metrics(vals['baseline'],vals['crypto']);row.update(m);row['crypto_over_complex']=float(median(vals['crypto'])/median(vals['complex']))
 rows.append(row)
with (args.output/'all40.csv').open('w',newline='') as f:
 fields=[k for k in rows[0] if k!='exact_median_difference_us'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows([{k:r[k] for k in fields} for r in rows])
suite={s:[trials[k,s]['total'] for k in range(7)] for s in BIOS};aggregate={s:{'median_us':float(median(a)),'min_us':float(min(a)),'max_us':float(max(a)),'raw_totals_exact':[record(x) for x in a]} for s,a in suite.items()};aggregate.update(metrics(suite['baseline'],suite['crypto']))
report={'schema':1,'validated_kernel_runs':21,'workloads_per_run':40,'samples_per_workload':{'object-cold-64':1,'others':3},'contracts':contracts,'frequencies_hz':frequencies,'aggregate_all_recorded_workload_samples':aggregate,'workloads':rows,'chronological_execution':[{'run':n,'pair':k,'side':s,'derived_start':a.isoformat(),'end':b.isoformat()} for a,b,k,s,n in ordered],'manifest':manifest,'limitations':['Process intervals derive from recorded exit UTC and elapsed duration; overlays are identified by exported metadata/configuration, not independently reread disk image bytes.','Complex high-base vector10 differs from both unchanged SpiritBoot answers; all seven reference failures are retained.','Counter normalization uses each BIOS reported frequency; no same-frequency assumption is made.','Aggregate sums all118 declared iteration-batch samples; boot time and FPS are not measured.']}
(args.output/'native-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'kernel_runs':21,'workloads':40,'contracts':[(x['side'],x['tap']['ok'],x['tap']['failed']) for x in contracts],'aggregate':aggregate,'changes':[(r['workload'],round(r['median_change_percent'],3),r['range_class']) for r in rows]},indent=2))
