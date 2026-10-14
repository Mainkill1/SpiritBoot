#!/usr/bin/env python3
"""Strict qualification and descriptive comparison of seven gather-control pairs.

All outputs are descriptive. No outliers or enabled leaves are discarded.
"""
import argparse
import copy
import csv
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
import statistics as st
import tomllib

HERE=Path(__file__).resolve().parent
CONTRACT_SHA='2a9a67fbe89f807aa80a4e3f0d5e21c8cb22ad65e22a19bf93c1ce4446463b07'
REFERENCE_SHA='12ddc6b6871f3a3d6d58b8e564f1ac248f623ce09df8d9478631e99b6bcf2f1a'
BIOS={'full':'c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853',
      'nosg':'1f15b01bd3a7b83990d4e0185f4f0a2ccc02c142e42ebb73d0620be975a96e7f'}
TREES={'full':'3c23ea01cf43c2979c4c3ef247236e03d079f465',
       'nosg':'719705f9b4e6ab0da533ab45b8cc3b713801d4b7'}
FIXTURE='099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33'
EXE='14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d'
REMOVED='patches/roswell/0124-direct-sync-gather-write.patch'
HIGHLIGHTS=['io/storage/flush_hdd_file','io/fileobj/head_fields',
            'io/scatter/concurrent_async_requests_are_independent',
            'mm/vmcontract/noaccess_commit','io/cc-write/small_file_reopen',
            'io/cc-write/subdir_small_reopen','io/scatter/gather_writes_from_each_page']

