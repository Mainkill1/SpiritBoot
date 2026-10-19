# SPDX-License-Identifier: MIT
"""Offline identities, never an inference of request ownership from nesting alone."""
import argparse
import calendar
from collections import Counter
import datetime
import hashlib
import json
from pathlib import Path
import re
import statistics

FIELDS=set('seq kind host_ns virtual_ns thread api iosb parent child srb request envelope bytes status info value0 value1 flags'.split())
HEX=set('thread iosb parent child srb request envelope status value0 value1'.split())
META=set('version events overflow reentry lost read_fail open_api map_open map_reentry map_lost'.split())
KINDS={1:'begin',2:'return',3:'bind',4:'start',5:'complete',6:'callback',7:'queue_return',8:'fs_bind',9:'map_begin',10:'map_walk',11:'map_end',12:'map_ready'}


def fields(text,expected):
    result={}
    for item in text.split():
        if item.count('=')!=1:raise ValueError('Malformed field')
        key,value=item.split('=')
        if key not in expected or key in result:raise ValueError('Unexpected or duplicate field')
        if not re.fullmatch('[0-9a-fA-F]{8}' if key in HEX else '[0-9]+',value):
            raise ValueError('Invalid field value')
        result[key]=int(value,16 if key in HEX else 10)
    if set(result)!=expected:raise ValueError('Missing fields')
    return result


def parse(text):
    lines=text.splitlines()
    if len(lines)<2 or not lines[0].startswith('identity_meta ') or not lines[-1].startswith('identity_end '):
        raise ValueError('Missing header or complete flush footer')
    meta=fields(lines[0].split(' ',1)[1],META)
    footer=fields(lines[-1].split(' ',1)[1],{'events'})
    if meta['version']!=1:raise ValueError('Unknown observer format')
    if any(meta[k] for k in ['overflow','reentry','lost','read_fail','map_reentry','map_lost']):
        raise ValueError('Observer lost or ambiguous observations')
    events=[]
    for line in lines[1:-1]:
        if not line.startswith('identity_event '):raise ValueError('Unexpected record')
        event=fields(line.split(' ',1)[1],FIELDS)
        if event['seq']!=len(events)+1 or event['kind'] not in KINDS:
            raise ValueError('Sequence gap or invalid kind')
        if event['flags']:raise ValueError('Read failure or identity cross-check failure')
        events.append(event)
    if len(events)!=meta['events'] or footer['events']!=len(events):
        raise ValueError('Header/footer count mismatch')
    active={};maps={}
    for e in events:
        if e['kind']==1:
            if not e['api'] or e['api'] in active:raise ValueError('Invalid active API identity')
            active[e['api']]=(e['thread'],e['iosb'])
        elif e['kind']==2:
            if active.pop(e['api'],None)!=(e['thread'],e['iosb']):
                raise ValueError('Unmatched full-capture API return')
        elif e['kind']==9:
            key=(e['thread'],e['request'])
            if key in maps:raise ValueError('Duplicate mapper entry')
            maps[key]=e['api']
        elif e['kind']==11:
            if maps.pop((e['thread'],e['request']),None)!=e['api']:raise ValueError('Unmatched mapper exit')
    if len(active)!=meta['open_api']:raise ValueError('Header open-API count mismatch')
    if len(maps)!=meta['map_open']:raise ValueError('Header open-mapper count mismatch')
    return meta,events


def bounds(receipts):
    rows=[json.loads(line) for line in receipts.splitlines() if line.strip()]
    def stamp(suffix,key):
        matches=[r for r in rows if str(r.get('Id','')).endswith(suffix) and r.get('Status')=='completed']
        if len(matches)!=1:raise ValueError('Need one completed '+suffix+' receipt')
        value=matches[0][key]
        match=re.fullmatch(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)\.(\d{1,9})(?:Z|\+00:00)',value)
        if not match:raise ValueError('Expected exact fractional UTC receipt time')
        seconds=calendar.timegm(datetime.datetime.strptime(match[1],'%Y-%m-%dT%H:%M:%S').timetuple())
        return seconds*10**9+int(match[2].ljust(9,'0'))
    start,end=stamp('-resume','EndedUtc'),stamp('-pause','StartedUtc')
    if start>=end:raise ValueError('Empty or reversed replay interval')
    return start,end


