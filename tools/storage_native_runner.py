#!/usr/bin/env python3
"""Read native public-API fixture evidence without supplying missing measurements.

The runner HTTP client remains scripts/runner_tests.py. This adapter parses the
owned serial protocol, retains its hash and binds native observations to the
exact frozen qualification plan. The full performance-recorder bridge remains
unfinished. It never fabricates firmware-internal counters.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _unique_fields(words) -> dict:
    fields = {}
    for word in words:
        if '=' not in word:
            continue
        key, value = word.split('=', 1)
        if not key or key in fields:
            raise ValueError('duplicate or empty protocol field: ' + key)
        fields[key] = value
    return fields


def parse_serial(serial: str) -> dict:
    meta, summaries, operations, end = None, {}, {}, None
    global_issues = []
    for line in serial.splitlines():
        if line.strip().startswith('not ok '):
            global_issues.append('TAP failure: ' + line.strip())
        marker = line.find('STORAGE-PERF-')
        if marker < 0:
            continue
        words = line[marker:].strip().split()
        tag = words.pop(0)
        fields = _unique_fields(words)
        if tag == 'STORAGE-PERF-ERROR':
            global_issues.append('fixture fatal error: ' + ' '.join(words))
            continue
        if end is not None:
            raise ValueError('protocol record after END: ' + tag)
        if tag == 'STORAGE-PERF-META':
            if meta is not None:
                raise ValueError('duplicate metadata')
            meta = fields
        elif tag == 'STORAGE-PERF-OP':
            if meta is None:
                raise ValueError('operation before counter metadata')
            identity, index = fields['id'], int(fields['index'])
            case_ops = operations.setdefault(identity, {})
            if index in case_ops:
                raise ValueError('duplicate operation index')
            if identity in summaries:
                raise ValueError('operation after its case summary')
            case_ops[index] = fields
        elif tag == 'STORAGE-PERF-CASE':
            if meta is None:
                raise ValueError('case before counter metadata')
            if fields['id'] in summaries:
                raise ValueError('duplicate case summary')
            summaries[fields['id']] = fields
        elif tag == 'STORAGE-PERF-END':
            if end is not None:
                raise ValueError('duplicate end record')
            end = fields
    if not meta or meta.get('version') != '1' or meta.get('counter') != 'rdtsc':
        raise ValueError('missing or unsupported counter metadata')
    frequency = int(meta['frequency'])
    if frequency <= 0:
        raise ValueError('invalid clock frequency')
    cases = {}
    for identity, summary in summaries.items():
        count = int(summary['operations'])
        case_ops = operations.get(identity, {})
        ordered = [case_ops[index] for index in sorted(case_ops)]
        issues = list(global_issues)
        if set(case_ops) != set(range(count)):
            issues.append('missing operation evidence')
        if any(int(op['status'], 16) != 0 or int(op['io_status'], 16) != 0 or int(op['ticks']) <= 0 for op in ordered):
            issues.append('failed status/IOSB or timing')
        actual_bytes = sum(int(op['information']) for op in ordered
                           if int(op['status'], 16) == 0 and int(op['io_status'], 16) == 0)
        if actual_bytes != int(summary['bytes']):
            issues.append('byte count mismatch')
        if summary.get('cache') not in ('warm', 'cold-ish'):
            issues.append('missing/truncated cache policy')
        if int(summary['failures']):
            issues.append('fixture assertions failed')
        completed = sum(int(op['status'], 16) == 0 and int(op['io_status'], 16) == 0 for op in ordered)
        cases[identity] = {
            'status': 'error' if issues else 'ok', 'error': '; '.join(issues) or None,
            'operations_completed': completed, 'bytes_completed': actual_bytes,
            'assertions_executed': int(summary['assertions']), 'assertions_failed': int(summary['failures']),
            'elapsed_ms': int(summary['ticks']) * 1000 / frequency,
            'latencies_ms': [int(op['ticks']) * 1000 / frequency for op in ordered],
            'operation_records': ordered,
            'timing_scope': 'caller-issue-to-consumer-ready',
            'flush_api_calls_completed': int(summary.get('flush_calls', 0)),
            # NtFlushBuffersFile success is not observation of ATA cache-sync.
            'flushes_completed': int(summary['device_flushes']) if 'device_flushes' in summary else None,
            'reopen_readback_reported': summary.get('persistence') == '1',
            'reopen_readback_verified': True if (summary.get('persistence') == '1'
                and meta.get('fixture_generation') == '2' and not issues) else None,
            # Closing/reopening does not qualify reset or device persistence.
            'durability_verified': None,
            'counters': {'file_read_calls': int(summary.get('read_calls', len(ordered))),
                         **({'file_write_calls': int(summary['write_calls'])} if 'write_calls' in summary else {}),
                         'apc_callbacks': sum(int(op.get('apcs', 0)) for op in ordered)},
            'native': {'queue_depth_observed': int(summary['qd_actual']),
                       'available_pages_observed': int(summary['available_pages']),
                       **({'available_pages_before': int(summary['pages_before'])} if 'pages_before' in summary else {}),
                       **({'pressure_target_pages': int(summary['pressure_target'])} if 'pressure_target' in summary else {}),
                       'cache_label': summary['cache'], 'clock_frequency': frequency,
                       'clock_overhead_ticks': int(meta['overhead_ticks']),
                       'firmware_internal_counters_available': False,
                       'device_cache_sync_observed': False},
        }
    complete = bool(end and int(end.get('cases', -1)) == len(cases)
                    and set(operations) == set(summaries) and int(end.get('failures', -1)) == 0
                    and not global_issues)
    if not complete:
        for observed in cases.values():
            observed['reopen_readback_verified'] = None
    return {'schema_version': 1, 'complete': complete, 'metadata': meta, 'cases': cases,
            'global_issues': global_issues,
            'serial_sha256': hashlib.sha256(serial.encode()).hexdigest()}


def parse_queries(serial: str) -> dict:
    """Preserve public syscall output, never infer an internal driver's IOSB."""
    observations, chunks, styles, end = {}, {}, set(), None
    global_issues, auxiliary = [], []
    for line in serial.splitlines():
        if line.strip().startswith('not ok '):
            global_issues.append('TAP failure: ' + line.strip())
        marker = line.find('STORAGE-')
        if marker < 0:
            continue
        words = line[marker:].strip().split()
        tag = words.pop(0)
        fields = _unique_fields(words)
        if tag == 'STORAGE-PERF-ERROR':
            global_issues.append('fixture fatal error: ' + ' '.join(words))
            continue
        if end is not None:
            raise ValueError('query protocol record after END: ' + tag)
        if tag in ('STORAGE-QUERY', 'STORAGE-QUERY-DATA', 'STORAGE-PARTITION-STYLE'):
            key = (fields['path'], fields.get('control', 'geometry-ex'), int(fields['length']))
            if tag == 'STORAGE-QUERY':
                if key in observations:
                    raise ValueError('duplicate query observation')
                observations[key] = {
                    'path': key[0], 'control': key[1], 'output_length': key[2],
                    'code': int(fields['code'], 16), 'status': int(fields['status'], 16),
                    'caller_iosb_status': int(fields['iosb'], 16),
                    'caller_information': int(fields['information']),
                    'caller_iosb_poison_preserved': fields['iosb'] == '5a5a5a5a'
                        and fields['information'] == '1515870810',
                    'internal_driver_information': None,
                }
                chunks[key] = {}
            elif key not in observations:
                raise ValueError('query detail without observation')
            elif tag == 'STORAGE-QUERY-DATA':
                offset = int(fields['offset'])
                if offset in chunks[key]:
                    raise ValueError('duplicate query output bytes')
                data = bytes.fromhex(fields['hex'])
                if not data or offset < 0 or offset + len(data) > key[2]:
                    raise ValueError('invalid query output bytes extent')
                chunks[key][offset] = data
            else:
                if key in styles:
                    raise ValueError('duplicate query partition style')
                styles.add(key)
                observations[key].update(partition_record_size=int(fields['record_size']),
                                         partition_style=int(fields['style']))
        elif tag == 'STORAGE-QUERY-END':
            if end is not None:
                raise ValueError('duplicate query end')
            end = fields
        else:
            auxiliary.append({'tag': tag, 'fields': fields})
    for key, row in observations.items():
        output = bytearray()
        for offset in sorted(chunks[key]):
            if offset != len(output):
                raise ValueError('missing or overlapping query output bytes')
            output.extend(chunks[key][offset])
        if len(output) != row['output_length']:
            raise ValueError('missing query output bytes')
        row['output_hex'] = output.hex()
        row['initialization'] = {'output_byte': 165, 'caller_iosb_byte': 90}
    return {'schema_version': 1,
            'complete': bool(end and int(end['controls']) == len(observations) and not global_issues),
            'observations': list(observations.values()),
            'global_issues': global_issues, 'auxiliary_observations': auxiliary,
            'no_disc_observed': bool(end and end.get('no_disc_observed') == '1'),
            'serial_sha256': hashlib.sha256(serial.encode()).hexdigest()}


