#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Read-only analysis of frozen prefix samples; no new native observations."""
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import statistics
import sys
here=Path(__file__).resolve().parent
archive=here.parent
frozen=archive.parent/'initial-poll'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
identity=json.loads((frozen/'release-identity.json').read_text())
if sha(frozen/'analyze.py')!=identity['sha256']['analyze.py']:raise SystemExit('analyzer identity mismatch')
sys.path.insert(0,str(frozen))
from analyze import analyze
manifest=json.loads((archive/'capture-manifest.json').read_text())
frames_out=[];ops_out=[];cases_out=[]

def stats(rows):
    values=[r['submit_us'] for r in rows]
    return {'count':len(values),'sum_us':sum(values),'mean_us':statistics.mean(values) if values else None,
            'median_us':statistics.median(values) if values else None,'min_us':min(values) if values else None,
            'max_us':max(values) if values else None}

for name in manifest['order']:
    for kind,suffix in [('serial','log'),('summary','json')]:
        if sha(archive/f'{name}-{kind}.{suffix}')!=manifest['runs'][name][f'{kind}_sha256']:raise SystemExit('input changed')
    text=(archive/f'{name}-serial.log').read_text();summary=analyze(text)
    if summary!=json.loads((archive/f'{name}-summary.json').read_text()):raise SystemExit('summary mismatch')
    frequency=summary['frequency'];records={'OP':[],'FRAME':[]}
    for line in text.splitlines():
        match=re.search(r'FORZA-PUMP-(OP|FRAME)\s+(.*)',line)
        if match:
            kind,fields=match.groups()
            records[kind].append({k:int(v,16 if k=='status' else 10) for k,v in re.findall(r'(\w+)=([^\s]+)',fields)})
    for case in summary['cases']:
        base={'run':name,'case':case['id'],'target':case['target'],'budget_us':case['budget_us']}
        frames=sorted((f for f in records['FRAME'] if f['id']==case['id']),key=lambda f:f['frame'])
        ops=sorted((o for o in records['OP'] if o['id']==case['id']),key=lambda o:o['seq'])
        sequence=0;frame_base={};frame_rows=[];op_rows=[]
        for f in frames:
            frame_base[f['frame']]=sequence
            sizes=[65536 if (sequence+n)%2==0 else 512 for n in range(f['issued'])]
            observed=[o for o in ops if o['frame']==f['frame']]
            for o in observed:
                ordinal=o['seq']-sequence
                if not 0<=ordinal<f['issued'] or o['bytes']!=sizes[ordinal]:raise SystemExit('ordinal inference mismatch')
            row={**base,'frame':f['frame'],'first_sequence':sequence,'issued':f['issued'],
                 'first_size':sizes[0] if sizes else 0,'size_order':','.join(map(str,sizes)),
                 'timed_op_count':len(observed),'before':f['before'],'after_initial':f['after_initial'],
                 'after':f['after'],'initial_callbacks':f['initial_callbacks'],'budget_hit':f['budget_hit'],
                 'initial_poll_us':f['initial_ticks']*1e6/frequency,'all_frame_submit_us':f['submit_ticks']*1e6/frequency,
                 'later_polls_us':f['poll_ticks']*1e6/frequency,'pump_us':(f['end']-f['begin'])*1e6/frequency}
            frame_rows.append(row);sequence+=f['issued']
        per_frame_seen={}
        for o in ops:
            ordinal=per_frame_seen.get(o['frame'],0);per_frame_seen[o['frame']]=ordinal+1
            if o['frame'] in frame_base and ordinal!=o['seq']-frame_base[o['frame']]:raise SystemExit('ordinal mismatch')
            row={**base,'seq':o['seq'],'frame':o['frame'],'ordinal':ordinal,'bytes':o['bytes'],'slot':o['slot'],
                 'offset':o['offset'],'status':f"{o['status']:08x}",'submit_us':(o['returned']-o['issue'])*1e6/frequency,
                 'callback_after_return_us':(o['callback']-o['returned'])*1e6/frequency,
                 'return_from_pump_begin_us':(o['returned']-o['burst'])*1e6/frequency,
                 'sampled_frame_after_initial':next((f['after_initial'] for f in frames if f['frame']==o['frame']),None)}
            op_rows.append(row)
        groups=[]
        for size in (65536,512):
            for ordinal in range(8):
                rows=[r for r in op_rows if r['bytes']==size and r['ordinal']==ordinal]
                groups.append({'bytes':size,'ordinal':ordinal,**stats(rows)})
        first_later=[]
        for size in (65536,512):
            for position in ('first','later'):
                rows=[r for r in op_rows if r['bytes']==size and (r['ordinal']==0)==(position=='first')]
                first_later.append({'bytes':size,'position':position,**stats(rows),
                                    'excluding_frame_zero':stats([r for r in rows if r['frame']!=0])})
        full_first={65536:case['frames']-case['zero_issue_frames']-case['pair_split'],512:case['pair_split']}
        for size in (65536,512):
            size_count=next(s['count'] for s in case['sizes'] if s['bytes']==size)
            if not sum(f['first_size']==size for f in frame_rows)<=full_first[size]<=size_count:raise SystemExit('whole-case first-size count bounds')
        cases_out.append({**base,'frequency':frequency,'full_operations':case['operations'],'full_frames':case['frames'],
                          'full_first_size_counts_derived':{str(size):full_first[size] for size in (65536,512)},
                          'full_first_share_of_size_reads':{str(size):full_first[size]/next(s['count'] for s in case['sizes'] if s['bytes']==size) for size in (65536,512)},
                          'full_pair_split':case['pair_split'],'full_zero_issue_frames':case['zero_issue_frames'],
                          'full_sizes':case['sizes'],'full_weighted_mean_us':sum(s['submit_sum'] for s in case['sizes'])*1e6/frequency/case['operations'],
                          'sampled_frames':len(frames),'sampled_frame_issues':sequence,'timed_ops':len(ops),
                          'timed_frame_count':len(per_frame_seen),'last_timed_frame':max(per_frame_seen),
                          'sampled_first_size_counts':{str(size):sum(f['first_size']==size for f in frame_rows) for size in (0,65536,512)},
                          'sampled_sizes':[{'bytes':size,**stats([r for r in op_rows if r['bytes']==size])} for size in (65536,512)],
                          'ordinal_groups':groups,'first_later_groups':first_later})
        frames_out.extend(frame_rows);ops_out.extend(op_rows)
