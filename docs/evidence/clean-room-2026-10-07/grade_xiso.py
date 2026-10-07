"""Grade a direct guest capture; never launches a test runner or changes inputs."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


parser = argparse.ArgumentParser()
parser.add_argument('--capture', type=Path, required=True)
parser.add_argument('--raw-hdd', type=Path)
parser.add_argument('--baseline-root', type=Path, default=Path('/workspace/SpiritBoot'))
args = parser.parse_args()
root = args.baseline_root
capture = args.capture
results_dir = capture / 'results'
results_dir.mkdir(exist_ok=True)
if args.raw_hdd:
    from pyfatx import Fatx
    filesystem = Fatx(str(args.raw_hdd), drive='e')
    try:
        for guest, local in [('results.txt', 'results.txt'),
                             ('resolved-plan-result.json', 'resolved-plan-result.json'),
                             ('xemu_perf_tests_config.json', 'guest-config.json')]:
            (results_dir / local).write_bytes(filesystem.read('/xemu_perf_tests/' + guest))
    finally:
        del filesystem
catalog_bytes = (root / 'artifacts/xiso-suite/catalog.json').read_bytes()
lock = json.loads((root / 'sources/xiso-suite-lock.json').read_text())
assert hashlib.sha256(catalog_bytes).hexdigest() == lock['artifacts']['catalog']['sha256']
catalog = json.loads(catalog_bytes)
expected = {record['id']: (record['revision'], record['kind']) for record in catalog['tests']}
raw_results = (results_dir / 'results.txt').read_bytes()
records = json.loads(raw_results)
ids = Counter(record['id'] for record in records)
duplicates = sorted(key for key, value in ids.items() if value != 1)
missing = sorted(set(expected) - set(ids))
extra = sorted(set(ids) - set(expected))
wrong_contracts = [record['id'] for record in records
                   if (record['revision'], record['kind']) != expected.get(record['id'])]
outcomes = Counter(record['outcome'] for record in records)
applicable_failures = []
non_applicable_diagnostics = []
for record in records:
    metadata = record.get('metadata', {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata)
    failed = metadata.get('oracle_status', 'PASS') != 'PASS' or metadata.get('oracle_failure_count', 0) != 0
    if not failed:
        continue
    entry = {'id': record['id'], 'status': metadata.get('oracle_status'),
             'failure_count': metadata.get('oracle_failure_count')}
    (applicable_failures if metadata.get('oracle_applicable', True)
     else non_applicable_diagnostics).append(entry)
receipt = json.loads((results_dir / 'resolved-plan-result.json').read_bytes())
baseline_receipt = json.loads((root / 'artifacts/xiso-suite/direct-release-results/resolved-plan-result.json').read_bytes())
config_matches = (results_dir / 'guest-config.json').read_bytes() == (root / 'artifacts/xiso-suite/full-guest-config.json').read_bytes()
run = json.loads((capture / 'run.json').read_bytes())
passed = (not duplicates and not missing and not extra and not wrong_contracts
          and outcomes == {'PASS': 149} and not applicable_failures
          and receipt == baseline_receipt and config_matches
          and run['status'] == 'captured' and run['returncode'] == 0)
result = {'schema': 1, 'passed': passed, 'records': len(records),
          'leaves': sum(record['kind'] == 'leaf' for record in records),
          'groups': sum(record['kind'] == 'group' for record in records),
          'record_outcomes': dict(outcomes), 'duplicates': duplicates,
          'missing': missing, 'extra': extra, 'wrong_contracts': wrong_contracts,
          'applicable_oracle_failures': applicable_failures,
          'non_applicable_diagnostics': non_applicable_diagnostics,
          'plan': receipt, 'guest_config_matches': config_matches,
          'exit_code': run['returncode'], 'elapsed_seconds': run['elapsed_seconds'],
          'raw_result_sha256': hashlib.sha256(raw_results).hexdigest(),
          'performance_comparison_qualified': False}
(results_dir / 'verification.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if passed else 1)