def validate_seed_lineage(manifest: dict, host: dict, request_mode: str) -> None:
    """Direct copies hash the seed; prepared XISO disks carry original lineage."""
    if request_mode not in ('prepared_xiso', 'direct_copy'):
        raise ValueError('unsupported frozen seed request mode')
    disks = [row for row in manifest.get('RuntimeFiles', [])
             if row.get('Destination') == 'hdd.qcow2']
    if (len(disks) != 1 or disks[0].get('DiskAssetId') != host['hdd_seed_id']
            or disks[0].get('Source') != 'disk-asset:' + host['hdd_seed_id']):
        raise ValueError('frozen seed asset/source binding differs')
    disk = disks[0]
    key = 'SeedSha256' if request_mode == 'prepared_xiso' else 'Sha256'
    if (disk.get(key) != host['hdd_seed_sha256']
            or (request_mode == 'direct_copy' and 'SeedSha256' in disk)):
        raise ValueError('frozen seed lineage differs for declared request mode')


def validate_query_matrix(parsed: dict, expected_matrix: list[dict]) -> None:
    """Require the exact frozen public path/control/code/length set and bytes."""
    def key(row):
        return (row['path'], row['control'], row['code'], row['output_length'])
    expected = [key(row) for row in expected_matrix]
    actual = [key(row) for row in parsed['observations']]
    if (not parsed['complete'] or parsed.get('global_issues')
            or len(set(expected)) != len(expected) or len(set(actual)) != len(actual)
            or set(actual) != set(expected)):
        raise ValueError('public query matrix differs or incomplete')
    for row in parsed['observations']:
        data = bytes.fromhex(row['output_hex'])
        if len(data) != row['output_length']:
            raise ValueError('public query matrix output extent differs')
        needs_style = row['control'] == 'geometry-ex' and row['status'] == 0 and len(data) >= 40
        has_style = 'partition_record_size' in row or 'partition_style' in row
        if needs_style:
            if (row.get('partition_record_size') != int.from_bytes(data[32:36], 'little')
                    or row.get('partition_style') != int.from_bytes(data[36:40], 'little')):
                raise ValueError('public query partition style missing or differs from actual bytes')
        elif has_style:
            raise ValueError('public query partition style outside successful complete geometry record')