def analyze(events,start,end,meta=None):
    if start>=end:raise ValueError('Empty or reversed replay interval')
    # Discard all warmup maps: a snapshot restore may rewind guest identities.
    selected=[e for e in events if start<=e['host_ns']<=end]
    if any(a['host_ns']>b['host_ns'] or a['virtual_ns']>b['virtual_ns'] for a,b in zip(selected,selected[1:])):
        raise ValueError('Clock reversal inside replay interval')
    calls={};live_iosb={};children={};srbs={};parents={};parent_iosbs={};partials={};counts=Counter();bindings=[];start_events=[];queue_events=[];maps={};map_rows=[];ready=[]
    def mark(call_id,reason):
        if call_id in calls:calls[call_id]['issues'].add(reason)
    def owner(binding):return binding['owner'] if binding else None
    def relation(binding,current):
        if not binding:return 'unknown'
        if binding['ambiguous']:return 'unknown'
        if binding['owner']==current:return 'own'
        if binding['owner'] is not None:return 'other'
        # An unmatched read may be ordinary background I/O. Distinct IOSB and
        # parent establish another request only when the current call was bound.
        c=calls[current]
        if c['parents'] and binding['iosb'] and binding['parent'] not in c['parents'] and binding['iosb']!=c['iosb']:
            return 'other'
        return 'unknown'
    for e in selected:
        kind=KINDS[e['kind']];api=e['api'];counts[kind]+=1
        if kind=='begin':
            if not api or api in calls or not e['iosb']:raise ValueError('Invalid API generation')
            call={'id':api,'iosb':e['iosb'],'thread':e['thread'],'begin':e,
                  'return':None,'callback':None,'parents':set(),'bindings':[],
                  'starts':Counter(),'queue_returns':Counter(),'issues':set(),'parent_completions':[],'partial_completions':[],'via_partial':0}
            if e['iosb'] in live_iosb:
                mark(live_iosb[e['iosb']],'iosb_reuse_before_callback');call['issues'].add('iosb_reuse_before_callback')
            calls[api]=call;live_iosb[e['iosb']]=api
        elif kind=='map_begin':
            key=(e['thread'],e['request'])
            if key in maps:raise ValueError('Mapper nesting/reuse mismatch')
            maps[key]={'begin':e,'walk':None,'owner':live_iosb.get(e['iosb'])}
        elif kind=='map_walk':
            m=maps.get((e['thread'],e['request']))
            if m is None:counts['walk_without_replay_entry']+=1;continue
            if m['walk'] is not None or e['info']!=0 or e['value0']>e['bytes'] or e['bytes']>8192:
                raise ValueError('Invalid initialized mapper counters')
            m['walk']=e
        elif kind=='map_end':
            m=maps.pop((e['thread'],e['request']),None)
            if m is None:counts['map_exit_without_replay_entry']+=1;continue
            if e['status']>1 or e['value0']>1 or bool(e['value0'])!=(m['walk']is not None):raise ValueError('Invalid mapper result/initialization')
            if e['status'] and (not e['value0'] or e['info']!=e['bytes']):raise ValueError('Successful mapping requires a complete initialized walk')
            if m['walk'] and (e['info']>e['bytes'] or e['bytes']!=m['walk']['bytes'] or e['value1']!=m['walk']['value0']):
                raise ValueError('Invalid final mapper counters')
            map_rows.append({'api':m['owner'],'execution_api':m['begin']['api'],'success':bool(e['status']),
                             'walk_initialized':bool(e['value0']),'steps':e['info']if e['value0']else None,
                             'skip':e['value1']if e['value0']else None,'planned_steps':e['bytes']if e['value0']else None,
                             'inclusive_us':(e['virtual_ns']-m['begin']['virtual_ns'])/1000})
        elif kind=='map_ready':
            if e['value0']>1:raise ValueError('Invalid extent-hit flag')
            ready.append({'api':live_iosb.get(e['iosb']),'parent':e['parent'],'extent_hit':bool(e['value0'])})
        elif kind=='return':
            if api not in calls:counts['return_without_replay_entry']+=1;continue
            c=calls[api]
            if c['return'] is not None or c['iosb']!=e['iosb'] or c['thread']!=e['thread']:
                raise ValueError('Mismatched API return')
            c['return']=e
        elif kind=='fs_bind':
            who=live_iosb.get(e['iosb'])
            if not e['child'] or not e['parent']:raise ValueError('Null filesystem identity')
            ambiguous=e['child'] in partials
            if ambiguous:
                mark(who,'partial_reuse_before_completion')
                mark(partials[e['child']]['owner'],'partial_reuse_before_completion')
                for old_binding in children.values():
                    if old_binding['parent']==e['child']:old_binding['ambiguous']=True
            partials[e['child']]={'owner':who,'root':e['parent'],'iosb':e['iosb'],
                                   'generation':e['seq'],'ambiguous':ambiguous}
            if e['parent'] in parents and parents[e['parent']]!=who:
                mark(who,'root_reuse_before_completion');mark(parents[e['parent']],'root_reuse_before_completion')
            parents[e['parent']]=who;parent_iosbs[e['parent']]=e['iosb']
            if who is not None:calls[who]['parents'].add(e['parent'])
        elif kind=='bind':
            if not e['child'] or not e['parent'] or not e['srb']:raise ValueError('Null dispatch identity')
            who=live_iosb.get(e['iosb'])
            partial=partials.get(e['parent']) if not e['iosb'] else None
            effective_iosb=e['iosb']
            if partial:
                who=partial['owner'];effective_iosb=partial['iosb']
                if who is not None:calls[who]['via_partial']+=1
                if partial['ambiguous']:mark(who,'ambiguous_filesystem_partial')
            b={'generation':e['seq'],'owner':who,'parent':e['parent'],'iosb':effective_iosb,
               'child':e['child'],'srb':e['srb'],'ambiguous':bool(partial and partial['ambiguous'])}
            for old in [children.get(e['child']),srbs.get(e['srb'])]:
                if old:
                    b['ambiguous']=True;old['ambiguous']=True
                    mark(who,'child_or_srb_reuse_before_completion');mark(owner(old),'child_or_srb_reuse_before_completion')
            if e['parent'] in parents and parents[e['parent']]!=who:
                b['ambiguous']=True;mark(who,'parent_reuse_before_completion');mark(parents[e['parent']],'parent_reuse_before_completion')
            children[e['child']]=b;srbs[e['srb']]=b;parents[e['parent']]=who;parent_iosbs[e['parent']]=e['iosb'];bindings.append(b)
            if who is not None:
                calls[who]['parents'].add(e['parent']);calls[who]['bindings'].append(b['generation'])
        elif kind=='start':
            b=children.get(e['child'])
            if b and (b['srb']!=e['srb'] or srbs.get(e['srb']) is not b):
                mark(owner(b),'start_srb_mismatch');b=None
            # Preserve identity at this event. Attribute interval overlap only
            # after all API endpoints are known, including thread switches.
            start_events.append((e,b))
            if api not in calls or calls[api]['return'] is not None:
                counts['start_without_active_api_on_current_thread']+=1
            if b:counts['start_with_dispatch_identity']+=1
            else:counts['start_without_dispatch_identity']+=1
        elif kind=='queue_return':
            b=children.get(e['child'])
            if b and b['srb']!=e['srb']:b=None
            queue_events.append((e,b))
        elif kind=='complete':
            b=children.pop(e['child'],None)
            if b and srbs.get(b['srb']) is b:del srbs[b['srb']]
            partials.pop(e['child'],None)
            if e['child'] in parents:
                who=parents.pop(e['child']);expected_iosb=parent_iosbs.pop(e['child'])
                if who is not None:
                    key='parent_completions' if expected_iosb==calls[who]['iosb'] else 'partial_completions'
                    calls[who][key].append(e['seq'])
                    if e['iosb']!=expected_iosb:mark(who,'parent_iosb_mismatch')
        elif kind=='callback':
            who=live_iosb.pop(e['iosb'],None)
            if who is None:counts['callback_without_replay_entry']+=1
            else:
                c=calls[who];c['callback']=e
                if e['status'] or e['info']!=c['begin']['bytes']:c['issues'].add('callback_status_or_length')
    rows=[]
    for api,c in calls.items():
        if c['return'] is None:counts['open_api_at_phase_end']+=1;continue
        elapsed=c['return']['virtual_ns']-c['begin']['virtual_ns']
        if elapsed<0:raise ValueError('Negative API interval')
        different_thread=0
        for e,b in start_events:
            if c['begin']['seq']<e['seq']<c['return']['seq']:
                r=relation(b,api);c['starts'][r]+=1
                different_thread+=e['thread']!=c['thread']
                if r=='unknown':c['issues'].add('unresolved_start_identity')
        for e,b in queue_events:
            if c['begin']['seq']<e['seq']<c['return']['seq']:
                c['queue_returns'][relation(b,api)+':'+format(e['status'],'08x')]+=1
        own,other,unknown=(c['starts'][k]for k in ['own','other','unknown'])
        category='unresolved'if c['issues']else 'own_and_other'if own and other else 'own_only'if own else 'other_only'if other else 'no_start'
        rows.append({'api':api,'iosb':format(c['iosb'],'08x'),'bytes':c['begin']['bytes'],
                     'api_us':elapsed/1000,'result':format(c['return']['status'],'08x'),
                     'begin_iosb_status':format(c['begin']['status'],'08x'),'begin_iosb_info':c['begin']['info'],
                     'return_iosb_status':format(c['return']['value0'],'08x'),'return_iosb_info':c['return']['info'],
                     'parent_completion_before_return':any(seq<c['return']['seq'] for seq in c['parent_completions']),
                     'partition':category,'own_starts':own,'other_starts':other,'unknown_starts':unknown,
                     'dispatch_generations':c['bindings'],'starts_on_different_thread':different_thread,
                     'queue_returns':dict(c['queue_returns']),
                     'issues':sorted(c['issues']),'callback_seen_by_phase_end':c['callback']is not None,
                     'parent_completion_count':len(c['parent_completions']),
                     'partial_completion_count':len(c['partial_completions']),'dispatches_via_filesystem_partial':c['via_partial']})
    groups={}
    for category in ['own_only','other_only','own_and_other','no_start','unresolved']:
        subset=[r for r in rows if r['partition']==category]
        groups[category]={'calls':len(subset),'median_api_us':statistics.median(r['api_us']for r in subset)if subset else None,
                         'sizes':dict(Counter(r['bytes']for r in subset))}
    return {'host_start_ns':start,'host_end_ns':end,'header':meta,'events_selected':len(selected),
            'events_excluded':len(events)-len(selected),'event_counts':dict(counts),
            'partitions':groups,'reads':rows,'mapper_calls':map_rows,'mapping_ready':ready,'open_mapper_at_phase_end':len(maps),'pending_at_phase_end':{'iosbs':len(live_iosb),'children':len(children),'parents':len(parents),'filesystem_partials':len(partials)},
            'limits':['PataStartIo entry is the hardware-start routine boundary, not proof a device command was successfully issued.',
                      'Generations begin at each observed lower dispatch; mappings from before the replay are deliberately discarded.',
                      'No-start means no observed PataStartIo entry during this API interval, not that this request never starts. Cross-thread starts are included and counted separately.',
                      'Scope timing includes observer, scheduling and interrupt effects; no exclusive CPU attribution or uninstrumented rates.',
                      'Queue-path pending does not prove a request remains queued or exclude cancellation.']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('log',type=Path);parser.add_argument('receipts',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();meta,events=parse(args.log.read_text());start,end=bounds(args.receipts.read_text())
    result=analyze(events,start,end,meta)
    result['sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [args.log,args.receipts]}
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output:args.output.write_text(text)
    else:print(text,end='')

if __name__=='__main__':main()
