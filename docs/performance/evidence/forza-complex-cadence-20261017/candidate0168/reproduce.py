#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate the candidate0168 frozen-fixture observation and all references."""
import hashlib
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root.parent/'bursts'))
from analyze import analyze
manifest=json.loads((root/'capture-manifest.json').read_text())
for name,key in [('serial.log','serial_sha256'),('summary.json','summary_sha256'),('request.sanitized.json','request_sha256')]:
    if hashlib.sha256((root/name).read_bytes()).hexdigest()!=manifest[key]:raise SystemExit('hash mismatch: '+name)
req=json.loads((root/'request.sanitized.json').read_text())
reference=json.loads((root.parent/'candidate0167/candidate2-request.sanitized.json').read_text())
want={f['Path']:f['Sha256'] for f in reference['files']}
want['flash.bin']='2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6'
if {f['Path']:f['Sha256'] for f in req['files']}!=want or req['files']!=manifest['files']:raise SystemExit('input hashes mismatch')
if req['job']['Arguments']!=reference['job']['Arguments']:raise SystemExit('launch argument mismatch')
receipt=json.loads((root/'runner-outcome.json').read_text())
if (req['id']!=req['job']['Id'] or req['id']!=manifest['job_id'] or receipt['jobId']!=req['id']
        or receipt['runId']!=manifest['result_id'] or receipt['state']!='tested'
        or receipt['outcome']['execution']!='completed' or manifest['runner_result']!='completed'):raise SystemExit('run identity/execution mismatch')
runs={}
for name,directory,serial,summary in [
    ('baseline2',root.parent/'candidate0167','baseline2-serial.log','baseline2-summary.json'),
    ('candidate0167',root.parent/'candidate0167','candidate2-serial.log','candidate2-summary.json'),
    ('candidate0168',root,'serial.log','summary.json'),
    ('complex',root.parent/'bursts','complex-serial1.log','complex-summary1.json')]:
    runs[name]=analyze((directory/serial).read_text())
    if runs[name]!=json.loads((directory/summary).read_text()):raise SystemExit('summary mismatch: '+name)
rows=[]
for index in range(8):
    values={name:s['cases'][index] for name,s in runs.items()};keys=('id','target','budget_us')
    if any(any(v[k]!=values['baseline2'][k] for k in keys) for v in values.values()):raise SystemExit('case matrix mismatch')
    row={k:values['baseline2'][k] for k in keys};row['runs']=values
    row['candidate0168_change_percent']={name:100*(values['candidate0168']['operations_per_second']/v['operations_per_second']-1) for name,v in values.items() if name!='candidate0168'}
    rows.append(row)
print(json.dumps({'status':'single_synthetic_fixture_observation_not_Forza_fix','cases':rows},indent=2))