def validate_owned_exit(cleanup: dict) -> None:
    if (cleanup.get('state') != 'complete' or cleanup.get('targetStopped') is not True
            or cleanup.get('evidenceFinalized') is not True):
        raise ValueError('owned target exit/finalized evidence unconfirmed')


def validate_successful_execution(result: dict) -> None:
    if (result.get('status') != 'completed'
            or result.get('assessment', {}).get('Execution') != 'completed'
            or result.get('exitCode') != 0):
        raise ValueError('failed runner result remains failed')


def derive_clock_observation(guest: dict, wall: dict) -> dict:
    """QPC calibrates QPC; host receipt estimates an RDTSC rate, not duration."""
    frequency, qpc, rdtsc = int(guest['qpc_hz']), int(guest['qpc_ticks']), int(guest['rdtsc_ticks'])
    nanoseconds = int(wall['host_wall_ns_estimate'])
    if frequency <= 0 or qpc <= 0 or rdtsc <= 0 or nanoseconds < 0:
        raise ValueError('invalid clock counter/receiver observation')
    seconds = nanoseconds / 1e9
    return {'qpc_elapsed_seconds': qpc / frequency,
            'qpc_over_host_ratio': qpc / frequency / seconds if seconds else None,
            'rdtsc_ticks_per_host_second_estimate': rdtsc / seconds if seconds else None,
            'rdtsc_rate_origin': 'receiver_interval_estimate; backend delivery unbounded',
            'clock_qualification': 'INCONCLUSIVE'}


def derive_causal_rate(guest_begin, guest_end, host_begin_ns, host_end_ns) -> dict:
    """Exact conditional rate bounds; arithmetic cannot prove the causal link."""
    from fractions import Fraction
    brackets = [guest_begin, guest_end, host_begin_ns, host_end_ns]
    if any(len(pair) != 2 or any(type(value) is not int or value < 0 for value in pair)
           or pair[1] < pair[0] for pair in brackets):
        raise ValueError('invalid or rolled-back counter/host bracket')
    dmin, dmax = guest_end[0]-guest_begin[1], guest_end[1]-guest_begin[0]
    tmin, tmax = host_end_ns[0]-host_begin_ns[1], host_end_ns[1]-host_begin_ns[0]
    if dmin < 0 or dmax < dmin or tmin <= 0 or tmax < tmin:
        raise ValueError('counter rollback or overlapping host brackets: INCONCLUSIVE')
    lower, upper = Fraction(dmin*10**9, tmax), Fraction(dmax*10**9, tmin)
    def rational(value):
        return {'numerator':value.numerator, 'denominator':value.denominator}
    return {'counter_delta_bounds':[dmin,dmax], 'host_delta_ns_bounds':[tmin,tmax],
            'rate_lower':rational(lower), 'rate_upper':rational(upper),
            'relative_rate_interval_width':rational((upper-lower)/lower) if lower else None,
            'causal_proof_status':'not_established_by_arithmetic',
            'normative_clock_qualified':False, 'performance_acceptance_eligible':False}


