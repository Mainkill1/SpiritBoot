#!/usr/bin/env python3
"""Numeric page observations from private RAM captures; never export contents."""
import argparse
from collections import Counter
import json
from pathlib import Path
import struct

PAGE = 4096


def marker_page(address):
    if address < 0 or address % PAGE or address >= 0x10000000:
        raise ValueError('Expected an aligned physical page below 256 MiB')
    return b''.join(struct.pack('<I', 0xa0000001 | ((address + i) & 0x0ffffffc))
                    for i in range(0, PAGE, 4))


def classify(observed, seeded):
    if len(observed) != PAGE or len(seeded) != PAGE:
        raise ValueError('A complete physical page is required')
    if observed == seeded:
        return 'retained'
    if observed == bytes(PAGE):
        return 'zero'
    if any(observed[i:i+4] == seeded[i:i+4] for i in range(0, PAGE, 4)):
        return 'mixed'
    return 'replaced'


def summarize(observed, before=None, ranges=None):
    if len(observed) not in (64 * 1024 * 1024, 128 * 1024 * 1024):
        raise ValueError('Require a complete 64 or 128 MiB physical RAM capture')
    if before is not None and len(before) != len(observed):
        raise ValueError('Before and after captures must have identical lengths')
    if ranges is None:
        ranges = [(0, len(observed))]
    prior_end = 0
    rows = []
    for start, length in sorted(ranges):
        if (start < prior_end or length <= 0 or start % PAGE or length % PAGE
                or start + length > len(observed)):
            raise ValueError('Ranges must be aligned, bounded, and nonoverlapping')
        counts = Counter()
        for address in range(start, start + length, PAGE):
            seed = (marker_page(address) if before is None
                    else before[address:address+PAGE])
            counts[classify(observed[address:address+PAGE], seed)] += 1
        rows.append({'physical': start, 'bytes': length, 'page_classes': dict(counts)})
        prior_end = start + length
    return {'schema': 1, 'capture_bytes': len(observed), 'ranges': rows,
            'interpretation': 'Page observations, not writer attribution or physical ownership'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('after', type=Path)
    parser.add_argument('--before', type=Path,
                        help='Warm-reset capture; absent means a verified cold marker seed')
    parser.add_argument('--range', action='append', default=[], metavar='START:BYTES',
                        help='Hex or decimal physical range; repeat for owned buffers')
    args = parser.parse_args()
    ranges = [tuple(int(value, 0) for value in item.split(':')) for item in args.range]
    if any(len(item) != 2 for item in ranges):
        parser.error('Each range must contain START:BYTES')
    result = summarize(args.after.read_bytes(),
                       args.before.read_bytes() if args.before else None,
                       ranges or None)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
