#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate 0169/0168/0169 generated-fixture evidence and native return cost."""
import hashlib
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'initial-poll'))
from analyze import analyze
manifest=json.loads((root/'capture-manifest.json').read_text())
if manifest['order']!=['0169-first','0168-repeat','0169-repeat']:
    raise SystemExit('unexpected trial order')
if manifest['firmware']!={'0168':'2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6',
                          '0169':'c7dcfe9214d422ef0477e10a2ff552e08f6c78db0675085ad6cf88eef44a5527'}:
    raise SystemExit('unexpected firmware hashes')
build=json.loads((root/'build0169.sanitized.json').read_text())
if build['status']!='built' or build['variant']!='release' or build['memory_mib']!=64 or build['flash_sha256']!=manifest['firmware']['0169']:
    raise SystemExit('build receipt mismatch')
if hashlib.sha256((root/'plan.json').read_bytes()).hexdigest()!=manifest['plan_sha256']:
    raise SystemExit('qualification plan mismatch')
for previous,current in [('0169-first','0168-repeat'),('0168-repeat','0169-repeat')]:
    if (manifest['runs'][current]['prior_job']!=manifest['runs'][previous]['job_id']
            or manifest['runs'][current]['prior_finished_utc']!=manifest['runs'][previous]['finished_utc']):
        raise SystemExit('trials were not consecutive in the recorded order')
freeze=json.loads((root.parent/'initial-poll/release-identity.json').read_text())
if hashlib.sha256((root.parent/'initial-poll/analyze.py').read_bytes()).hexdigest()!=freeze['sha256']['analyze.py']:
    raise SystemExit('frozen analyzer changed')
reference=json.loads((root.parent/'initial-poll/candidate-request.sanitized.json').read_text())
runs={}
for name in ('0169-first','0168-repeat','0169-repeat'):
    identity=manifest['runs'][name]
    req=json.loads((root/f'{name}-request.sanitized.json').read_text())
    want={f['Path']:f['Sha256'] for f in reference['files']}
    want['flash.bin']=manifest['firmware']['0168' if name=='0168-repeat' else '0169']
    if {f['Path']:f['Sha256'] for f in req['files']}!=want or req['files']!=identity['files']:
        raise SystemExit(f'{name}: input hash mismatch')
    if req['job']['Arguments']!=reference['job']['Arguments'] or req['job']['SnapshotName'] is not None:
        raise SystemExit(f'{name}: launch contract mismatch')
    receipt=json.loads((root/f'{name}-runner-outcome.json').read_text())
    if (req['id']!=req['job']['Id'] or req['id']!=identity['job_id'] or receipt['jobId']!=req['id']
            or receipt['runId']!=identity['result_id'] or receipt['state']!='tested'
            or receipt['outcome']['execution']!='completed' or identity['runner_result']!='completed'):
        raise SystemExit(f'{name}: run identity/execution mismatch')
    for kind,suffix in [('serial','log'),('summary','json')]:
        if hashlib.sha256((root/f'{name}-{kind}.{suffix}').read_bytes()).hexdigest()!=identity[f'{kind}_sha256']:
            raise SystemExit(f'{name}: {kind} hash mismatch')
    summary=analyze((root/f'{name}-serial.log').read_text())
    if summary!=json.loads((root/f'{name}-summary.json').read_text()):raise SystemExit(f'{name}: summary mismatch')
    runs[name]=summary
rows=[]
for index in range(8):
    values={name:summary['cases'][index] for name,summary in runs.items()};keys=('id','target','budget_us')
    if any(any(v[k]!=values['0168-repeat'][k] for k in keys) for v in values.values()):raise SystemExit('case matrix mismatch')
    row={k:values['0168-repeat'][k] for k in keys};row['runs']=values
    costs={name:sum(size['submit_sum'] for size in case['sizes'])*1e6/runs[name]['frequency']/case['operations'] for name,case in values.items()}
    row['native_return_mean_us']=costs
    row['changes_vs_0168']={name:{
        'native_return_mean_percent':100*(costs[name]/costs['0168-repeat']-1),
        'reads_per_second_percent':100*(case['operations_per_second']/values['0168-repeat']['operations_per_second']-1),
        'submit_mean_65536_percent':100*(case['sizes'][0]['submit_mean_us']/values['0168-repeat']['sizes'][0]['submit_mean_us']-1),
        'submit_mean_512_percent':100*(case['sizes'][1]['submit_mean_us']/values['0168-repeat']['sizes'][1]['submit_mean_us']-1)
    } for name,case in values.items() if name!='0168-repeat'}
    rows.append(row)
print(json.dumps({'status':'repeated_synthetic_native_return_cost_not_Forza_fix',
                  'order':manifest['order'], 'cases':rows},indent=2))
