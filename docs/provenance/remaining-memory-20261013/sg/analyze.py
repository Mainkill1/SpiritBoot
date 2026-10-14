#!/usr/bin/env python3
import datetime as dt, hashlib, json, re, statistics as st, sys, tomllib
from pathlib import Path
ROOT=Path(sys.argv[1]);OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True)
BIOS={'baseline':'be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827','sg':'a159ae7826c2d5122ffe810904fc93ac0dbd471e100cf39dacdb9df30464124f'}
EXE='14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d';ISO='885fef1345ad9612114bb3e332ff6391f505d0c33f8ac5febea707f4a5bcb5d1'
def req(v,why):
 if not v: raise ValueError(why)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def doc(p):return json.loads(p.read_text(encoding='utf-8-sig'))
cap={};want=[(mode,str(n),str(i),str(n*4096)) for mode in ['gather','flat'] for n in [1,2,16,128,512] for i in range(7)]
for p in sorted(ROOT.glob('probe-sg-seven-*')):
 hit=re.fullmatch(r'probe-sg-seven-(\d+)-(baseline|sg)-\d{8}-\d{6}',p.name);req(hit is not None,str(p))
 i,side=int(hit[1]),hit[2];req((i,side) not in cap,'duplicate capture')
 launch=doc(p/'launch.json');inputs=doc(p/'inputs.json');res=doc(p/'result.json');log=(p/'serial.log').read_text();lines=log.splitlines()
 req(launch['biosSha256'].lower()==BIOS[side] and launch['exeSha256'].lower()==EXE and launch['probeSha256'].lower()==ISO and launch['session']>0,'launch identity')
 req(inputs['memoryMiB']==64 and res['exited'] is True and res['exitCode']==0,'profile/exit')
 req(sha(p/'launch-xemu.toml')==inputs['configSha256'].lower(),'launch config hash')
 cfg=tomllib.loads((p/'launch-xemu.toml').read_text(encoding='utf-8-sig'));req(cfg['display']['renderer']=='VULKAN' and cfg['display']['window']['vsync'] is False,'render settings')
 for k in ['flashrom_path','eeprom_path','hdd_path','dvd_path']:cfg['sys']['files'][k]='<per-run-file>'
 req(lines[-1]=='# == sg-performance end PASS ==' and lines.count('# SG-SUMMARY samples=70 failures=0')==1,'terminal pass')
 req(not any('not ok' in x or '# TODO' in x or '# SKIP' in x for x in lines),'nonpass')
 req(re.findall(r'^ok (\d+) - ',log,re.M)==[str(j) for j in range(1,73)],'72 TAP checks')
 req(lines.count('1..72')==1,'plan')
 meta=re.findall(r'^# SG-META version=1 frequency=(\d+) samples=7 max_pages=512$',log,re.M);req(len(meta)==1 and int(meta[0])>0,'clock metadata');freq=int(meta[0])
 rows=re.findall(r'^# SG mode=(gather|flat) pages=(\d+) sample=(\d+) bytes=(\d+) ticks=(\d+) correct=(\d+) status=([0-9a-f]{8}) io=([0-9a-f]{8}) information=(\d+)$',log,re.M)
 req([r[:4] for r in rows]==want,'all ordered samples')
 req(all(int(r[4])>0 and r[5]=='1' and r[6]==r[7]=='00000000' and r[8]==r[3] for r in rows),'correctness/status/count/ticks')
 finish=dt.datetime.fromisoformat(res['utc'].replace('Z','+00:00'));start=finish-dt.timedelta(seconds=res['elapsedSeconds'])
 cap[i,side]={'path':str(p),'side':side,'inputs':inputs,'cfg':cfg,'freq':freq,'rows':rows,'start':start,'finish':finish,'hashes':{n:sha(p/n) for n in ['launch.json','inputs.json','result.json','launch-xemu.toml','serial.log']}}
req(set(cap)=={(i,s) for i in range(7) for s in BIOS},'seven complete pairs')
ordered=[]
for i in range(7):
 pair=sorted([cap[i,s] for s in BIOS],key=lambda c:c['start']);req([c['side'] for c in pair]==(['baseline','sg'] if i%2==0 else ['sg','baseline']),'AB/BA order');ordered+=pair
for a,b in zip(ordered,ordered[1:]):req(a['finish']<=b['start'],'overlap')
ref=ordered[0];keys=['memoryMiB','bootromSha256','backingSha256','backingLength','backingModified','eepromSha256']
for c in ordered:req(c['cfg']==ref['cfg'] and c['freq']==ref['freq'] and all(c['inputs'][k]==ref['inputs'][k] for k in keys),'hardware/input match')
report=[]
for mode in ['gather','flat']:
 for n in [1,2,16,128,512]:
  data={s:[st.median([int(r[4])*1e6/cap[i,s]['freq'] for r in cap[i,s]['rows'] if r[0]==mode and int(r[1])==n and int(r[2])>0]) for i in range(7)] for s in BIOS}
  a,b=data['baseline'],data['sg'];row={'mode':mode,'pages':n,'baseline_us':a,'candidate_us':b,'baseline_median':st.median(a),'candidate_median':st.median(b),'delta_percent':100*(st.median(b)/st.median(a)-1),'faster_pairs':sum(y<x for x,y in zip(a,b)),'direction':'faster' if max(b)<min(a) else 'slower' if min(b)>max(a) else 'overlap'}
  report.append(row);print(json.dumps(row))
receipts=[{k:(v.isoformat() if isinstance(v,dt.datetime) else v) for k,v in c.items() if k not in ['rows','cfg','inputs']} for c in ordered]
(OUT/'report.json').write_text(json.dumps({'pairs':7,'TAP_checks':1008,'all_correct':True,'bios':BIOS,'fixture':ISO,'exe':EXE,'inputs':{k:ref['inputs'][k] for k in keys},'analyzer_sha256':sha(Path(__file__)),'workloads':report,'captures':receipts,'limits':'First sample retained in logs but excluded from warm medians. All seven runs retained. Descriptive ranges only; flat controls must be considered before attributing changes to SG.'},indent=2)+'\n')