def parse_causal_clock(serial: str, schedule: list) -> dict:
    """Strict separately versioned protocol; each marker includes its newline."""
    import re
    records = []
    for line in serial.splitlines(keepends=True):
        if line.strip().startswith('not ok ') or 'STORAGE-PERF-ERROR' in line:
            raise ValueError('causal clock fixture failure retained')
        if 'STORAGE-CAUSAL-' not in line:
            continue
        if not line.endswith('\n') or not re.fullmatch(r'(?:# )?STORAGE-CAUSAL-[^\r\n]+\r?\n', line):
            raise ValueError('partial or foreign causal protocol framing')
        words = line.removeprefix('# ').split()
        if any('=' not in word for word in words[1:]):
            raise ValueError('unframed causal protocol fields')
        records.append((words[0], _unique_fields(words[1:])))
    at = 0
    def take(kind, fields):
        nonlocal at
        if at >= len(records) or records[at][0] != 'STORAGE-CAUSAL-'+kind:
            raise ValueError('missing, duplicate or reordered causal record: '+kind)
        value = records[at][1]; at += 1
        if set(value) != set(fields):
            raise ValueError('causal record fields differ: '+kind)
        return value
    def number(value):
        if not re.fullmatch(r'[0-9]+', value):
            raise ValueError('invalid nonnegative causal counter value')
        return int(value)
    count = len(schedule)
    ready = take('READY', ('fixture_generation','diagnostic_revision','samples','markers',
                           'purpose','deadline_counter','qpc_hz'))
    expected_ready = {'fixture_generation':'2','diagnostic_revision':'3','samples':str(count),
                      'markers':str(count*2),'purpose':'causal_counter_brackets','deadline_counter':'qpc',
                      'qpc_hz':ready['qpc_hz']}
    frequency = number(ready['qpc_hz'])
    if ready != expected_ready or frequency <= 0 or not count:
        raise ValueError('causal diagnostic metadata differs')
    if take('ARM', ('samples',)) != {'samples':str(count)}:
        raise ValueError('causal guest runtime-state anchor differs')
    samples = []; previous = {'qpc':None,'rdtsc':None}
    for index, declared in enumerate(schedule):
        for edge in ('begin','end'):
            marker = take('MARKER', ('index','sample','edge'))
            expected = {'index':str(index*2+(edge=='end')),'sample':str(index),'edge':edge}
            if marker != expected:
                raise ValueError('nonunique or reordered causal marker')
        sample = {'index':index,'qpc_hz':frequency}
        for edge in ('begin','end'):
            sample[edge] = {}
            for counter in ('qpc','rdtsc'):
                bound = take('BOUND', ('marker','counter','before','after'))
                if bound['marker'] != str(index*2+(edge=='end')) or bound['counter'] != counter:
                    raise ValueError('causal counter/marker binding differs')
                pair = [number(bound['before']),number(bound['after'])]
                if pair[1] < pair[0] or (previous[counter] is not None and pair[0] < previous[counter]):
                    raise ValueError('causal counter rollback')
                previous[counter] = pair[1]; sample[edge][counter] = pair
        actual = take('SAMPLE', ('index','requested_us','busy'))
        if actual != {'index':str(index),'requested_us':str(declared['requested_us']),'busy':str(declared['busy'])}:
            raise ValueError('causal diagnostic schedule differs')
        sample.update(requested_us=declared['requested_us'],busy=declared['busy'])
        if sample['busy'] and sample['end']['qpc'][0]-sample['begin']['qpc'][1] < frequency*sample['requested_us']//10**6:
            raise ValueError('causal busy QPC deadline shorter than frozen schedule')
        samples.append(sample)
    ending = take('END', ('samples','markers','storage_operations'))
    if ending != {'samples':str(count),'markers':str(count*2),'storage_operations':'0'} or at != len(records):
        raise ValueError('causal terminal framing/count differs or records follow END')
    return {'complete':True,'metadata':ready,'samples':samples,'storage_operations':0,
            'normative_clock_qualified':False,'performance_acceptance_eligible':False}


