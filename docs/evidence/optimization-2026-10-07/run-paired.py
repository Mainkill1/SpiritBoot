#!/usr/bin/env python3
"""Controller: synchronous direct-xemu pairs; retain every attempt and exact order."""
import datetime
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, '/work')
from tools.firmware import run_firmware

root = Path('/work')
output = root / 'artifacts/optimization/paired-v1'
output.mkdir(exist_ok=False)
inputs_file = root / 'artifacts/optimization/runtime-inputs.json'
inputs = json.loads(inputs_file.read_text())
dvd = root / 'artifacts/optimization/guests/final-benchmark.iso'
flashes = {'baseline': root / 'bios/clean-room-xemu/SpiritBoot-release.bin',
           'candidate': root / 'artifacts/optimization/final-release-v1/flash.bin'}
for path, expected in [(dvd, inputs['benchmark_dvd']),
                       (flashes['baseline'], inputs['baseline_release']),
                       (flashes['candidate'], inputs['candidate_release'])]:
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected['sha256']
    assert path.stat().st_size == expected['bytes']

def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')

pairs = {'schema': 1, 'runtime_inputs_sha256': hashlib.sha256(inputs_file.read_bytes()).hexdigest(),
         'controller_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
         'pairs': [], 'execution_log': [], 'asset_path_map': {
             str(dvd): inputs['benchmark_dvd']['path'],
             str(flashes['baseline']): inputs['baseline_release']['path'],
             str(flashes['candidate']): inputs['candidate_release']['path'],
             '/xemu/usr/bin/xemu': inputs['xemu']['path'],
             '/seed.qcow2': inputs['api_seed']['path']}}
try:
    for pair in range(7):
        captures = {v: output / f'pair-{pair + 1:02d}-{v}' for v in flashes}
        pairs['pairs'].append({v: str(p.relative_to(output)) for v,p in captures.items()})
        order = ['baseline', 'candidate'] if pair % 2 == 0 else ['candidate', 'baseline']
        for variant in order:
            record = {'pair': pair, 'variant': variant,
                      'capture': str(captures[variant].relative_to(output)), 'started_utc': utc()}
            result = run_firmware('/xemu/usr/bin/xemu', flashes[variant], '/seed.qcow2',
                                  dvd, captures[variant], timeout=120, tap=True)
            record.update(completed_utc=utc(), status=result['status'])
            pairs['execution_log'].append(record)
            (output / 'pairs.json').write_text(json.dumps(pairs, indent=2) + '\n')
            print(f'pair={pair + 1} variant={variant} status={result["status"]} elapsed={result["elapsed_seconds"]}', flush=True)
            if result['status'] != 'passed':
                raise RuntimeError('A paired capture failed; preserve and investigate the complete attempted dataset.')
finally:
    (output / 'pairs.json').write_text(json.dumps(pairs, indent=2) + '\n')
