# SPDX-License-Identifier: MIT
"""Fail-closed qualification of the exact bounded native v2 cohort."""
import argparse
from collections import Counter
import hashlib
import importlib.util
import json
from pathlib import Path

import analyze_prefix as prefix


EXPECTED_LIMITS = {'handle': 0x42c, 'max_api': 64, 'admitted': 64,
                   'returned': 64, 'admission_closed': 1, 'range_count': 2}
EXPECTED_RANGES = [(0x84001000, 0x84055400), (0x84069000, 0x84069b08)]


def qualify(prefix_text, identity_text, receipts_text, identity):
    """Qualify accounting and callback lifetimes, not payload bytes or speed."""
    capture = prefix.parse(prefix_text)
    if capture['meta']['version'] != 2 or capture['limits'] != EXPECTED_LIMITS:
        raise ValueError('Native capture does not match frozen v2 admission configuration')
    ranges = sorted((row['start'], row['end']) for row in capture['ranges'].values())
    if ranges != EXPECTED_RANGES:
        raise ValueError('Native capture does not match frozen owned address ranges')

    meta, events = identity.parse(identity_text)
    if meta['open_api'] or meta['map_open']:
        raise ValueError('Identity capture contains open API or mapper state')
    start, end = identity.bounds(receipts_text)
    begins = [event for event in events if event['kind'] == 1]
    returned = [event for event in events if event['kind'] == 2]
    by_api = {event['api']: event for event in begins}
    by_return = {event['api']: event for event in returned}
    if (len(begins) != 64 or len(by_api) != 64 or len(returned) != 64 or
            set(by_api) != set(by_return)):
        raise ValueError('Expected exactly 64 distinct complete identity calls')
    if any(event['value0'] != EXPECTED_LIMITS['handle'] for event in begins):
        raise ValueError('Identity handle differs from frozen admission handle')
    for api, event in by_api.items():
        ret = by_return[api]
        if not start <= event['host_ns'] <= ret['host_ns'] <= end:
            raise ValueError('An admitted API lies outside or crosses the receipt interval')
        if ret['status'] not in (0, 0x103):
            raise ValueError('An admitted native read returned failure')

    # Resolve callback ownership through the live IOSB lifetime, never the
    # event's active-API label. A successful callback may precede native return.
    live_iosbs = {}
    callbacks = {}
    seen_begins, seen_returns = set(), set()
    drain_seq = None
    unassigned_post_drain = 0
    post_drain_events = Counter()
    for event in events:
        if drain_seq is not None:
            post_drain_events[identity.KINDS[event['kind']]] += 1
            unassigned_post_drain += event['kind'] == 6
            continue
        if event['kind'] == 1:
            seen_begins.add(event['api'])
            if event['iosb'] in live_iosbs:
                raise ValueError('IOSB reused before its callback')
            live_iosbs[event['iosb']] = event['api']
        elif event['kind'] == 2:
            seen_returns.add(event['api'])
        elif event['kind'] == 6:
            api = live_iosbs.pop(event['iosb'], None)
            if api is None or api in callbacks:
                raise ValueError('Unknown or duplicate callback')
            if event['status'] != 0 or event['info'] != by_api[api]['bytes']:
                raise ValueError('Callback status or length does not match its read')
            if not start <= event['host_ns'] <= end:
                raise ValueError('A callback lies outside the receipt interval')
            callbacks[api] = event
        if len(seen_begins) == len(seen_returns) == len(callbacks) == 64 and not live_iosbs:
            drain_seq = event['seq']
    if drain_seq is None or live_iosbs or set(callbacks) != set(by_api):
        raise ValueError('Missing callback or open IOSB lifetime')

    selected_events = [event for event in events if event['seq'] <= drain_seq]
    analyzed = identity.analyze(selected_events, start, end, meta)
    reads = analyzed['reads']
    if len(reads) != 64 or {row['api'] for row in reads} != set(by_api):
        raise ValueError('Receipt-selected identity analysis omitted an admitted call')
    if any(row['issues'] or not row['callback_seen_by_phase_end'] for row in reads):
        raise ValueError('Identity analysis reports unresolved or unsuccessful lifetimes')
    if (any(analyzed['pending_at_phase_end'].values()) or analyzed['open_mapper_at_phase_end'] or
            analyzed['event_counts'].get('open_api_at_phase_end', 0)):
        raise ValueError('Selected cohort ends with open tracked state')

    by_seq = {event['seq']: event for event in events}
    observations = capture['rows'] + capture['excluded']
    if {row['api'] for row in observations} != set(by_api):
        raise ValueError('Prefix observations do not cover exactly the admitted calls')
    for row in observations + capture['translations']:
        api, seq = row['api'], row['identity_seq']
        if (api not in by_api or seq not in by_seq or
                not by_api[api]['seq'] <= seq < by_return[api]['seq']):
            raise ValueError('Prefix identity reference lies outside an admitted active call')

    owned = sum(row['begun'] for row in capture['rows'])
    excluded = sum(row['begun'] for row in capture['excluded'])
    return {'status': 'qualified', 'version': 1, 'selected_calls': 64,
            'successful_callbacks': len(callbacks), 'selected_drain_seq': drain_seq,
            'unassigned_post_drain': unassigned_post_drain,
            'post_drain_event_counts': dict(post_drain_events), 'admission': capture['limits'],
            'owned_ranges': [{'start': f'{a:08x}', 'end': f'{b:08x}'} for a, b in ranges],
            'receipt_bounds_ns': {'start': start, 'end': end},
            'prefix_health': capture['health'], 'identity_header': meta,
            'instruction_starts': {'total': owned + excluded, 'owned': owned, 'excluded': excluded},
            'native_return_status_counts': dict(Counter(f'{event["status"]:08x}' for event in returned)),
            'pending_at_phase_end': analyzed['pending_at_phase_end'],
            'calls': [{'api': api, 'bytes': by_api[api]['bytes'],
                       'begin_seq': by_api[api]['seq'], 'return_seq': by_return[api]['seq'],
                       'callback_seq': callbacks[api]['seq']} for api in sorted(by_api)],
            'limitations': ['Qualifies recorder accounting and observed callback/status/length lifetimes; no payload-byte oracle.',
                            'After all 64 calls have begun, returned and completed, later events are outside the selected cohort; callback ownership is unassigned.',
                            'Instruction starts are not CPU time or architectural retirement.',
                            'Observation may alter timing and queue outcomes; no performance conclusion.',
                            'Declared address ranges do not independently prove runtime byte identity.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prefix', 'identity', 'receipts', 'identity-tools', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    identity_path = args.identity_tools / 'analyze_identity.py'
    spec = importlib.util.spec_from_file_location('qualification_identity', identity_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    inputs = {name: getattr(args, name).read_bytes() for name in ('prefix', 'identity', 'receipts')}
    result = qualify(*(inputs[name].decode() for name in ('prefix', 'identity', 'receipts')), module)
    result['hashes'] = {name: hashlib.sha256(data).hexdigest() for name, data in inputs.items()}
    result['tool_hashes'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                            for path in (Path(__file__), Path(prefix.__file__), identity_path)}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
