#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Validate a complete cadence serial log and summarize public observations."""
import argparse
import json
import math
from pathlib import Path
import re


def analyze(text):
    records = {}
    for line in text.splitlines():
        match = re.search(r'FORZA-CADENCE-([A-Z-]+)\s+(.*)', line)
        if not match:
            continue
        kind, fields = match.groups()
        values = dict(re.findall(r'(\w+)=([^\s]+)', fields))
        records.setdefault(kind, []).append(values)
    for kind in ('META', 'END', 'SEM-END', 'HANDOFF-END'):
        if len(records.get(kind, [])) != 1:
            raise ValueError(f'exactly one {kind} required')
    for kind, rows in records.items():
        for row in rows:
            if int(row.get('failures', 0)):
                raise ValueError(f'{kind} reports failures')
    meta = records['META'][0]
    frequency = int(meta['frequency'])
    if frequency <= 0 or int(meta['seconds']) < 10 or int(meta['cases']) != 8:
        raise ValueError('invalid META clock, duration or case count')
    if int(records['SEM-END'][0]['cases']) != 32 or int(records['HANDOFF-END'][0]['cases']) != 40:
        raise ValueError('missing semantic or handoff cases')
    semantic_indices = set()
    for row in records.get('SEM', []):
        row = {key: int(value, 16 if key in ('return', 'drain') else 10) for key, value in row.items()}
        if row['index'] in semantic_indices:
            raise ValueError('duplicate SEM index')
        semantic_indices.add(row['index'])
        if row['before'] != 0 or row['after'] != 1 or row['return'] != 0xc0 or row['drain'] != 0 or row['errors']:
            raise ValueError('SEM callback/status failure')
    if semantic_indices != set(range(32)):
        raise ValueError('all 32 unique SEM records required')
    cases = {}
    for row in records.get('CASE', []):
        row = {key: int(value) for key, value in row.items()}
        case_id = row['id']
        if case_id in cases:
            raise ValueError(f'duplicate CASE {case_id}')
        if row['elapsed'] < frequency * 10:
            raise ValueError(f'CASE {case_id} duration below ten seconds')
        if row['operations'] < 2 or row['total_bytes'] != row['operations'] * row['bytes']:
            raise ValueError(f'CASE {case_id} operations/byte count mismatch')
        expected = (900 if case_id < 4 else 783, 512 if case_id % 4 < 2 else 65536, 33 if case_id % 2 else 0)
        if (row['target'], row['bytes'], row['frame_ms']) != expected or row['before'] != row['target']:
            raise ValueError(f'CASE {case_id} unexpected matrix/pressure')
        cases[case_id] = row
    if sorted(cases) != list(range(8)):
        raise ValueError('eight distinct CASE records required')
    timing = {}
    for row in records.get('TIMING', []):
        row = {key: int(value) for key, value in row.items()}
        case_id = row.pop('id')
        if case_id in timing:
            raise ValueError(f'duplicate TIMING {case_id}')
        timing[case_id] = row
    if sorted(timing) != list(range(8)):
        raise ValueError('eight distinct TIMING records required')
    for case_id, case in cases.items():
        histogram = {}
        for row in records.get('HIST', []):
            if int(row['id']) != case_id:
                continue
            bucket, count = int(row['low_ms']), int(row['count'])
            if bucket in histogram or bucket < 0 or bucket > 127 or count <= 0:
                raise ValueError('invalid/duplicate histogram bucket')
            histogram[bucket] = count
        if sum(histogram.values()) != case['operations']:
            raise ValueError(f'CASE {case_id} histogram count mismatch')
        stats = timing[case_id]
        if not (0 <= stats['immediate'] <= case['operations'] and 0 <= stats['pending'] <= case['operations']):
            raise ValueError('TIMING operation count mismatch')
        case.update(stats)
        case['elapsed_seconds'] = case['elapsed'] / frequency
        case['operations_per_second'] = case['operations'] / case['elapsed_seconds']
        for name in ('submit', 'callback', 'poll'):
            case[name + '_mean_ms'] = stats[name + '_sum'] * 1000 / frequency / case['operations']
        case['callback_max_ms'] = stats['callback_max'] * 1000 / frequency
        for percentile in (50, 95):
            remaining = math.ceil(case['operations'] * percentile / 100)
            for bucket, count in sorted(histogram.items()):
                remaining -= count
                if remaining <= 0:
                    case[f'callback_p{percentile}_bucket_ms'] = [bucket, None if bucket == 127 else bucket + 1]
                    break
    operation_indices = {case_id: set() for case_id in cases}
    for row in records.get('OP', []):
        row = {key: int(value, 16 if key in ('status', 'immediate_status') else 10) for key, value in row.items()}
        case_id, index = row['id'], row['index']
        if case_id not in cases or index in operation_indices[case_id]:
            raise ValueError('unknown/duplicate OP sample')
        operation_indices[case_id].add(index)
        if row['calls'] != 1 or row['status'] not in (0, 0x103) or row['polls'] < 1:
            raise ValueError('OP callback/submission count or status failure')
        if not (0 < row['issue'] <= row['returned'] <= row['immediate'] <= row['last_poll'] <= row['callback']):
            raise ValueError('OP timestamp order failure')
        if row['polls'] == 1 and row['immediate_status'] != 0xc0:
            raise ValueError('OP callback delivery has wrong immediate wait status')
        if row['observed'] and not (row['returned'] <= row['observed'] <= row['callback']):
            raise ValueError('OP event observation order failure')
    for case_id, case in cases.items():
        if operation_indices[case_id] != set(range(min(32, case['operations']))):
            raise ValueError(f'CASE {case_id} missing OP samples')
    handoff = []
    handoff_indices = set()
    for row in records.get('HANDOFF', []):
        row = {key: int(value, 16 if key in ('status', 'enqueue_status') else 10) for key, value in row.items()}
        key = row['kind'], row['index']
        if key in handoff_indices:
            raise ValueError('duplicate HANDOFF record')
        handoff_indices.add(key)
        if row['errors'] or row['first_calls'] not in (0, 1) or not (0 < row['enter'] <= row['returned']):
            raise ValueError('HANDOFF identity/phase/count/order failure')
        if row['first_calls']:
            if not (row['enter'] <= row['callback'] <= row['returned']):
                raise ValueError('HANDOFF first callback outside first call')
        elif row['callback'] < row['returned']:
            raise ValueError('HANDOFF later callback timestamp before return')
        if row['kind'] == 3 and (row['first_calls'] != 1 or row['status'] != 0xc0):
            raise ValueError('HANDOFF prequeued control failure')
        during = row['enter'] <= row['producer'] <= row['enqueued'] <= row['returned']
        if row['enqueue_status'] or row['calls'] != 1:
            raise ValueError('HANDOFF enqueue/count failure')
        if row['kind'] == 1 and row['first_calls']:
            raise ValueError('HANDOFF nonalertable callback')
        row['outcome'] = ('delivered_before_return' if row['first_calls'] else
                          'queued_during_call_delivered_later' if during else 'enqueue_during_call_not_established')
        handoff.append(row)
    if handoff_indices != {(kind, index) for kind in range(5) for index in range(8)}:
        raise ValueError('all 40 unique HANDOFF records required')
    return {'frequency': frequency, 'cases': list(cases.values()), 'handoff': handoff,
            'limitations': ['native completion is not timestamped',
                            'ready_misses uses completion-event observation, not an APC enqueue timestamp',
                            'full byte oracle and buffer preparation occur between dependent reads',
                            'histogram bins have one millisecond width; bin 127 is unbounded above',
                            'frame cadence uses blocking nonalertable delays, not CPU-bound frame rendering',
                            'enqueue-return timestamps may follow issuer preemption, so absence inside a call is not established']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('serial', type=Path)
    args = parser.parse_args()
    try:
        result = analyze(args.serial.read_text(errors='replace'))
    except (ValueError, KeyError) as error:
        parser.exit(1, f'invalid cadence run: {error}\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
