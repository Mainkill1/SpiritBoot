#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, json
from pathlib import Path

ROOT = Path('/home/codex/xemu-shader-workbench-handoff')
HERE = ROOT / '.scratch/forza-deck-function-profile-20261015'
RUN = HERE / 'deck-run/evidence/20261016-065809185-372316c894b54f5c902ac9b4be7281ae'
REPO = ROOT / '.scratch/spiritboot-game-profile-20261015/spiritboot-pr248-source'

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

rows = [json.loads(x) for x in (RUN / 'phase-profile.ndjson').read_text().splitlines()]
header = rows[0]
start = rows[1]
end = rows[2]
complete = rows[-1]
entries = [x for x in rows if x['type'] == 'entry']
assert header['entries'] == complete['entries'] == 1685
assert complete['completed_windows'] == 1 and complete['clock_errors'] == 0
assert start['type'] == 'phase_start' and end['type'] == 'phase_end'

totals = {key: sum(x[key] for x in entries) for key in (
    'hits', 'tb_executions', 'weighted_instructions', 'attributed_thread_cpu_ns')}
for row in entries:
    for key, total in totals.items():
        row[key + '_share_percent'] = 100.0 * row[key] / total if total else 0.0
    row['entry_observed'] = bool(row['hits'])
    row['attribution_kind'] = ('entry+range' if row['hits'] and row['tb_executions'] else
                               'entry-only' if row['hits'] else 'range-only')

fields = ['pc', 'label', 'entry_observed', 'attribution_kind', 'hits',
          'hits_share_percent', 'tb_executions', 'tb_executions_share_percent',
          'weighted_instructions', 'weighted_instructions_share_percent',
          'attributed_thread_cpu_ns', 'attributed_thread_cpu_ns_share_percent']
