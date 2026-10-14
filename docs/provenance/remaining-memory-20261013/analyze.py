#!/usr/bin/env python3
import csv,datetime as dt,hashlib,json,re,statistics as st,sys,tomllib
from pathlib import Path
import contracts as m
ROOT=Path(sys.argv[1]);OUT=Path(sys.argv[2]);MAN=Path(sys.argv[3]);BIOS_CANDIDATE=sys.argv[4];TREE=sys.argv[5];OUT.mkdir(parents=True,exist_ok=True)
BIOS={'baseline':'be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827','combined':BIOS_CANDIDATE,'complex':'1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f'}
FIX={'api-leaf-performance':'099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33','kernel-performance-portable':'65da3568167cd7e25eec3da4baaffbe65c7fae931078659885297e657412a705','stream-timing':'efa6ef23e61a2ac3a40298d2e79e297640c02d7ab706b64801cc79d4472cd993','sync-cost':'06432e109939b83c31bf1c58884260a0d29beed76b3bc285b274342189353d89','api-clean':'64ac9ec3d5a9cb980b3bddc82d535985d42e90455bad20b159586637a9db0f44','storage':'9273b50ac9a3699aee02730c0e6eb6a2740a74de1f8f306643b41772f7e6ad23','timer':'37940971fa6f0501bc49c1198ea1ca1c49d031470f1fa883e161259ee876c83b'}
EXE='14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d'
INTEGRATED={'process-thread-contract-v6':(197,'51754ccc18fedc132c41fdec56ee9bb665a8d15f6521244d2e16dc036db7a45c'),'modexp-contract':(364,'859e5e1220d2dfa70075ce40fdcbf9fbf6ff3e21200f0507030e0bfb99988f26'),'vm-zero-reuse':(52,'52675ec0461587ac574e3e1a53a596b986480391155bc5756ae795da721a9647'),'mm-system-common':(59,'138733b225a59eb9be6f735a38a428999777545b0134e23fc162bf43f82532a3'),'system-va-validity':(7,'1bf359dd0eea72295246925b12509a62c0f8640192fed812e2073ed701b91741'),'pool-plain':(697,'7478e1ecc3fb8e7fbbafc48a981f3ac7f6710fe028d0133e196411ec8490a7d2'),'sg-performance-v2':(72,'885fef1345ad9612114bb3e332ff6391f505d0c33f8ac5febea707f4a5bcb5d1')}
FIX.update({n:h for n,(plan,h) in INTEGRATED.items()})
PROCESS={n for n in m.TODOS if n.startswith('ke/')};FIXED=m.TODOS-PROCESS
req=m.require
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def doc(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def api(log,side,clean=False):
 todo=set() if clean else m.TODOS;passed=todo if side!='baseline' else FIXED
 ordinary=m.tap(log,639,todo,m.SKIPS,passed)
 req(ordinary==[n for n in m.EXPECTED_LEAVES if n not in todo],'ordered ordinary TAP/LEAF identity')
 req(m.one(r'^# tests=(\d+) passed=(\d+) failed=(\d+) skipped=(\d+)$',log)==('639','634','0','5'),'API summary')
 req(m.one(r'^== api-regression end (\w+) ==$',log)=='PASS','API terminal')
 freq=int(m.one(r'^# LEAF-META version=1 frequency=(\d+).*$',log));req(freq>0,'API clock')
 rows=re.findall(r'^# LEAF name=(\S+) ticks=(\d+) ok=(\d+) todo=(\d+)$',log,re.M);req(len(rows)==634 and len(re.findall(r'^# LEAF(?: |$).*$',log,re.M))==634,'API rows/malformed records')
 req([r[0] for r in rows]==m.EXPECTED_LEAVES,'API ordered leaf set')
 for name,ticks,ok,t in rows:req((int(ok),int(t))==((int(name in passed),1) if name in todo else (1,0)),'API semantic '+name)
 return {n:int(t)*1e6/freq for n,t,ok,d in rows}
def receipt(p,fixture,side):
 launch,inputs,res=doc(p/'launch.json'),doc(p/'inputs.json'),doc(p/'result.json')
 req(launch['biosSha256'].lower()==BIOS[side] and launch['exeSha256'].lower()==EXE and launch['probeSha256'].lower()==FIX[fixture] and launch['session']>0,str(p)+' identity')
 req(inputs['memoryMiB']==64 and res['exited'] is True and res['exitCode']==0,'profile/exit')
 req(sha(p/'launch-xemu.toml')==inputs['configSha256'].lower(),'frozen config')
 cfg=tomllib.loads((p/'launch-xemu.toml').read_text(encoding='utf-8-sig'));req(cfg['display']['renderer']=='VULKAN' and cfg['display']['window']['vsync'] is False,'render')
 req(cfg['sys']['files']['flashrom_path'].lower()==launch['bios'].lower(),'BIOS configpath')
 for k in ['flashrom_path','eeprom_path','hdd_path','dvd_path']:cfg['sys']['files'][k]='<run-file>'
 finish=dt.datetime.fromisoformat(res['utc'].replace('Z','+00:00'));req(0<res['elapsedSeconds']<300,'duration');start=finish-dt.timedelta(seconds=res['elapsedSeconds'])
 return {'path':str(p),'fixture':fixture,'side':side,'inputs':inputs,'config':cfg,'started':start,'ended':finish,'hashes':{f:sha(p/f) for f in ['launch.json','inputs.json','result.json','serial.log','launch-xemu.toml']},'log':(p/'serial.log').read_text()}
manifest=doc(MAN);req(manifest['source_tree']==TREE and manifest['flash_sha256']==BIOS_CANDIDATE and manifest['memory_mib']==64 and manifest['status']=='built','build manifest')
cap={};extra={}
for p in sorted(ROOT.glob('probe-closing-*')):
 hit=re.fullmatch(r'probe-closing-(api-leaf-performance|kernel-performance-portable|stream-timing|sync-cost)-(\d+)-(baseline|combined|complex)-\d{8}-\d{6}',p.name)
 if hit:
  f,i,s=hit[1],int(hit[2]),hit[3];req((f,i,s) not in cap,'duplicate');cap[f,i,s]=receipt(p,f,s)
 else:
  hit=re.fullmatch(r'probe-closing-(api-clean|storage|timer)-(combined|complex)-\d{8}-\d{6}',p.name)
  if hit:req((hit[1],hit[2]) not in extra,'duplicate extra');extra[hit[1],hit[2]]=receipt(p,hit[1],hit[2])
  else:raise ValueError('Unknown closing run '+p.name)
paired=['api-leaf-performance','kernel-performance-portable','stream-timing','sync-cost'];req(set(cap)=={(f,i,s) for f in paired for i in range(3) for s in BIOS},'36 paired runs')
req(set(extra)=={('api-clean','combined'),('api-clean','complex'),('storage','combined'),('timer','combined')},'four extra contracts')
integrated={}
for p in sorted(ROOT.glob('probe-integrated-*')):
 hit=re.fullmatch(r'probe-integrated-(.+)-\d{8}-\d{6}',p.name);req(hit is not None and hit[1] in INTEGRATED,'integrated profile');name=hit[1];req(name not in integrated,'duplicate integrated');c=receipt(p,name,'combined');m.tap(c['log'],INTEGRATED[name][0]);integrated[name]=c
req(set(integrated)==set(INTEGRATED),'seven integrated contracts')
ordered=sorted([*cap.values(),*extra.values(),*integrated.values()],key=lambda c:c['started'])
for a,b in zip(ordered,ordered[1:]):req(a['ended']<=b['started'],'overlap')
for f in paired:
 for i in range(3):req([c['side'] for c in sorted([cap[f,i,s] for s in BIOS],key=lambda c:c['started'])]==(['baseline','combined','complex'] if i%2==0 else ['complex','combined','baseline']),'triplet order')
ref=ordered[0];keys=['memoryMiB','bootromSha256','backingSha256','backingLength','backingModified','eepromSha256']
for c in ordered:req(c['config']==ref['config'] and all(c['inputs'][k]==ref['inputs'][k] for k in keys),'runtime invariants')
values={};parsers={'kernel-performance-portable':m.parse_micro,'stream-timing':m.parse_stream,'sync-cost':m.parse_sync}
for (f,i,s),c in cap.items():values[f,i,s]=api(c['log'],s) if f=='api-leaf-performance' else parsers[f](c['log'])
for (f,s),c in extra.items():
 if f=='api-clean':api(c['log'],s,True)
 elif f=='storage':storage=m.parse_storage(c['log'])
 else:timer=m.parse_apc(c['log'])
rows=[]
for f in paired:
 for name in values[f,0,'baseline']:
  per={s:[values[f,i,s][name] for i in range(3)] for s in BIOS}
  rows.append({'fixture':f,'workload':name,'eligible':f!='api-leaf-performance' or name not in PROCESS,'candidate_vs_baseline':m.stats(per['baseline'],per['combined']),'candidate_vs_complex':m.stats(per['complex'],per['combined'])})
common=set(m.EXPECTED_LEAVES)-PROCESS
per={s:[sum(values['api-leaf-performance',i,s][n] for n in common) for i in range(3)] for s in BIOS}
totals={'candidate_vs_baseline':m.stats(per['baseline'],per['combined']),'candidate_vs_complex':m.stats(per['complex'],per['combined'])}
for comp in ['candidate_vs_baseline','candidate_vs_complex']:
 table=[{'fixture':r['fixture'],'workload':r['workload'],'eligible':r['eligible'],**r[comp]} for r in rows]
 for n,reason in m.SKIPS.items():table.append({'fixture':'api-leaf-performance','workload':n,'eligible':False,**dict.fromkeys(table[0].keys()-{'fixture','workload','eligible'},'')})
 with (OUT/(comp+'.csv')).open('w') as out:
  w=csv.DictWriter(out,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
receipts=[{k:(v.isoformat() if isinstance(v,dt.datetime) else v) for k,v in c.items() if k not in ['log','config']} for c in ordered]
report={'validated':True,'runs':47,'bios':BIOS,'source_tree':TREE,'fixtures':FIX,'exe':EXE,'API':{'planned':639,'enabled':634,'baseline_true_passes':632,'candidate_true_passes':634,'complex_true_passes':634,'ordinary_clean_passes':634,'remainingTODOs':[],'frozen_skips':m.SKIPS,'common_cost_leaves':632,'totals':totals},'integrated_checks':{n:plan for n,(plan,h) in INTEGRATED.items()},'storage':storage,'timer':timer,'rows':rows,'receipts':receipts,'limits':'Three matched triplets, descriptive ranges. Wait/pressure aggregates are not game/FPS measures. Five frozen exclusions retained; two baseline process failures excluded from costs.'}
(OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:report[k] for k in ['validated','runs','API','storage','timer']},indent=2))
