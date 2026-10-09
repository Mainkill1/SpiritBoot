"""Validate paired direct-driver captures before making conservative timing claims."""
import json
import math
from datetime import datetime, timedelta
from fractions import Fraction
from pathlib import Path
import re
from statistics import median

from tools.firmware import grade_tap, sha256

BASELINE = '154276a142c7df727ea46f1a35ee9a896f7369221f10d07f21757a61bc8e6d60'
# Public guest v1 contract, in its declared execution order.
WORKLOADS = {'empty': 1000,
 'pin-1': 1000,
 'pin-16': 500,
 'pin-64': 100,
 'pin-65': 100,
 'pin-256': 32,
 'pin-4096': 4,
 'pin-reject-0': 500,
 'pin-reject-32': 100,
 'pin-reject-64': 100,
 'pin-reject-65': 100,
 'pool-1': 64,
 'pool-16': 16,
 'pool-256': 4,
 'pool-1024': 1,
 'pool-fragmented-fail-4': 16,
 'sysva-1': 32,
 'sysva-16': 8,
 'sysva-1024': 1,
 'sysva-1025': 1,
 'sysva-4096': 1,
 'object-cold-64': 1,
 'object-warm-1': 1000,
 'object-warm-8': 128,
 'object-warm-64': 16,
 'modexp-1-e1-odd': 64,
 'modexp-1-e65537-odd': 32,
 'modexp-2-e3-even': 8,
 'modexp-32-e3-odd': 2,
 'modexp-64-e65537-odd': 1,
 'modexp-512-e1-odd': 1,
 'sha-0': 512,
 'sha-1': 512,
 'sha-63': 256,
 'sha-65': 256,
 'sha-4096': 8,
 'sha-1MiB': 1,
 'des-block': 128,
 'des3-block': 64,
 'des-cbc-4096': 2,
 'des3-cbc-4096': 1}
META = re.compile(r'# PERF-META version=1 clock=(\w+) frequency=(\d+) samples=3')
SAMPLE = re.compile(r'# PERF workload=([\w-]+) sample=(\d+) iterations=(\d+) ticks=(\d+) correct=1 checksum=([0-9a-f]{8})')
SUMMARY = '# PERF-SUMMARY workloads=41 failures=0'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(Path(path).read_text())


def stamp(value):
    require(isinstance(value, str) and value.endswith('Z'), 'expected UTC Z timestamp')
    return datetime.fromisoformat(value[:-1] + '+00:00')


def asset_identity(asset):
    require(isinstance(asset, dict), 'missing asset record')
    digest, size = asset.get('sha256'), asset.get('size', asset.get('bytes'))
    require(isinstance(digest, str) and re.fullmatch('[0-9a-f]{64}', digest), 'invalid asset hash')
    require(type(size) is int and size > 0, 'invalid asset size')
    return {'sha256': digest, 'size': size}


def capture(path, mapping, *, expected_memory_mib=128):
    require(type(expected_memory_mib) is int and expected_memory_mib in (64, 128),
            'unsupported expected memory capacity')
    path = Path(path)
    run_path, serial_path = path / 'run.json', path / 'serial.log'
    run, serial = read_json(run_path), serial_path.read_text()
    require(run.get('schema') == 1 and run.get('status') == 'passed' and run.get('returncode') == 0, f'{path}: failed driver')
    require(type(run.get('memory_mib')) is int and run.get('memory_mib') == expected_memory_mib and run.get('boot_mode') == 'open-direct' and run.get('expect_tap') is True and run.get('snapshot') is True, f'{path}: runtime configuration mismatch')
    tap = grade_tap(serial)
    require(tap == run.get('tap') and tap['passed'] and tap['plan'] == 42 and tap['ok'] == 42 and tap['ran'] == 42 and tap['failed'] == tap['todo'] == tap['skipped'] == 0 and not tap['errors'], f'{path}: unclean TAP')
    lines = serial.splitlines()
    require(lines.count('== kernel-performance begin ==') == 1 and lines.count('== kernel-performance end PASS ==') == 1 and lines[-1] == '== kernel-performance end PASS ==', f'{path}: missing terminal PASS')
    perf = [line for line in lines if 'PERF' in line]
    require(len(perf) >= 2 and META.fullmatch(perf[0]) and perf[-1] == SUMMARY, f'{path}: metadata/summary mismatch')
    meta = META.fullmatch(perf[0]); frequency = int(meta[2])
    require(meta[1] == 'KeQueryPerformanceCounter' and 0 < frequency <= 2**64-1, 'invalid clock/frequency')
    workloads = {name: [] for name in WORKLOADS}
    expected = [(name, sample) for name in WORKLOADS for sample in range(1 if name == 'object-cold-64' else 3)]
    actual = []
    for line in perf[1:-1]:
        match = SAMPLE.fullmatch(line)
        require(match is not None, f'{path}: malformed or incorrect PERF sample')
        name, sample, iterations, ticks, checksum = match.groups()
        sample, iterations, ticks = int(sample), int(iterations), int(ticks)
        require(name in WORKLOADS and iterations == WORKLOADS[name] and 0 <= ticks <= 2**64-1, f'{path}: invalid workload/iterations/ticks')
        actual.append((name, sample))
        workloads[name].append({'sample': sample, 'iterations': iterations, 'ticks': ticks, 'checksum': checksum, 'ticks_per_iteration': ticks / iterations, 'correct': 1})
    require(actual == expected, f'{path}: duplicate/missing/out-of-order samples or workloads')
    tap_names = [re.fullmatch(r'ok (\d+) - (.+)', line) for line in lines if re.match(r'^ok\b', line)]
    require(all(tap_names) and [m[2] for m in tap_names] == ['public-known-answers'] + list(WORKLOADS), f'{path}: TAP workloads mismatch')
    for name, samples in workloads.items():
        require(len({s['checksum'] for s in samples}) == 1, f'{path}: checksum differs within workload {name}')
    assets, verified = {}, []
    for name in ('xemu', 'hdd', 'dvd', 'flash'):
        record = run.get('assets', {}).get(name)
        assets[name] = asset_identity(record)
        require(isinstance(record.get('path'), str), 'asset path missing')
        # Only explicit paths/mappings are used; never infer container mounts.
        local = Path(mapping.get(record['path'], record['path']))
        if local.is_file():
            require(local.stat().st_size == assets[name]['size'] and sha256(local) == assets[name]['sha256'], f'{path}: local {name} bytes mismatch')
            verified.append({'asset': name, 'path': str(local)})
    elapsed = run.get('elapsed_seconds')
    require(type(elapsed) in (int, float) and math.isfinite(elapsed) and elapsed > 0, 'invalid elapsed duration')
    return {'path': str(path), 'memory_mib': run['memory_mib'], 'run_sha256': sha256(run_path), 'serial_sha256': sha256(serial_path), 'started_utc': run['started_utc'], 'elapsed_seconds': elapsed, 'clock': meta[1], 'frequency': frequency, 'workloads': workloads, 'assets': assets, 'asset_records':run['assets'], 'locally_verified_assets': verified}


