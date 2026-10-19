# SPDX-License-Identifier: MIT
# Independently authored analysis of existing owned fixture scalar samples.
from pathlib import Path
from collections import defaultdict,Counter
import json,statistics,re
root=Path(__file__).resolve().parent.parent/'forza-complex-cadence-20261017'/'initial-poll'
result={}
for typ in ['baseline','candidate','complex']:
 ops=defaultdict(list);frames={};frequency=None;cases={}
 for line in(root/f'{typ}-serial.log').read_text().splitlines():
  d=dict(re.findall(r'(\w+)=([^\s]+)',line))
  if 'FORZA-PUMP-META 'in line:frequency=int(d['frequency'])
  if 'FORZA-PUMP-BEGIN 'in line:cases[int(d['id'])]=d
  if 'FORZA-PUMP-OP 'in line:ops[(int(d['id']),int(d['frame']))].append({k:int(v,16 if k=='status'else 10)for k,v in d.items()})
  if 'FORZA-PUMP-FRAME 'in line:frames[(int(d['id']),int(d['frame']))]={k:int(v)for k,v in d.items()}
 allrows=[];excluded=0
 for key,group in ops.items():
  frame=frames.get(key)
  if frame is None or len(group)!=frame['issued']:excluded+=len(group);continue
  group.sort(key=lambda r:r['seq'])
  for ordinal,row in enumerate(group,1):
   earlier=[r for k,rs in ops.items()if k[0]==key[0]for r in rs if r['seq']<row['seq']]
   callbacks=sum(frame['initial_return']<r['callback']<row['issue']for r in earlier)
   depth=frame['after_initial']+ordinal-1-callbacks
   assert depth>=0
   allrows.append({'case':key[0],'frame':key[1],'ordinal':ordinal,'bytes':row['bytes'],'api_us':(row['returned']-row['issue'])*1e6/frequency,'after_initial':frame['after_initial'],'callback_unacknowledged_before_issue':depth,'callback_before_return':row['callback']<=row['returned']})
 def stats(rs):
  v=sorted(r['api_us']for r in rs)
  return {'n':len(v),'median_us':statistics.median(v),'mean_us':sum(v)/len(v)}if v else {'n':0}
 out={'sample_scope':'First64 operations/case; only fully sampled frames; excludes partial final frame. Exploratory prefix, not representative of full10secondcase.','excluded_partial_ops':excluded,'cases':{}}
 for case in [1,5]:
  selected=[r for r in allrows if r['case']==case]
  summary={'samples':len(selected),'frames':len(set(r['frame']for r in selected)),'after_initial_distribution':dict(Counter(r['after_initial']for r in selected)),
    'first':stats([r for r in selected if r['ordinal']==1]),'later':stats([r for r in selected if r['ordinal']>1]),
    'first_excluding_frame0':stats([r for r in selected if r['ordinal']==1 and r['frame']>0]),'later_excluding_frame0':stats([r for r in selected if r['ordinal']>1 and r['frame']>0]),
    'by_ordinal':{i:stats([r for r in selected if r['ordinal']==i])for i in sorted(set(r['ordinal']for r in selected))},
    'by_public_unacknowledged_count':{i:stats([r for r in selected if r['callback_unacknowledged_before_issue']==i])for i in sorted(set(r['callback_unacknowledged_before_issue']for r in selected))},
    'by_size_and_first':{str((size,ordinal)):stats([r for r in selected if r['bytes']==size and (r['ordinal']==1)==ordinal])for size in [512,65536]for ordinal in [True,False]}}
  out['cases'][case]=summary
 result[typ]=out
(Path(__file__).resolve().parent/'initial-poll-ordinals.json').write_text(json.dumps(result,indent=2)+'\n')
print('Wrote initial-poll-ordinals.json from archived OP/FRAME prefix samples')
