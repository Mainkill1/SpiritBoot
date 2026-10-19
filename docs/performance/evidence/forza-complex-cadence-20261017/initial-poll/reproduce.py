#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Revalidate the frozen initial-poll experiment and compare all eight cases."""
import hashlib
import json
from pathlib import Path
from analyze import analyze
root=Path(__file__).resolve().parent
manifest=json.loads((root/'capture-manifest.json').read_text())
for filename in ('analyze.py','test_analyze.py'):
    if hashlib.sha256((root/filename).read_bytes()).hexdigest()!=manifest['fixture']['sha256'][filename]:
        raise SystemExit('frozen analyzer identity mismatch: '+filename)
bios={'baseline':'add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296',
      'candidate':'2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6',
      'complex':'1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f'}
configs={'baseline':'10ea387472f831c3eb2451f9e5d1b01a27b7da929edc2d259879e7b24bdbca26',
         'candidate':'10ea387472f831c3eb2451f9e5d1b01a27b7da929edc2d259879e7b24bdbca26',
         'complex':'5acc868d9242720c28402e33606064b79bc73072d4f2f0047ffbad1899b30a39'}
runs={}
for name in ('baseline','candidate','complex'):
    identity=manifest['runs'][name]
    req=json.loads((root/f'{name}-request.sanitized.json').read_text())
    want={'fixture.iso':'8d94b0c6fa4699de29959e0bdc5ddd63b6b518ea7c65fcf22cf4da9e1f9b4630',
          'flash.bin':bios[name], 'xemu.toml':configs[name],
          'native-launch.exe':'95ed9b3668bddfe70e76755cd6f8b931511069771871966d8c710ba9daed297c',
          'xemu.exe':'5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564'}
    if {f['Path']:f['Sha256'] for f in req['files']}!=want or req['files']!=identity['files']:
        raise SystemExit(f'{name}: input hashes mismatch')
    args=['-config_path','{packageDir}/xemu.toml','-m','64','-device','lpc47m157','-serial','file:{resultDir}/native-serial.log','-d','guest_errors','-D','{resultDir}/qemu.log']
    if req['job']['Arguments']!=args:raise SystemExit(f'{name}: launch arguments mismatch')
    receipt=json.loads((root/f'{name}-runner-outcome.json').read_text())
    if (req['id']!=req['job']['Id'] or req['id']!=identity['job_id'] or receipt['jobId']!=req['id']
            or receipt['runId']!=identity['result_id'] or receipt['state']!='tested'
            or receipt['outcome']['execution']!='completed' or identity['runner_result']!='completed'):
        raise SystemExit(f'{name}: execution/identity mismatch')
    for kind,suffix in [('serial','log'),('summary','json')]:
        if hashlib.sha256((root/f'{name}-{kind}.{suffix}').read_bytes()).hexdigest()!=identity[f'{kind}_sha256']:
            raise SystemExit(f'{name}: {kind} hash mismatch')
    runs[name]=analyze((root/f'{name}-serial.log').read_text())
    if runs[name]!=json.loads((root/f'{name}-summary.json').read_text()):raise SystemExit(f'{name}: summary mismatch')
rows=[]
for index in range(8):
    values={name:summary['cases'][index] for name,summary in runs.items()};keys=('id','target','budget_us')
    if any(any(v[k]!=values['baseline'][k] for k in keys) for v in values.values()):raise SystemExit('case matrix mismatch')
    row={k:values['baseline'][k] for k in keys};row['runs']=values
    row['candidate_change_percent']={name:100*(values['candidate']['operations_per_second']/v['operations_per_second']-1) for name,v in values.items() if name!='candidate'}
    rows.append(row)
print(json.dumps({'status':'initial_poll_synthetic_fixture_not_Forza_fix','cases':rows},indent=2))