def display_numbers(value):
    """Round exact rationals only after all timing decisions are complete."""
    if isinstance(value, Fraction):
        return float(value)
    if isinstance(value, dict):
        return {key: display_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [display_numbers(item) for item in value]
    return value


def rational_record(value):
    return {'numerator': value.numerator, 'denominator': value.denominator}


def analyze(pairs_path, runtime_path, candidate_build_path=None, baseline_hash=BASELINE, candidate_hash=None):
    pairs_path = Path(pairs_path).resolve()
    dataset, runtime = read_json(pairs_path), read_json(runtime_path)
    release = runtime['candidate_release']
    build = read_json(candidate_build_path) if candidate_build_path else {'status':'built', 'variant':'release', 'flash_size':asset_identity(release)['size'], 'flash_sha256':release['sha256'], 'source_tree':release.get('source_tree')}
    pairs, log = dataset.get('pairs'), dataset.get('execution_log')
    require(isinstance(pairs, list) and len(pairs) >= 7, 'at least seven pairs required')
    require(isinstance(log, list) and len(log) == 2 * len(pairs), 'precise controller execution_log required')
    require(baseline_hash == BASELINE, 'baseline must be the validated release')
    require(build.get('status') == 'built' and build.get('variant') == 'release' and build.get('flash_size') == 262144, 'invalid candidate build output')
    require(build.get('source_tree') == 'f7adb302a762ed1945cc07d9c2ff428c643ba959', 'unapproved candidate source tree')
    candidate_hash = candidate_hash or build.get('flash_sha256')
    require(candidate_hash != baseline_hash and candidate_hash == build.get('flash_sha256'), 'candidate must match build and differ from baseline')
    require(asset_identity(release) == {'sha256':candidate_hash, 'size':262144} and release.get('source_tree') == build['source_tree'], 'runtime candidate mismatch')
    identities = {name: asset_identity(runtime[key]) for name, key in [('xemu', 'xemu'), ('hdd', 'api_seed'), ('dvd', 'benchmark_dvd')]}
    require(asset_identity(runtime['baseline_release']) == {'sha256': baseline_hash, 'size': 262144}, 'runtime baseline mismatch')
    mapping = dataset.get('asset_path_map', {})
    require(isinstance(mapping, dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in mapping.items()), 'invalid explicit asset mapping')
    def resolve(value):
        require(isinstance(value, str), 'capture path must be text')
        p = Path(value)
        return p.resolve() if p.is_absolute() else (pairs_path.parent / p).resolve()
    captures, ordered = [], []
    for i, pair in enumerate(pairs):
        require(isinstance(pair, dict) and set(pair) == {'baseline', 'candidate'}, 'invalid pair')
        loaded = {}
        for variant in ('baseline', 'candidate'):
            p = resolve(pair[variant]); require(str(p) not in ordered, 'capture reused across pairs')
            ordered.append(str(p)); c = capture(p, mapping)
            require(all(c['assets'][name] == identity for name, identity in identities.items()), 'runtime input asset mismatch')
            require(c['assets']['flash'] == {'sha256': baseline_hash if variant == 'baseline' else candidate_hash, 'size':262144}, 'flash identity mismatch')
            loaded[variant] = c
        captures.append(loaded)
    reference = captures[0]['baseline']
    for pair in captures:
        for c in pair.values():
            require((c['clock'],c['frequency']) == (reference['clock'],reference['frequency']), 'clock/frequency mismatch')
            require(all([s['checksum'] for s in c['workloads'][name]] == [s['checksum'] for s in reference['workloads'][name]] for name in WORKLOADS), 'checksum mismatch across captures')
    previous_end = None
    for position, entry in enumerate(log):
        pair_index = position // 2
        variants = ('baseline','candidate') if pair_index % 2 == 0 else ('candidate','baseline')
        variant = variants[position % 2]
        require(entry.get('pair') == pair_index and entry.get('variant') == variant and resolve(entry.get('capture')) == Path(captures[pair_index][variant]['path']), 'nonalternating controller execution order')
        start, end = stamp(entry['started_utc']), stamp(entry['completed_utc'])
        require('.' in entry['started_utc'] and '.' in entry['completed_utc'] and end > start and (previous_end is None or start >= previous_end), 'imprecise/overlapping controller timestamps')
        c = captures[pair_index][variant]; coarse = stamp(c['started_utc'])
        require(start - timedelta(seconds=1) <= coarse <= end and coarse + timedelta(seconds=1) >= start, 'driver start outside controller bounds')
        require(c['elapsed_seconds'] <= (end-start).total_seconds() + 0.01, 'driver duration exceeds controller interval')
        previous_end = end
    results = {}
    n = len(pairs); minimum_consistent = (6*n + 6)//7
    for name in WORKLOADS:
        values, variations = {}, []
        for variant in ('baseline', 'candidate'):
            # The capture's ticks_per_iteration is presentation only. Rebuild
            # exact normalized samples from retained uint64 ticks and iterations.
            normalized = [[Fraction(s['ticks'], s['iterations'])
                           for s in p[variant]['workloads'][name]] for p in captures]
            trials = [median(samples) for samples in normalized]
            raw = [sample for samples in normalized for sample in samples]
            values[variant] = {'trial_medians': trials, 'min': min(trials), 'max': max(trials), 'median': median(trials), 'raw_normalized_min':min(raw), 'raw_normalized_max':max(raw)}
            variations.extend([max(trials)-min(trials), max(raw)-min(raw)])
        b, c = values['baseline'], values['candidate']
        differences = [x-y for x,y in zip(b['trial_medians'],c['trial_medians'])]
        delta, variation = b['median']-c['median'], max(variations)
        improvement = delta > 0 and delta > variation and sum(d>0 for d in differences) >= minimum_consistent
        regression = delta < 0 and -delta > variation and sum(d<0 for d in differences) >= minimum_consistent
        percentages = [100*(y-x)/x if x else None for x,y in zip(b['trial_medians'],c['trial_medians'])]
        exact_decision = {
            'baseline_median': rational_record(b['median']),
            'candidate_median': rational_record(c['median']),
            'median_difference': rational_record(delta),
            'maximum_observed_variant_range': rational_record(variation),
            'paired_differences': [rational_record(d) for d in differences],
        }
        results[name] = display_numbers({**values,'paired_differences':differences,'paired_percentage_changes':percentages,'median_percentage_change':median(percentages) if all(p is not None for p in percentages) else None,'median_difference':delta,'maximum_observed_variant_range':variation,'improving_pairs':sum(d>0 for d in differences),'classification':'timing improvement' if improvement else 'timing regression' if regression else 'timing inconclusive', 'exact_decision': exact_decision})
    return {'schema':1,'pair_count':n,'clock':reference['clock'],'frequency':reference['frequency'],'overhead_subtracted':False,'decision_arithmetic':'exact rational; numeric display fields rounded to float','provenance':{'dataset':{'path':str(pairs_path),'sha256':sha256(pairs_path)},'runtime_inputs':{'path':str(runtime_path),'sha256':sha256(runtime_path),'records':runtime},'candidate_build':{'path':str(candidate_build_path),'sha256':sha256(candidate_build_path),'record':build} if candidate_build_path else None,'analyzer_sha256':sha256(__file__)},'asset_path_map':mapping,'execution_log':log,'captures':captures,'workloads':results}


def markdown(report):
    rows = ['| Workload | Baseline median | Candidate median | Paired change | Classification |','|---|---:|---:|---:|---|']
    for name, result in report['workloads'].items():
        change = result['median_percentage_change']
        rendered_change = f'{change:.2f}%' if change is not None else 'undefined'
        rows.append(f"| {name} | {result['baseline']['median']:.3f} | {result['candidate']['median']:.3f} | {rendered_change} | {result['classification']} |")
    return f"{report['pair_count']} alternating pairs; ticks per iteration. Negative percentage means less time. All raw samples and empty-loop overhead retained; no overhead subtraction.\n\n" + '\n'.join(rows) + '\n'
