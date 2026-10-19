#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Revalidate archived owned-fixture evidence and emit the paired comparison."""
import json
from pathlib import Path
from analyze import analyze

root = Path(__file__).resolve().parent
runs = {}
for variant, serial, summary in (
    ('complex', 'complex-serial2.log', 'complex-summary2.json'),
    ('spirit', 'spirit-serial1.log', 'spirit-summary1.json'),
):
    observed = analyze((root / serial).read_text())
    archived = json.loads((root / summary).read_text())
    if observed != archived:
        raise SystemExit(f'{variant}: recomputed summary differs from archived result')
    runs[variant] = observed
cases = []
for complex_case, spirit_case in zip(runs['complex']['cases'], runs['spirit']['cases']):
    keys = ('id', 'target', 'bytes', 'frame_ms')
    if any(complex_case[key] != spirit_case[key] for key in keys):
        raise SystemExit('case matrix mismatch')
    row = {key: complex_case[key] for key in keys}
    row['complex'] = complex_case
    row['spirit'] = spirit_case
    row['spirit_over_complex_submit_time'] = spirit_case['submit_mean_ms']/complex_case['submit_mean_ms']
    row['spirit_throughput_change_percent'] = 100*(spirit_case['operations_per_second']/complex_case['operations_per_second']-1)
    row['complex_mib_per_second'] = complex_case['operations_per_second']*complex_case['bytes']/1048576
    row['spirit_mib_per_second'] = spirit_case['operations_per_second']*spirit_case['bytes']/1048576
    cases.append(row)
print(json.dumps({'status':'baseline_comparison_not_a_firmware_fix',
                  'frequency':{key:value['frequency'] for key,value in runs.items()},
                  'cases':cases}, indent=2))
