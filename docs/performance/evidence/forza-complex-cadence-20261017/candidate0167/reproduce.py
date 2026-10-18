#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Revalidate all owned serial oracles and report every 0167 comparison case."""
import hashlib
import json
from pathlib import Path
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent/'bursts'))
from analyze import analyze

manifest = json.loads((root/'capture-manifest.json').read_text())
bios = {'baseline': 'add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296',
        'candidate': 'f4c48706403c4c0c151e58d6ce5bba0b2748830fc5d3ab1b055757b0e0a80702'}
reference = json.loads((root.parent/'bursts/spirit-request.sanitized.json').read_text())
expected = {f['Path']: f['Sha256'] for f in reference['files']}
runs = {}
paths = {'complex': (root.parent/'bursts', 'complex-serial1.log', 'complex-summary1.json'),
         'baseline1': (root.parent/'bursts', 'spirit-serial1.log', 'spirit-summary1.json')}
for name in ('candidate1', 'baseline2', 'candidate2'):
    paths[name] = (root, f'{name}-serial.log', f'{name}-summary.json')
    req = json.loads((root/f'{name}-request.sanitized.json').read_text())
    want = dict(expected, **{'flash.bin': bios['baseline' if name.startswith('baseline') else 'candidate']})
    if {f['Path']: f['Sha256'] for f in req['files']} != want:
        raise SystemExit(f'{name}: unexpected input hashes')
    if req['job']['Arguments'] != reference['job']['Arguments']:
        raise SystemExit(f'{name}: launch arguments changed')
    identity = manifest['runs'][name]
    if identity['files'] != req['files']:
        raise SystemExit(f'{name}: manifest/request input mismatch')
    if identity['job_id'] != req['id'] or req['id'] != req['job']['Id'] or identity['runner_result'] != 'completed':
        raise SystemExit(f'{name}: inconsistent run identity or unsuccessful execution')
    if name.endswith('2'):
        outcome = json.loads((root/f'{name}-runner-outcome.json').read_text())
        if (outcome['jobId'] != identity['job_id'] or outcome['runId'] != identity['result_id']
                or outcome['state'] != 'tested' or outcome['outcome']['execution'] != 'completed'):
            raise SystemExit(f'{name}: runner execution receipt mismatch')
    for kind in ('serial', 'summary'):
        file = root/f'{name}-{kind}.{"log" if kind == "serial" else "json"}'
        if hashlib.sha256(file.read_bytes()).hexdigest() != identity[f'{kind}_sha256']:
            raise SystemExit(f'{name}: {kind} hash mismatch')
for name, (directory, serial, summary) in paths.items():
    observed = analyze((directory/serial).read_text())
    if observed != json.loads((directory/summary).read_text()):
        raise SystemExit(f'{name}: recomputed summary differs')
    runs[name] = observed
cases = []
for index in range(8):
    values = {name: data['cases'][index] for name, data in runs.items()}
    keys = ('id', 'target', 'budget_us')
    if any(any(v[k] != values['complex'][k] for k in keys) for v in values.values()):
        raise SystemExit('case matrix mismatch')
    row = {k: values['complex'][k] for k in keys}
    row['runs'] = values
    row['candidate_change_percent'] = {
        str(repeat): 100*(values[f'candidate{repeat}']['operations_per_second']/values[f'baseline{repeat}']['operations_per_second']-1)
        for repeat in (1, 2)}
    row['candidate2_vs_complex_percent'] = 100*(values['candidate2']['operations_per_second']/values['complex']['operations_per_second']-1)
    cases.append(row)
print(json.dumps({'status': 'synthetic_fixture_qualification_not_overall_Forza_fix',
                  'frequency': {name: data['frequency'] for name, data in runs.items()},
                  'cases': cases}, indent=2))