result={'contract':'Observed first64 OP timings and first32 FRAME records per case; sizes beyond OP prefix inferred from alternating sequence and frame issue counts.',
        'limits':['Prefixes are not representative samples of whole cases.','No IOSB-at-return, device-idle or lower queue occupancy observation exists.','FRAME after_initial counts undelivered fixture callbacks, not native queue depth.','No first512 timed operation is guaranteed; absent groups remain null.','Whole-case first512 count equals pair_split under the frozen strictly alternating issue sequence; this is derived, not a new timing measurement.','No explanation of full-case regressions is proven.'],
        'input_serial_sha256':{name:manifest['runs'][name]['serial_sha256'] for name in manifest['order']},'cases':cases_out}
outputs={'analysis.json':json.dumps(result,indent=2)+'\n'}
for filename,rows in [('frames.csv',frames_out),('operations.csv',ops_out)]:
    buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows);outputs[filename]=buf.getvalue()
for filename,text in outputs.items():
    path=here/filename
    if '--write' in sys.argv:path.write_text(text)
    elif not path.exists() or path.read_text()!=text:raise SystemExit(f'{filename}: exact reproduction differs')
print(json.dumps({'cases':len(cases_out),'frames':len(frames_out),'operations':len(ops_out),'exact_outputs':list(outputs)},indent=2))