def validate_lifetime_timeout(serial: str, result: dict, cleanup: dict,
                              attempt: dict, *, windows_receipts: dict | None = None) -> None:
    """Qualify the declared failure path, never any arbitrary failed process."""
    validate_owned_exit(cleanup)
    holds = []
    for line in serial.splitlines():
        words = line[line.find('STORAGE-'):].split() if 'STORAGE-' in line else []
        if words and words[0] == 'STORAGE-LIFETIME-HOLD':
            holds.append(_unique_fields(words[1:]))
        if line.strip().startswith('not ok ') or (words and words[0] == 'STORAGE-PERF-ERROR'):
            raise ValueError('fixture failed before declared lifetime timeout')
    if (len(holds) != 1 or holds[0] != {'fixture_generation':'2', 'data_writes':'0',
                                     'expected_completion':'owned_timeout'}):
        raise ValueError('declared lifetime HOLD missing, duplicated or differs')
    expected = attempt['expected_lifetime_outcome']
    if (result.get('status') != expected['status']
            or result.get('assessment', {}).get('Execution') != expected['execution']):
        raise ValueError('actual lifetime timeout outcome differs')
    if expected['kind'] == 'runner_timeout':
        if result.get('detail') != f"Exceeded {expected['timeout_seconds']} unpaused seconds.":
            raise ValueError('actual runner timeout deadline differs')
    elif expected['kind'] == 'owned_server_deadline':
        if (result.get('exitCode') != expected['exit_code'] or windows_receipts is None
                or expected['server_error'] not in windows_receipts.get('server_stderr', '')):
            raise ValueError('actual owned server timeout deadline evidence missing')
        validate_windows_exit(windows_receipts, deadline=True)
    else:
        raise ValueError('unsupported frozen lifetime timeout kind')


def infer_integrity(serial: str, expected: dict, manifest: dict, *,
                    fixture_sha256: str, seed_sha256: str) -> dict:
    """Deterministic implication from the trusted fixture's complete equality checks.

    Low-level equality implication used by synthetic behavior tests. Native
    callers use infer_integrity_for_attempt, which supplies every trusted value
    from an exact frozen plan and verifies its parser/source/input bindings.
    """
    import re
    if fixture_sha256 in {
        '02c8b038eab6e216cc5957203b3aa485d14e59128e0b005d8091a46fe55a2515',
        'de8c3c022536e724ad1c599be7c6b0c258e0d983c321028118f736de4bd3512c',
    }:
        raise ValueError('V1 fixture integrity is unqualified: reused output buffers can mask no-fill/partial-fill success')
    for digest in (expected.get('expected_sha256'), fixture_sha256, seed_sha256):
        if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
            raise ValueError('integrity inference needs complete frozen hashes')
    fixtures = [item for item in manifest.get('Inputs', []) if item.get('Path') == 'storage-perf.iso']
    if (len(fixtures) != 1 or fixtures[0].get('Verified') is not True
            or fixtures[0].get('Sha256') != fixture_sha256
            or fixtures[0].get('ExpectedSha256') != fixture_sha256):
        raise ValueError('actual fixture differs from trusted frozen fixture')
    seeds = [item for item in manifest.get('RuntimeFiles', []) if item.get('Destination') == 'hdd.qcow2']
    if (len(seeds) != 1 or not seeds[0].get('DiskAssetId')
            or seeds[0].get('SeedSha256') != seed_sha256):
        raise ValueError('actual seed differs from trusted frozen seed')
    parsed = parse_serial(serial)
    if parsed['metadata'].get('fixture_generation') != '2':
        raise ValueError('integrity inference requires the corrected pinned fixture generation')
    if not parsed['complete'] or set(parsed['cases']) != {expected['id']}:
        raise ValueError('incomplete or unmatched selected-case evidence')
    observed = parsed['cases'][expected['id']]
    if (observed['status'] != 'ok' or observed['assertions_failed'] != 0
            or observed['operations_completed'] != expected['operations']
            or observed['bytes_completed'] != expected['bytes_completed_expected']
            or observed['assertions_executed'] != expected['assertions_expected']
            or len(observed['latencies_ms']) != expected['operations']
            or any(value > observed['elapsed_ms'] for value in observed['latencies_ms'])):
        raise ValueError('partial or failed exact-byte comparison evidence')
    return {'integrity_sha256': expected['expected_sha256'],
            'integrity_evidence': 'complete_exact_byte_comparison',
            'integrity_sha256_origin': 'host_inferred_from_verified_equality',
            'integrity_fixture_sha256': fixture_sha256,
            'integrity_seed_sha256': seed_sha256,
            'integrity_comparisons_completed': observed['operations_completed']}


