# SPDX-License-Identifier: MIT
"""Generation-bound timeline; tracked outstanding lifetimes are not hardware tags."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import analyze_identity as identity


def stats(values):
    values=sorted(values)
    return {'n':len(values),'median':statistics.median(values)if values else None,
            'sum':sum(values),'min':min(values)if values else None,'max':max(values)if values else None}


def timeline(events,start,end):
    validated=identity.analyze(events,start,end)
    events=[e for e in events if start<=e['host_ns']<=end]
    calls={};iosbs={};active={};bindings=[];partials={};roots={};parent_bindings={}
    unmatched=[];ready={};maps={}
    def tracked_started():return [b['generation']for b in active.values()if b['starts']]
    def edge(event):return {'seq':event['seq'],'virtual_ns':event['virtual_ns'],'host_ns':event['host_ns']}
    for e in events:
        k=e['kind']
        if k==1:
            if e['iosb'] in iosbs:raise ValueError('Ambiguous IOSB reuse')
            c={'api':e['api'],'iosb':e['iosb'],'thread':e['thread'],'bytes':e['bytes'],
               'begin':edge(e),'returned':None,'bindings':[],'root_completions':[],
               'entry_tracked_started_uncompleted':tracked_started()}
            calls[e['api']]=c;iosbs[e['iosb']]=e['api']
        elif k==2 and e['api']in calls:calls[e['api']]['returned']=edge(e)
        elif k==8:
            if e['child']in partials:raise ValueError('Ambiguous filesystem partial reuse')
            who=iosbs.get(e['iosb']);partials[e['child']]=(who,e['parent'])
            roots[e['parent']]=who
        elif k==3:
            if e['child']in active:raise ValueError('Ambiguous child generation reuse')
            who=iosbs.get(e['iosb']);root=e['parent']
            if not e['iosb'] and root in partials:who,root=partials[root]
            b={'generation':e['seq'],'owner':who,'parent':e['parent'],'root':root,
               'child':e['child'],'srb':e['srb'],'bind':edge(e),'starts':[],
               'queues':[],'child_completion':None,'parent_completion':None,
               'bind_tracked_started_uncompleted':tracked_started(),
               'via_partial':e['parent']!=root}
            active[e['child']]=b;bindings.append(b)
            parent_bindings.setdefault(e['parent'],[]).append(b)
            roots[root]=who
            if who is not None:calls[who]['bindings'].append(b)
        elif k in (4,7):
            b=active.get(e['child'])
            if not b or b['srb']!=e['srb']:
                unmatched.append({'kind':identity.KINDS[k],'seq':e['seq']});continue
            record=edge(e)
            if k==7:record['status']=format(e['status'],'08x')
            b['starts'if k==4 else 'queues'].append(record)
        elif k==5:
            found=False
            b=active.pop(e['child'],None)
            if b:b['child_completion']=edge(e);found=True
            for b in parent_bindings.pop(e['child'],[]):b['parent_completion']=edge(e);found=True
            if e['child']in roots:
                who=roots.pop(e['child'])
                if who is not None:calls[who]['root_completions'].append(edge(e))
                found=True
            partials.pop(e['child'],None)
            if not found:unmatched.append({'kind':'complete','seq':e['seq']})
        elif k==6:iosbs.pop(e['iosb'],None)
        elif k==12:
            who=iosbs.get(e['iosb'])
            if who is not None:ready.setdefault(who,[]).append(bool(e['value0']))
    for m in validated['mapper_calls']:
        if m['api']is not None:maps.setdefault(m['api'],[]).append(m)
    base_rows={r['api']:r for r in validated['reads']}
    rows=[]
    previous_by_thread={}
    for api,c in calls.items():
        if c['returned'] is None:continue
        r=base_rows[api];bb=c['bindings'];begin=c['begin'];ret=c['returned']
        if not bb:raise ValueError('Complete selected read has no observed lower binding')
        first_bind=min(b['bind']['seq']for b in bb)
        p=previous_by_thread.get(c['thread']);prior='no_previous_selected_read';prior_seq=None
        if p:
            completions=[b['child_completion']for b in p['bindings']]
            if not completions or any(v is None for v in completions):prior='previous_completion_unobserved'
            else:
                prior_seq=max(v['seq']for v in completions)
                prior='before_current_entry'if prior_seq<begin['seq']else 'during_current_before_bind'if prior_seq<first_bind else 'during_current_after_bind'if prior_seq<ret['seq']else'after_current_return'
        previous_by_thread[c['thread']]=c
        def relative(record):
            if record is None:return None
            return {'seq':record['seq'],'from_entry_us':(record['virtual_ns']-begin['virtual_ns'])/1000,
                    'relative_to_return':'before'if record['seq']<ret['seq']else'after'if record['seq']>ret['seq']else'equal'}
        life=[]
        for b in bb:
            life.append({'generation':b['generation'],'via_partial':b['via_partial'],
                         'bind':relative(b['bind']),'starts':[relative(x)for x in b['starts']],
                         'queue_returns':[{**relative(x),'status':x['status']}for x in b['queues']],
                         'child_completion':relative(b['child_completion']),
                         'adapter_parent_completion':relative(b['parent_completion']),
                         'bind_tracked_started_uncompleted':b['bind_tracked_started_uncompleted']})
        queued=any(b['queues']for b in bb)
        own_before=any(s['seq']<ret['seq']for b in bb for s in b['starts'])
        category=('queued_then_start_before_return'if queued else'no_queue_start_before_return')if own_before else('queued_start_after_return'if queued and all(b['starts']for b in bb)else'no_start_unresolved')
        segments=None
        if len(life)==1 and len(life[0]['starts'])==1 and life[0]['starts'][0]['relative_to_return']=='before':
            bind_us=life[0]['bind']['from_entry_us'];start_us=life[0]['starts'][0]['from_entry_us']
            segments={'entry_to_bind_us':bind_us,'bind_to_pata_entry_us':start_us-bind_us,
                      'pata_entry_to_return_us':r['api_us']-start_us}
            if min(segments.values())<0 or abs(sum(segments.values())-r['api_us'])>1e-6:
                raise ValueError('Invalid disjoint interval boundaries')
        row={**r,'submission_segments':segments,'queue_start_partition':category,'entry_tracked_started_uncompleted':c['entry_tracked_started_uncompleted'],
             'previous_selected_read_api':p['api']if p else None,'previous_child_completion':prior,
             'previous_last_child_completion_seq':prior_seq,'extent_ready_flags':ready.get(api,[]),
             'mapping':maps.get(api,[]),'lifecycle':life,'root_completions':[relative(x)for x in c['root_completions']]}
        rows.append(row)
    cohorts={}
    for name in sorted(set(r['queue_start_partition']for r in rows)):
        subset=[r for r in rows if r['queue_start_partition']==name]
        cohorts[name]={'calls':len(subset),'api_us':stats([r['api_us']for r in subset]),
                       'sizes':{size:stats([r['api_us']for r in subset if r['bytes']==size])for size in sorted(set(r['bytes']for r in subset))},
                       'entry_tracked_started_counts':dict(Counter(len(r['entry_tracked_started_uncompleted'])for r in subset)),
                       'before_bind_tracked_started_counts':dict(Counter(len(r['lifecycle'][0]['bind_tracked_started_uncompleted'])for r in subset)),
                       'previous_completion':dict(Counter(r['previous_child_completion']for r in subset)),
                       'extent_hits':sum(r['extent_ready_flags']==[True]for r in subset),
                       'mapper_calls':sum(len(r['mapping'])for r in subset),
                       'disjoint_segments':{key:stats([r['submission_segments'][key]for r in subset if r['submission_segments']])for key in ['entry_to_bind_us','bind_to_pata_entry_us','pata_entry_to_return_us']},
                       'disjoint_segments_by_size':{size:{key:stats([r['submission_segments'][key]for r in subset if r['submission_segments']and r['bytes']==size])for key in ['entry_to_bind_us','bind_to_pata_entry_us','pata_entry_to_return_us']}for size in sorted(set(r['bytes']for r in subset))},
                       'entry_to_first_bind_us':stats([r['lifecycle'][0]['bind']['from_entry_us']for r in subset]),
                       'first_bind_to_return_us':stats([r['api_us']-r['lifecycle'][0]['bind']['from_entry_us']for r in subset]),
                       'return_to_eventual_start_us':stats([x['from_entry_us']-r['api_us']for r in subset for b in r['lifecycle']for x in b['starts']if x['relative_to_return']=='after'])}
    return {'selected_reads':len(rows),'queue_start_cohorts':cohorts,
            'mapping_inclusive_us':stats([m['inclusive_us']for r in rows for m in r['mapping']]),
            'mapping_steps':dict(Counter(m['steps']for r in rows for m in r['mapping'])),
            'mapping_extent_hits':sum(r['extent_ready_flags']==[True]for r in rows),
            'previous_completion_all':dict(Counter(r['previous_child_completion']for r in rows)),
            'entry_tracked_started_counts':dict(Counter(len(r['entry_tracked_started_uncompleted'])for r in rows)),
            'before_bind_tracked_started_counts':dict(Counter(len(r['lifecycle'][0]['bind_tracked_started_uncompleted'])for r in rows)),
            'unmatched_events':unmatched,'open_tracked_lower_at_end':len(active),
            'reads':rows,'limitations':['Counts include only lower dispatch generations observed in this replay. Pre-replay or bypassing lifetimes remain unknown.',
            'Started but not yet at child-completion entry is NOT hardware-tag occupancy: the lower driver can start the next request before completing the previous child.',
            'Previous read means previous completed-API selected read on the same guest thread, not all device traffic.',
            'Mapping and native call times are inclusive instrumented intervals; no exclusive CPU attribution.',
            'IOSB samples are ordinary title values, not controlled sentinels. An unchanged value cannot establish that no write occurred.']}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('log',type=Path);p.add_argument('receipts',type=Path);p.add_argument('--output',type=Path)
    args=p.parse_args();meta,events=identity.parse(args.log.read_text());start,end=identity.bounds(args.receipts.read_text())
    result=timeline(events,start,end);result['header']=meta
    result['sha256']={f.name:hashlib.sha256(f.read_bytes()).hexdigest()for f in [args.log,args.receipts]}
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')

if __name__=='__main__':main()
