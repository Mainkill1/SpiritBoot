#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Revalidate archived generated-burst evidence and emit the paired comparison."""
import json
from pathlib import Path
from analyze import analyze

root = Path(__file__).resolve().parent
runs = {}
for variant in ('complex', 'spirit'):
    observed = analyze((root/f'{variant}-serial1.log').read_text())
    archived = json.loads((root/f'{variant}-summary1.json').read_text())
    if observed != archived:
        raise SystemExit(f'{variant}: recomputed summary differs from archived result')
    runs[variant] = observed
cases = []
for a, b in zip(runs['complex']['cases'], runs['spirit']['cases']):
    keys = ('id', 'target', 'budget_us')
    if any(a[key] != b[key] for key in keys):
        raise SystemExit('case matrix mismatch')
    row = {key:a[key] for key in keys}
    row.update(complex=a, spirit=b,
               spirit_throughput_change_percent=100*(b['operations_per_second']/a['operations_per_second']-1))
    cases.append(row)
print(json.dumps({'status':'synthetic_budget_baseline_not_a_firmware_fix',
                  'frequency':{key:value['frequency'] for key,value in runs.items()},
                  'statistics_queries':{key:value['statistics_queries'] for key,value in runs.items()},
                  'cases':cases}, indent=2))