def validate_frozen_attempt(manifest: dict, *, plan_path: Path,
                            plan_sha256: str, attempt_id: str) -> tuple[dict, dict]:
    """Bind every qualification kind to its pinned parser, request and inputs."""
    plan_path = Path(plan_path)
    if sha256(plan_path) != plan_sha256:
        raise ValueError('frozen plan hash differs')
    plan = json.loads(plan_path.read_text())
    if plan.get('schema_version') != 1 or plan.get('purpose') != 'native_fixture_qualification':
        raise ValueError('unsupported frozen native plan')
    parser_hash = sha256(Path(__file__))
    if plan.get('parser_sha256') != parser_hash:
        raise ValueError('actual parser differs from frozen plan')
    source_pin = plan['source_manifest']
    source_path = (plan_path.parent / source_pin['path']).resolve()
    if sha256(source_path) != source_pin['sha256']:
        raise ValueError('frozen fixture source manifest differs')
    source = json.loads(source_path.read_text())
    for entry in source['files']:
        relative = Path(entry['path'])
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('invalid frozen source path')
        path = source_path.parent / relative
        if path.stat().st_size != entry['bytes'] or sha256(path) != entry['sha256']:
            raise ValueError('frozen source/artifact bytes differ: ' + entry['path'])
    attempts = [row for row in plan['attempts'] if row['id'] == attempt_id]
    if len(attempts) != 1 or manifest.get('JobId') != attempt_id:
        raise ValueError('native attempt binding differs')
    attempt = attempts[0]
    if attempt['kind'] == 'native_integrity' and attempt['fixture_sha256'] not in {entry['sha256'] for entry in source['files']
                                        if entry['path'].endswith('.iso')}:
        raise ValueError('fixture is absent from trusted source/artifact freeze')
    for path, expected_hash in attempt['expected_inputs'].items():
        actual = [row for row in manifest.get('Inputs', []) if row['Path'] == path]
        if (len(actual) != 1 or actual[0].get('Verified') is not True
                or actual[0].get('Sha256') != expected_hash
                or actual[0].get('ExpectedSha256') != expected_hash):
            raise ValueError('frozen input binding differs: ' + path)
    host = plan['hosts'][attempt['host']]
    relative = Path(attempt['request_path'])
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('invalid frozen request path')
    request_path = plan_path.parent / relative
    if sha256(request_path) != attempt['request_sha256']:
        raise ValueError('frozen request hash differs')
    request = json.loads(request_path.read_text())
    if request.get('id') != attempt_id or request.get('job', {}).get('id') != attempt_id:
        raise ValueError('frozen request identity differs')
    declared = request.get('files', [])
    if (len(declared) != len(attempt['expected_inputs'])
            or {row['Path']:row['Sha256'] for row in declared} != attempt['expected_inputs']):
        raise ValueError('frozen request input pins differ')
    state = request['job']['runtimeState']
    mode = 'prepared_xiso' if state.get('xiso') is not None else 'direct_copy'
    if mode != attempt['seed_request_mode']:
        raise ValueError('frozen seed mode differs from exact request')
    seeds = [row for row in state['diskAssets'] if row.get('destination') == 'hdd.qcow2']
    if (len(seeds) != 1 or seeds[0].get('assetId') != host['hdd_seed_id']
            or seeds[0].get('expectedSha256') != host['hdd_seed_sha256']):
        raise ValueError('frozen request seed asset binding differs')
    validate_seed_lineage(manifest, host, mode)
    return plan, attempt


def infer_integrity_for_attempt(serial: str, manifest: dict, *, plan_path: Path,
                                plan_sha256: str, attempt_id: str) -> dict:
    """Infer only from the exact frozen request, fixture, parser and operation set."""
    plan, attempt = validate_frozen_attempt(manifest, plan_path=plan_path,
                                           plan_sha256=plan_sha256, attempt_id=attempt_id)
    if attempt['kind'] != 'native_integrity':
        raise ValueError('this qualification attempt cannot infer integrity')
    host, source_pin = plan['hosts'][attempt['host']], plan['source_manifest']
    parser_hash = sha256(Path(__file__))
    parsed = parse_serial(serial)
    if any(parsed['metadata'].get(key) != value for key, value in attempt['expected_metadata'].items()):
        raise ValueError('frozen fixture metadata differs')
    expected = attempt['expected_case']
    if not parsed['complete'] or set(parsed['cases']) != {expected['id']}:
        raise ValueError('frozen selected case differs or incomplete')
    observed = parsed['cases'][expected['id']]
    if (observed['native']['queue_depth_observed'] != attempt['expected_qd']
            or observed['native']['cache_label'] != attempt['expected_cache']):
        raise ValueError('frozen queue/cache policy differs')
    if attempt.get('pressure_target_pages') is not None:
        if (observed['native'].get('pressure_target_pages') != attempt['pressure_target_pages']
                or observed['native'].get('available_pages_before') != attempt['pressure_target_pages']):
            raise ValueError('frozen memory pressure differs')
    sizes = attempt['expected_operation_bytes']
    if len(sizes) != expected['operations']:
        raise ValueError('frozen operation schedule incomplete')
    for fields in observed['operation_records']:
        index = int(fields['index'])
        if (fields['id'] != expected['id'] or index < 0 or index >= len(sizes)
                or int(fields['information']) != sizes[index]
                or int(fields.get('apcs', -1)) != attempt['expected_apcs_per_operation']):
            raise ValueError('frozen per-operation size/APC schedule differs')
    value = infer_integrity(serial, expected, manifest, fixture_sha256=attempt['fixture_sha256'],
                            seed_sha256=host['hdd_seed_sha256'])
    value.update(integrity_plan_sha256=plan_sha256, integrity_parser_sha256=parser_hash,
                 integrity_source_manifest_sha256=source_pin['sha256'],
                 integrity_attempt_id=attempt_id, integrity_qualification_scope='fixture_byte_fill_only',
                 acceptance_eligible=False)
    return value


