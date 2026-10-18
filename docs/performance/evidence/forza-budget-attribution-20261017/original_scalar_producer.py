import json,sys,statistics,collections
from pathlib import Path
p=Path(sys.argv[1]);active={};calls={};reads=[];wait_active={};waits=[];anomalies=collections.Counter()
for line in p.open():
 if not line.startswith('forza_io '):continue
 d=dict(x.split('=',1) for x in line.split()[1:] if '=' in x);k=d['kind'];t=int(d['host_ns']);th=d['thread']
 if k=='_XeNtReadFile@32' and d['returning']=='0' and d['a4']=='001103e0':
  r={'iosb':d['a5'],'begin':t,'thread':th,'bytes':int(d['a7'],16),'offset':d['p8'],'caller':d['ret']};active[r['iosb']]=r;calls[th]=r;reads.append(r)
 if k=='title_read_return' and th in calls:calls.pop(th).update(returned=t,result=d['eax'])
 if k=='io_complete' and d['iosb'] in active:
  r=active[d['iosb']];r['done']=t;r['status']=d['status'];r['info']=int(d['info']);r['complete_count']=r.get('complete_count',0)+1
 if k=='title_apc_dispatch' and d['a2'] in active:active[d['a2']]['dispatch']=t
 if k=='world_completion_callback' and d['a3'] in active:active.pop(d['a3']).update(callback=t,error=d['a1'],callback_bytes=int(d['a2'],16))
 if k=='delay_thread' and d['ret']=='00264e84':
  slot=(int(d['a3'],16)-int(d['esp'],16))//4
  zero=1<=slot<=7 and d.get('a'+str(slot))=='00000000' and d.get('a'+str(slot+1))=='00000000'
  w={'start':t,'thread':th,'mode':d['a1'],'alertable':d['a2'],'zero':zero};waits.append(w);wait_active[th]=w
 if k=='title_delay_return' and th in wait_active:wait_active.pop(th).update(end=t,status=d['eax'])
def st(v):
 s=sorted(v);return {'n':len(s),'median':statistics.median(s),'p95':s[min(len(s)-1,int(len(s)*.95))],'max':max(s)} if s else {'n':0}
r=[x for x in reads if all(k in x for k in ['done','returned','callback'])];w=[x for x in waits if 'end' in x];inside=[]
for x in r:
 hits=[y for y in w if y['thread']==x['thread'] and y['start']<=x['done']<=y['end'] and y['zero'] and y['alertable']=='00000001']
 for y in hits:inside.append({'read':x,'wait':y,'callback_inside_wait':x['callback']<=y['end']})
out={'reads_seen':len(reads),'joined':len(r),'return_statuses':dict(collections.Counter(x['result'] for x in r)),'completion_statuses':dict(collections.Counter(x['status'] for x in r)),'complete_counts':dict(collections.Counter(x['complete_count'] for x in r)), 'issue_to_complete_ms':st([(x['done']-x['begin'])/1e6 for x in r]),'complete_to_callback_ms':st([(x['callback']-x['done'])/1e6 for x in r]),'issue_to_return_ms':st([(x['returned']-x['begin'])/1e6 for x in r]),'zero_wait_ms':st([(x['end']-x['start'])/1e6 for x in w if x['zero']]),'zero_wait_statuses':dict(collections.Counter(x['status'] for x in w if x['zero'])),'completed_inside_zero_wait':len(inside),'callback_same_zero_wait':sum(x['callback_inside_wait'] for x in inside)}
print(json.dumps(out,indent=2));p.with_suffix('.pair-summary.json').write_text(json.dumps(out,indent=2));p.with_suffix('.pair-reads.json').write_text(json.dumps(r,indent=2));p.with_suffix('.pair-waits.json').write_text(json.dumps(w,indent=2));p.with_suffix('.pair-inside.json').write_text(json.dumps(inside,indent=2))
