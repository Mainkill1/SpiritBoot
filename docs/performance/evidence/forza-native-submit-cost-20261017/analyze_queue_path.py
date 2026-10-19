#!/usr/bin/env python3
"""Reproduce API-scope queue-path partitions; no request identity is inferred."""
from collections import Counter
import json
from pathlib import Path
from statistics import median
import sys

root = Path(__file__).resolve().parent
archive = root.parent / 'forza-budget-attribution-20261017'
sys.path.insert(0, str(archive))
import analyze_owned

report = analyze_owned.run(archive/'spirit-v12b-owned.log',
    archive/'spirit-v12b-receipts.jsonl', archive/'v12b-owned-observer.c.txt',
    archive/'owned-phase-sites.json')
assert json.loads(json.dumps(report)) == json.loads((archive/'spirit-v12b-owned-analysis.json').read_text())
_, rows = analyze_owned.parse_log((archive/'spirit-v12b-owned.log').read_text())
rows = [r for r in rows if report['host_start_ns'] <= r['host_ns'] <= report['host_end_ns']
        and r['handle'] == 0x42c]
assert len(rows) == 373
fields = {'api':'total_ns', 'adapter':'p3_ns', 'pump':'p7_ns',
          'prepare':'p5_ns', 'packet':'p4_ns', 'submit':'p6_ns', 'pata':'p8_ns'}
parts = {}
for pata in (False, True):
    for dpc in (False, True):
        selected = [r for r in rows if bool(r['p8_count']) == pata
                    and bool(r['p1_count']) == dpc]
        parts[f'pata_{int(pata)}_dpc_{int(dpc)}'] = {
            'n':len(selected),
            'median_us':{name:median(r[key] for r in selected)/1000
                         for name,key in fields.items()},
            'length_counts':dict(sorted(Counter(r['bytes'] for r in selected).items())),
            'iosb_info_counts':dict(sorted(Counter(r['info'] for r in selected).items()))}
print(json.dumps({'input_sha256':report['sha256'],
    'host_start_ns':report['host_start_ns'], 'host_end_ns':report['host_end_ns'],
    'handle':'0000042c', 'rows':len(rows),
    'phase_count_histograms':{f'p{i}':dict(sorted(Counter(r[f'p{i}_count'] for r in rows).items()))
                              for i in range(9)},
    'partitions':parts,
    'limitation':'Counts are inclusive API scopes, not child-IRP/request identities; timings are instrumented elapsed durations.'}, indent=2))