def validate_windows_exit(receipts: dict, *, deadline: bool = False) -> dict:
    """Require the live pipe and exact retained owned lifetime identities."""
    proof = parse_pipe_proof(receipts['server'], receipts['client'], receipts['launch'])
    if not proof['graphical_guest_launched']:
        raise ValueError('owned Windows child launch unconfirmed')
    def fields(key):
        return _unique_fields(line for line in receipts[key].splitlines() if '=' in line)
    server, client, launch = fields('server'), fields('client'), fields('launch')
    sl, cl, job = fields('server_lifetime'), fields('client_lifetime'), fields('job_lifetime')
    if (sl.get('version') != '2' or cl.get('version') != '2' or job.get('version') != '2'
            or sl.get('server_pid') != server['server_pid']
            or cl.get('server_pid') != server['server_pid']
            or sl.get('child_pid') != launch['xemu_pid']
            or cl.get('client_pid') != client.get('client_pid')
            or job.get('client_pid') != client.get('client_pid')
            or sl.get('child_started') != 'True' or cl.get('server_started') != 'True'
            or sl.get('owned_child_exit_confirmed') != 'True'
            or cl.get('owned_server_exit_confirmed') != 'True'):
        raise ValueError('owned Windows server/child exit or lifetime identity differs')
    for key, expected in {'client_suspended_before_assignment':'1', 'assigned_to_owned_job':'1',
                          'client_resumed':'1', 'client_wait_result':'0',
                          'client_deadline_ms':'170000', 'kill_on_job_close':'1',
                          'job_terminate_succeeded':'1', 'job_query_succeeded':'1',
                          'active_processes_after_cleanup':'0', 'owned_descendants_cleared':'1'}.items():
        if job.get(key) != expected:
            raise ValueError('owned Windows job lifetime differs: ' + key)
    if deadline and (sl.get('owned_child_kill_requested') != 'True'
                     or job.get('client_exit_status') != '1'):
        raise ValueError('owned Windows internal deadline cleanup missing')
    if any('cleanup_error' in key for record in (sl, cl, job) for key in record):
        raise ValueError('owned Windows lifetime cleanup failed')
    return proof


def parse_pipe_proof(server_text: str, client_text: str, launch_text: str | None = None) -> dict:
    def fields(raw):
        return _unique_fields(line for line in raw.splitlines() if '=' in line)
    server, client = fields(server_text), fields(client_text)
    for record in (server, client):
        if (int(record.get('session', 0)) <= 0 or record.get('window_station') != 'WinSta0'
                or record.get('desktop') != 'Default'
                or record.get('identity', '').rsplit('\\', 1)[-1].casefold() != 'codex'):
            raise ValueError('pipe is outside the approved live Codex desktop')
    for key in ('identity', 'session', 'server_pid', 'pipe_name', 'window_station', 'desktop', 'operation'):
        if server.get(key) != client.get(key):
            raise ValueError('pipe client/server identity mismatch: ' + key)
    if (client.get('handshake_verified') != 'True' or server.get('launch_transport') != 'named-pipe'
            or not server.get('pipe_name', '').startswith('pr248-owned-')
            or server.get('operation') not in ('PROVE', 'RUN')):
        raise ValueError('missing verified owned pipe handshake')
    launch = fields(launch_text) if launch_text is not None else None
    if launch is not None:
        if (server['operation'] != 'RUN' or int(launch.get('xemu_pid', 0)) <= 0
                or launch.get('xemu_session') != server['session']
                or launch.get('userInteractive') != 'True'
                or launch.get('launch_transport') != 'named-pipe'
                or any(launch.get(key) != server[key] for key in
                       ('identity', 'session', 'server_pid', 'pipe_name', 'window_station', 'desktop'))):
            raise ValueError('missing or mismatched actual graphical child receipt')
    return {'bridge_verified': True, 'graphical_guest_launched': launch is not None,
            'guest_launch_requested': server['operation'] == 'RUN',
            'server': server, 'client': client, 'child': launch}