def require(condition,message):
    if not condition:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def document(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

require(sha(HERE/'frozen_contracts.py')==CONTRACT_SHA,'frozen contracts changed')
require(sha(HERE/'reference.json')==REFERENCE_SHA,'frozen reference changed')
import frozen_contracts as m
REFERENCE=document(HERE/'reference.json')

def parse_api(log):
    ordinary=m.tap(log,639,m.TODOS,m.SKIPS,m.TODOS)
    require(ordinary==[n for n in m.EXPECTED_LEAVES if n not in m.TODOS],
            'ordinary TAP identities/order do not match frozen leaves')
    require(m.one(r'^# tests=(\d+) passed=(\d+) failed=(\d+) skipped=(\d+)$',log)==
            ('639','634','0','5'),'API summary differs')
    require(m.one(r'^== api-regression end (\w+) ==$',log)=='PASS','API terminal differs')
    frequency=int(m.one(r'^# LEAF-META version=1 frequency=(\d+).*$',log))
    require(frequency>0,'invalid API clock')
    rows=re.findall(r'^# LEAF name=(\S+) ticks=(\d+) ok=(\d+) todo=(\d+)$',log,re.M)
    require(len(rows)==634 and len(re.findall(r'^# LEAF(?: |$).*$',log,re.M))==634,
            'missing, extra, or malformed LEAF records')
    require([r[0] for r in rows]==m.EXPECTED_LEAVES,'LEAF identity/order differs')
    for name,ticks,ok,todo in rows:
        require((int(ok),int(todo))==(1,int(name in m.TODOS)),
                'API correctness/TODO disposition differs: '+name)
    return {name:int(ticks)*1e6/frequency for name,ticks,ok,todo in rows}

def seven_stats(nosg,full):
    require(len(nosg)==len(full)==7,'seven complete cost pairs required')
    require(all(math.isfinite(x) and x>=0 for x in [*nosg,*full]),'invalid cost')
    a,b=st.median(nosg),st.median(full)
    deltas=[y-x for x,y in zip(nosg,full)]
    ratios=[y/x if x else None for x,y in zip(nosg,full)]
    result={'pairs':7,'nosg_median_us':a,'full_median_us':b,
            'nosg_mean_us':st.mean(nosg),'full_mean_us':st.mean(full),
            'ratio_full_over_nosg':b/a if a else None,
            'delta_full_minus_nosg_us':b-a,
            'paired_delta_median_us':st.median(deltas),
            'paired_ratio_median':st.median(ratios) if all(x is not None for x in ratios) else None,
            'nosg_min_us':min(nosg),'nosg_max_us':max(nosg),
            'full_min_us':min(full),'full_max_us':max(full),
            'full_faster_pairs':sum(y<x for x,y in zip(nosg,full)),
            'full_slower_pairs':sum(y>x for x,y in zip(nosg,full)),
            'equal_pairs':sum(y==x for x,y in zip(nosg,full)),
            'direction':'full lower observed range' if max(full)<min(nosg) else
                        'full higher observed range' if min(full)>max(nosg) else 'overlapping ranges',
            'nosg_samples_us':list(nosg),'full_samples_us':list(full),
            'paired_deltas_us':deltas,'paired_ratios':ratios}
    for i,(x,y) in enumerate(zip(nosg,full)):
        result[f'nosg_pair{i}_us']=x
        result[f'full_pair{i}_us']=y
    return result

def validate_run_order(runs):
    require(len(runs)==14,'fourteen runs required')
    require({(r['pair'],r['side']) for r in runs}==
            {(i,s) for i in range(7) for s in BIOS},'missing/duplicate/unknown pair member')
    ordered=sorted(runs,key=lambda r:r['started'])
    expected=[(i,s) for i in range(7) for s in
              (('full','nosg') if i%2==0 else ('nosg','full'))]
    require([(r['pair'],r['side']) for r in ordered]==expected,'seven chronological AB/BA pairs required')
    for r in ordered:
        require(r['started']<r['ended'],'invalid run interval')
    for a,b in zip(ordered,ordered[1:]):
        require(a['ended']<=b['started'],'overlapping runs')
    return True

def validate_manifests(full_path,nosg_path):
    manifests={'full':document(full_path),'nosg':document(nosg_path)}
    for side,j in manifests.items():
        require(j['status']=='built' and j['source_tree']==TREES[side] and
                j['flash_sha256']==BIOS[side],'build identity differs: '+side)
        require(j['variant']=='release' and j['memory_mib']==64 and
                j['reserve_upper_ram'] is False and j['rom_kernel'] is True and
                j['metadata_counters'] is False and j['pool_audit'] is False,
                'build profile differs: '+side)
        require(any('-DNXK_POOL_CENSUS=OFF' in c and '-DNXK_POOL_AUDIT=OFF' in c
                    for c in j['commands']),'diagnostics must be off: '+side)
    full,nosg=manifests['full'],manifests['nosg']
    patches=full['patches']
    require(sum(p['path']==REMOVED for p in patches)==1,'control patch is not unique')
    require(nosg['patches']==[p for p in patches if p['path']!=REMOVED],
            'control must remove only 0124 runtime/fixture patch, preserving order/hashes')
    for key in ['schema','base_source_tree','source_revision','source_date_epoch','tool_versions','media_policy']:
        require(full[key]==nosg[key],'build invariant differs: '+key)
    repositories=copy.deepcopy(full['repositories'])
    repositories['roswell']['patches']=[p for p in repositories['roswell']['patches'] if p['path']!=REMOVED]
    require(repositories==nosg['repositories'],'repository/patch identities differ beyond 0124')
    return {'removed_patch':REMOVED,'full_manifest_sha256':sha(full_path),
            'nosg_manifest_sha256':sha(nosg_path),'bios':BIOS,'source_trees':TREES}

def receipt(path,pair,side):
    launch,inputs,result=(document(path/f) for f in ['launch.json','inputs.json','result.json'])
    require(launch['biosSha256'].lower()==BIOS[side] and
            launch['exeSha256'].lower()==EXE and launch['probeSha256'].lower()==FIXTURE and
            isinstance(launch['session'],int) and launch['session']>0,'launch identity/session differs: '+str(path))
    require(inputs['memoryMiB']==64 and result['exited'] is True and result['exitCode']==0,
            'memory profile or exit differs: '+str(path))
    require(sha(path/'launch-xemu.toml')==inputs['configSha256'].lower(),'frozen config hash differs')
    cfg=tomllib.loads((path/'launch-xemu.toml').read_text(encoding='utf-8-sig'))
    require(cfg['sys']['files']['flashrom_path'].lower()==launch['bios'].lower(),'BIOS config path differs')
    for k in ['flashrom_path','eeprom_path','hdd_path','dvd_path']:
        cfg['sys']['files'][k]='<run-file>'
    require(cfg==REFERENCE['config'],'normalized launch config differs from qualified campaign')
    for key,want in REFERENCE['inputs'].items():
        got=inputs[key].lower() if key.endswith('Sha256') else inputs[key]
        require(got==want,'frozen runtime seed differs: '+key)
    require(isinstance(result['elapsedSeconds'],(int,float)) and
            0<result['elapsedSeconds']<300,'invalid run duration')
    ended=dt.datetime.fromisoformat(result['utc'].replace('Z','+00:00'))
    require(ended.tzinfo is not None and ended.utcoffset()==dt.timedelta(0),'UTC receipt required')
    log=(path/'serial.log').read_text()
    values=parse_api(log)
    return {'path':str(path),'pair':pair,'side':side,
            'started':ended-dt.timedelta(seconds=result['elapsedSeconds']),'ended':ended,
            'elapsed_seconds':result['elapsedSeconds'],
            'frequency':int(m.one(r'^# LEAF-META version=1 frequency=(\d+).*$',log)),
            'hashes':{f:sha(path/f) for f in ['launch.json','inputs.json','result.json','launch-xemu.toml','serial.log']},
            'values':values}

def analyze(results,output,full_manifest,nosg_manifest):
    build=validate_manifests(full_manifest,nosg_manifest)
    runs=[]
    for p in sorted(Path(results).glob('probe-gather-control-*')):
        hit=re.fullmatch(r'probe-gather-control-([0-6])-(full|nosg)-\d{8}-\d{6}',p.name)
        require(hit is not None and p.is_dir(),'unknown gather-control run: '+p.name)
        runs.append(receipt(p,int(hit[1]),hit[2]))
    validate_run_order(runs)
    values={(r['pair'],r['side']):r['values'] for r in runs}
    rows=[{'workload':name,'eligible':True,
           **seven_stats([values[i,'nosg'][name] for i in range(7)],
                         [values[i,'full'][name] for i in range(7)])}
          for name in m.EXPECTED_LEAVES]
    totals=seven_stats([sum(values[i,'nosg'][n] for n in m.EXPECTED_LEAVES) for i in range(7)],
                       [sum(values[i,'full'][n] for n in m.EXPECTED_LEAVES) for i in range(7)])
    run_totals=[{'pair':r['pair'],'side':r['side'],'frequency':r['frequency'],
                 'all_634_leaf_sum_us':sum(r['values'][n] for n in m.EXPECTED_LEAVES),
                 'median_of_634_leaf_costs_us':st.median(r['values'].values()),
                 'elapsed_seconds':r['elapsed_seconds']} for r in sorted(runs,key=lambda r:r['started'])]
    receipt_rows=[{k:(v.isoformat() if isinstance(v,dt.datetime) else v)
                   for k,v in r.items() if k!='values'} for r in sorted(runs,key=lambda r:r['started'])]
    report={'validated':True,'runs':14,'pairs':7,'build_control':build,
            'fixture_sha256':FIXTURE,'exe_sha256':EXE,'contract_sha256':CONTRACT_SHA,
            'reference_sha256':REFERENCE_SHA,
            'API':{'planned':639,'enabled':634,'true_passes_per_run':634,
                   'legacy_todos_passed':sorted(m.TODOS),'frozen_skips':m.SKIPS,'cost_leaves':634},
            'totals':totals,'run_totals':run_totals,'rows':rows,'receipts':receipt_rows,
            'highlights':[r for r in rows if r['workload'] in HIGHLIGHTS or r['workload'].startswith('io/scatter/')],
            'direction_counts':{d:sum(r['direction']==d for r in rows) for d in
                ['full lower observed range','full higher observed range','overlapping ranges']},
            'limits':'Seven alternating pairs; descriptive ranges, no outlier rejection. '
                     'Whole-leaf timings include setup, assertions and diagnostics. '
                     'Removing 0124 also changes linked instruction layout; comparison attributes differences '
                     'to the assembled patch, without isolating copy/mapping mechanisms or drive faults. '
                     'The new direct-gather lease is qualified separately by the 72-check SG guest; '
                     'this frozen API fixture does not establish its large-transfer throughput. '
                     'No native peak RAM or gameplay/FPS measured.'}
    out=Path(output);out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    scalar=[k for k,v in rows[0].items() if not isinstance(v,list)]
    table=[{k:r[k] for k in scalar} for r in rows]
    for name,reason in m.SKIPS.items():
        row=dict.fromkeys(scalar,'');row.update(workload=name,eligible=False,exclusion_reason=reason);table.append(row)
    with (out/'full_vs_nosg.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=[*scalar,'exclusion_reason']);w.writeheader();w.writerows(table)
    with (out/'run_totals.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(run_totals[0]));w.writeheader();w.writerows(run_totals)
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('results',type=Path);p.add_argument('output',type=Path)
    p.add_argument('full_manifest',type=Path);p.add_argument('nosg_manifest',type=Path)
    a=p.parse_args()
    j=analyze(a.results,a.output,a.full_manifest,a.nosg_manifest)
    print(json.dumps({k:j[k] for k in ['validated','runs','pairs','API','totals','direction_counts']},indent=2))

if __name__=='__main__':
    main()
