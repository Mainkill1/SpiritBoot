import sys,json,collections,statistics
from pathlib import Path
path=Path(sys.argv[1]); active={}; contexts={}; files=collections.defaultdict(list); counts=collections.Counter(); alloc=collections.Counter(); queue=[]; completed=[]; mem=[]; reads={}; api=[]; invalid=[]; awaiting_apc={}; apc=[]
def ms(a,b):return (int(b['host_ns'])-int(a['host_ns']))/1e6
def stats(v):
 if not v:return {'n':0}
 s=sorted(v);return {'n':len(v),'min':s[0],'median':statistics.median(s),'p95':s[min(len(s)-1,int(.95*len(s)))],'max':s[-1]}
for n,line in enumerate(path.open(errors='replace'),1):
 if not line.startswith('forza_io '):continue
 d=dict(x.split('=',1) for x in line.split()[1:] if '=' in x);k=d['kind'];counts[k]+=1
 if int(d['free_pages'])>0:mem.append(int(d['free_pages']))
 if d['returning']=='1':
  if 'Allocate' in k:alloc[k+':'+d['eax']]+=1
  if k=='_XeNtReadFile@32':
   r=reads.pop((d['thread'],d['esp']),None)
   if r:api.append({'issue_ms':ms(r,d),'status':d['eax'],'offset':r['p8'],'bytes':int(r['a7'],16),'free_pages':int(r['free_pages'])})
  continue
 if k=='_XeNtReadFile@32':reads[(d['thread'],d['esp'])]=d
 if k in ('fatx_dispatch','fatx_worker_dispatch'):
  if k=='fatx_dispatch' and not contexts.get(d['irp'],{}).pop('worker_reentry',False):contexts[d['irp']]={'start':d,'name':d['name']}
  if k=='fatx_worker_dispatch' and d['irp'] in contexts:
   c=contexts[d['irp']];c['worker_reentry']=True;q=c.get('queue')
   if q:queue.append({'file':c['name'],'wait_ms':ms(q,d),'free_pages':int(q['free_pages']),'queued':int(q['fatx_queued'])})
 if k=='fatx_queue' and d['irp'] in contexts:contexts[d['irp']]['queue']=d
 if k=='native_submit':
  if d['irp'] in active:invalid.append({'line':n,'reason':'resubmit before completion','irp':d['irp']})
  active[d['irp']]={'submit':d,'file':contexts.get(d['irp'],{}).get('name',''),'context':contexts.get(d['irp'],{})}
 if k=='lower_submit' and d['irp'] in active:
  active[d['irp']].setdefault('lower',d)
 if k=='io_complete' and d['irp'] in active:
  a=active.pop(d['irp']);r={'file':a['file'],'status':d['status'],'bytes':int(d['info']),'native_ms':ms(a['submit'],d),'free_pages':int(a['submit']['free_pages']),'host_ns':a['submit']['host_ns']}
  if a.get('lower'):r['admission_ms']=ms(a['submit'],a['lower']);r['lower_to_complete_ms']=ms(a['lower'],d)
  if a['context']:r['fatx_to_native_ms']=ms(a['context']['start'],a['submit'])
  completed.append(r);files[r['file']].append(r)
 if k=='io_complete':
  contexts.pop(d['irp'],None)
  awaiting_apc[d['irp']]=d
 if k=='io_apc_delivery':
  c=awaiting_apc.pop(d['irp'],None)
  if c:apc.append(ms(c,d))
out={'events':dict(counts),'memory_sample_pages':stats(mem),'completed_native':len(completed),'pending_native':len(active),'statuses':dict(collections.Counter(x['status'] for x in completed)),'allocation_return_values':dict(alloc),'fatx_queue_wait_ms':stats([x['wait_ms'] for x in queue]),'longest_queue_waits':sorted(queue,key=lambda x:x['wait_ms'],reverse=True)[:15],'completion_to_io_apc_ms':stats(apc),'api_issue_ms':stats([x['issue_ms'] for x in api]),'read_return_statuses':dict(collections.Counter(x['status'] for x in api)),'files':{},'integrity_errors':invalid}
for name,rows in sorted(files.items(),key=lambda x:len(x[1]),reverse=True):
 out['files'][name]={'count':len(rows),'bytes':sum(x['bytes'] for x in rows),'status':dict(collections.Counter(x['status'] for x in rows)),**{k:stats([x[k] for x in rows if k in x]) for k in ['native_ms','admission_ms','lower_to_complete_ms','fatx_to_native_ms','free_pages']}}
Path(str(path)+'.analysis.json').write_text(json.dumps(out,indent=2))
Path(str(path)+'.requests.json').write_text(json.dumps(completed))
print(json.dumps({k:v for k,v in out.items() if k not in ['files','allocation_return_values']},indent=2))
print('Largest file workloads:')
for name,rows in list(out['files'].items())[:15]:print(name,rows)