def validate_stage_request(request: dict) -> None:
    identity = request.get('id', '')
    job = request.get('job', {})
    if not identity.startswith('pr248-native-') or job.get('id') != identity:
        raise ValueError('stage is restricted to an owned pr248-native job identity')
    state = job.get('runtimeState', {})
    isolation = state.get('isolation', {})
    if not state.get('enabled') or not isolation.get('requirePrivateGuestState'):
        raise ValueError('native capture requires private HDD and EEPROM state')
    if not state.get('files') or not state.get('diskAssets'):
        raise ValueError('native capture requires declared private guest seeds')
    if job.get('plan'):
        raise ValueError('this recorder only stages self-terminating owned native fixtures')
    if job.get('targetOs') == 'windows' and job.get('executable') != 'native-launch.exe':
        raise ValueError('Windows capture requires the owned desktop pipe launcher')
    baseline = 'c630d22f2353d3898024d510f0b402b64bccdb331781fe7885389f73d6200853'
    flash = next((f for f in request.get('files', []) if f.get('Path') == 'flash.bin'), None)
    if not flash or flash.get('Sha256') != baseline:
        raise ValueError('this P1 recorder stages only the exact published untraced baseline')


def stage_http(args) -> dict:
    import sys
    sys.path.insert(0, str(args.runner_scripts.resolve()))
    from runner_transport import RunnerApi, declaration, inside
    from runner_workflows import Workflows
    request = json.loads(args.request.read_text())
    validate_stage_request(request)
    api = RunnerApi(args.url)
    current = api.json('/api/v1/status')
    active = current.get('CurrentJob') or ''
    if current.get('Phase') not in ('idle', 'waiting_for_package') and not active.startswith('pr248-native-'):
        raise ValueError('another runner operation is active; do not mutate its state')
    root = args.payload_dir.resolve()
    local = []
    for item in request['files']:
        path = inside(root, item['Path'])
        if path.exists():
            actual = declaration(root, item['Path'], item.get('Executable', False))
            if actual != item:
                raise ValueError('local payload differs from frozen declaration: ' + item['Path'])
            local.append(item)
        elif not args.reuse:
            raise ValueError('missing payload without an explicit retained source: ' + item['Path'])
    work = Workflows(api)
    identity = request['id']
    api.json('/api/v1/jobs', 'POST', request)
    status = work.status(identity)
    if status['state'] == 'busy':
        work.operation(identity)
        status = work.status(identity)
    if status['state'] == 'draft':
        if args.reuse:
            api.json('/api/v1/jobs/' + identity + '/reuse', 'POST', {'sourceJobId': args.reuse})
            work.operation(identity)
        for item in local:
            api.upload(identity, root, item)
        return work.submit_draft(identity) if args.start else work.status(identity)
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    parse = commands.add_parser('parse')
    parse.add_argument('serial', type=Path)
    parse.add_argument('--output', type=Path, required=True)
    queries = commands.add_parser('queries')
    queries.add_argument('serial', type=Path)
    queries.add_argument('--output', type=Path, required=True)
    pipe = commands.add_parser('pipe-proof')
    pipe.add_argument('server', type=Path)
    pipe.add_argument('client', type=Path)
    pipe.add_argument('--launch', type=Path)
    pipe.add_argument('--output', type=Path, required=True)
    stage = commands.add_parser('stage')
    stage.add_argument('--url', required=True)
    stage.add_argument('--request', type=Path, required=True)
    stage.add_argument('--payload-dir', type=Path, required=True)
    stage.add_argument('--runner-scripts', type=Path, required=True)
    stage.add_argument('--reuse')
    stage.add_argument('--start', action='store_true')
    identity = commands.add_parser('hash')
    identity.add_argument('files', type=Path, nargs='+')
    args = parser.parse_args(argv)
    if args.command == 'stage':
        print(json.dumps(stage_http(args)))
    elif args.command == 'pipe-proof':
        result = parse_pipe_proof(args.server.read_text(), args.client.read_text(),
                                  args.launch.read_text() if args.launch else None)
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps({'bridge_verified': result['bridge_verified'], 'output': str(args.output)}))
    elif args.command in ('parse', 'queries'):
        reader = parse_serial if args.command == 'parse' else parse_queries
        result = reader(args.serial.read_text(encoding='utf-8', errors='replace'))
        result['serial_sha256'] = sha256(args.serial)
        args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        print(json.dumps({'complete': result['complete'],
                          'observations': len(result.get('cases', result.get('observations', []))),
                          'output': str(args.output)}))
    else:
        print(json.dumps({str(path): sha256(path) for path in args.files}, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