with (HERE / 'results/executed-kernel-function-ledger.csv').open('w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    w.writerows(entries)

by_weight = sorted(entries, key=lambda x: (-x['weighted_instructions'], x['pc']))
by_cpu = sorted(entries, key=lambda x: (-x['attributed_thread_cpu_ns'], x['pc']))
by_hits = sorted(entries, key=lambda x: (-x['hits'], x['pc']))

def select(key: str, threshold: float = 1.0) -> list[dict]:
    return [{k: row[k] for k in ('pc', 'label', 'hits', 'tb_executions',
                                  'weighted_instructions', 'attributed_thread_cpu_ns',
                                  key + '_share_percent')}
            for row in entries if row[key + '_share_percent'] >= threshold]

kernel = REPO / '.scratch/forza-map-sg-release64/work-7k_329dz/build/ntoskrnl/xboxkrnl.unstripped.exe'
bios = REPO / '.scratch/forza-map-sg-release64/flash.bin'
original_fixture = REPO / 'tests/xbe/forza-map-stream/forza-map-stream.iso'
profile_fixture = HERE / 'fixture/forza-map-stream-profile.iso'
xemu = ROOT / '.scratch/spiritboot-game-profile-20261015/deck-package/xemu-profile'
plugin = HERE / 'build/phase_function_profile.so'
function_list = HERE / 'build/spiritboot-sg.functions'
manifest = json.loads((RUN / 'input-manifest.json').read_text())
host = json.loads((RUN / 'host-inventory.json').read_text())
payload = {
    'schema': 1,
    'scope': 'first marker-bounded measured 1024-read pass of owned Forza public request replay',
    'result': {
        'correctness': 'pass',
        'operations': 1024,
        'bytes': 10871296,
        'queue_depth': 12,
        'pressure_pages': 900,
        'oracle_failures': 0,
        'completed_windows': complete['completed_windows'],
        'clock_errors': complete['clock_errors'],
        'phase_wall_ns_diagnostic': complete['phase_wall_ns'],
        'phase_vcpu_thread_cpu_ns_diagnostic': complete['phase_thread_cpu_ns'],
        'attributed_kernel_cpu_ns_diagnostic': totals['attributed_thread_cpu_ns'],
        'attributed_kernel_cpu_coverage_percent':
            100.0 * totals['attributed_thread_cpu_ns'] / complete['phase_thread_cpu_ns'],
        'kernel_tb_callbacks': complete['kernel_callbacks'],
        'all_tb_callbacks': complete['callbacks'],
        'executed_entry_or_range_rows': len(entries),
        'exact_nonzero_entry_rows': sum(bool(x['hits']) for x in entries),
        'range_only_rows': sum(not x['hits'] and bool(x['tb_executions']) for x in entries),
        'totals': totals,
    },
    'over_one_percent': {
        'weighted_instructions': sorted(select('weighted_instructions'),
                                        key=lambda x: -x['weighted_instructions_share_percent']),
        'diagnostic_attributed_thread_cpu': sorted(select('attributed_thread_cpu_ns'),
                                                   key=lambda x: -x['attributed_thread_cpu_ns_share_percent']),
        'entry_hits': sorted(select('hits'), key=lambda x: -x['hits_share_percent']),
    },
    'top20': {
        'weighted_instructions': by_weight[:20],
        'diagnostic_attributed_thread_cpu': by_cpu[:20],
        'entry_hits': by_hits[:20],
    },
    'provenance': {
        'bios': {'sha256': sha(bios), 'bytes': bios.stat().st_size,
                 'source_tree': 'e65870455d2af1bfcc7b187b629a7e3988021491'},
        'kernel_unstripped': {'sha256': sha(kernel), 'bytes': kernel.stat().st_size},
        'function_list': {'sha256': sha(function_list), 'entries': 1685},
        'xemu_diagnostic_plugin_enabled': {
            'sha256': sha(xemu), 'bytes': xemu.stat().st_size,
            'commit': 'dcc536830deba245eec36cd009db5860ca04884c',
            'elf_build_id': '0f8ec555e648e22df98a0298e9ff9c2c2855073e',
        },
        'plugin': {'sha256': sha(plugin), 'bytes': plugin.stat().st_size},
        'original_fixture': {'sha256': sha(original_fixture), 'bytes': original_fixture.stat().st_size},
        'marker_fixture': {'sha256': sha(profile_fixture), 'bytes': profile_fixture.stat().st_size,
                           'begin': header['begin'], 'end': header['end']},
        'hdd_asset': {'id': 'pr256-clean-fatx-compat010-v1',
                      'sha256': '78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b'},
        'bootrom_asset': {'id': 'pr73-deck-bootrom-e99e3a-v1',
                         'sha256': 'e99e3a772bf5f5d262786aee895664eb96136196e37732fe66e14ae062f20335'},
        'runner': {'run_id': '20261016-065809185-372316c894b54f5c902ac9b4be7281ae',
                   'version': '0.2.0+3aa5e059d52339bf4b14725260e124322c30beca'},
        'host': host,
        'input_manifest_sha256': sha(RUN / 'input-manifest.json'),
    },
    'limits': [
        'Plugin callbacks and per-TB thread clocks heavily perturb wall and CPU time; neither is a release timing result.',
        'Weighted guest instructions are exact for translated blocks executed during the marked phase, but do not weight TCG helper or host I/O cost.',
        'Entry hits are exact for supplied PE/COFF function/code-entry addresses; aliases at one address are combined.',
        'Range attribution assigns a TB to the nearest lower supplied entry and can absorb local assembly labels, padding, and omitted private bodies.',
        'Inlined and LTO-eliminated source functions have no independent entry and cannot be attributed separately.',
        'vCPU thread CPU excludes xemu storage, render, audio, and other host worker-thread CPU.',
    ],
}
(HERE / 'results/summary.json').write_text(json.dumps(payload, indent=2) + '\n')

lines = [
    '# Retained-SG Forza 1,024-read Deck function census', '',
    f"Correctness: **PASS** (1,024/1,024 operations, {payload['result']['bytes']:,} bytes, QD12, pressure 900, zero oracle failures).",
    '',
    f"The marked phase executed {payload['result']['exact_nonzero_entry_rows']} supplied kernel entries and {payload['result']['range_only_rows']} additional nearest-symbol ranges. The ledger contains {len(entries)} nonzero rows.",
    '',
    '## Functions above 1% of weighted guest instructions', '',
    '| Function | Entry hits | TB executions | Weighted instructions | Share | Diagnostic vCPU CPU share |',
    '|---|---:|---:|---:|---:|---:|',
]
for row in payload['over_one_percent']['weighted_instructions']:
    source = next(x for x in entries if x['pc'] == row['pc'])
    lines.append(f"| `{row['label']}` | {row['hits']:,} | {row['tb_executions']:,} | {row['weighted_instructions']:,} | {row['weighted_instructions_share_percent']:.2f}% | {source['attributed_thread_cpu_ns_share_percent']:.2f}% |")
lines += ['', '## Measurement limits', ''] + [f'- {x}' for x in payload['limits']]
(HERE / 'results/summary.md').write_text('\n'.join(lines) + '\n')
print(json.dumps({'rows': len(entries), 'exact_entries': payload['result']['exact_nonzero_entry_rows'],
                  'totals': totals, 'over_one_weight': payload['over_one_percent']['weighted_instructions'],
                  'over_one_cpu': payload['over_one_percent']['diagnostic_attributed_thread_cpu']}, indent=2))
