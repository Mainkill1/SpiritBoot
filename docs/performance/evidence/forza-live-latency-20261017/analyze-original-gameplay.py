from pathlib import Path
import json,collections,statistics
r=Path(__file__).parent;active={};contexts={};pending={};rows=[];apis={};calls=[];allrows=[]
for line in (r/'qemu-paused.log').open(errors='replace'):
 if not line.startswith('forza_io '):continue
 d=dict(x.split('=',1) for x in line.split()[1:] if '=' in x);k=d['kind'];t=int(d['host_ns'])/1e6;key=d['irp']
 if k=='_XeNtReadFile@32' and d['returning']=='0':apis[d['thread']]={'caller':d['ret'],'offset':int(d['p8'],16),'size':int(d['a7'],16),'iosb':d['a5'],'time':t};calls.append(d)
 if k=='fatx_dispatch':contexts[key]={'name':d['name'],'offset':d['offset'],'api':apis.get(d['thread'],{}).copy()}
 if k=='native_submit':active[key]={'start':t,'end':None,'irp':key,'file':contexts.get(key,{}).get('name',''),'api':contexts.get(key,{}).get('api',{}),'free':int(d['free_pages']),'bytes':int(d['a3'],16),'thread':d['thread']}
 if k=='io_complete':
  contexts.pop(key,None)
  if key in active:
   x=active.pop(key);x.update(end=t,status=d['status']);pending[key]=x;allrows.append(x)
   if 'FarmersLipShort.res' in x['file']:rows.append(x)
 if k=='io_apc_delivery' and key in pending:
  pending.pop(key)['apc']=t
zero=rows[0]['start'];out=[]
for x in rows:
 if x['start']-zero<17000:continue
 x=x.copy();x['relative_s']=(x['start']-zero)/1000;x['io_ms']=x['end']-x['start'];x['apc_ms']=x.get('apc',x['end'])-x['end'];out.append(x)
for x in out[-32:]:print(json.dumps(x))
def stat(vals):
 v=sorted(vals);return {'n':len(v),'median':statistics.median(v),'p95':v[min(len(v)-1,int(len(v)*.95))],'max':max(v)} if v else {}
summary={'gameplay_reads':len(out),'bytes':sum(x['bytes'] for x in out),'io_ms':stat([x['io_ms'] for x in out]),'completion_to_kernel_apc_ms':stat([x['apc_ms'] for x in out]),'issue_gap_ms':stat([b['start']-a['start'] for a,b in zip(out,out[1:])]),'callers':dict(collections.Counter(x['api'].get('caller') for x in out)),'sizes':dict(collections.Counter(x['bytes'] for x in out))}
print(json.dumps(summary,indent=2));(r/'world-gameplay-summary.json').write_text(json.dumps(summary,indent=2));(r/'world-gameplay-requests.json').write_text(json.dumps(out,indent=2))
