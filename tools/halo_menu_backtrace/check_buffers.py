#!/usr/bin/env python3
"""Check four known Halo menu allocations; addresses are pinned to this lab workload."""
import argparse
import hashlib
import json
from pathlib import Path
SPANS = {
    'campaign': (0x02574000, 'ca1f6b3ebceb68b3616f194fab56d0a44ee7cafe226547c90b83c9f1b474cf96'),
    'multiplayer': (0x027a0000, '3cc5f9d74efe76cb17dcd633b4136bb2e5cf556a0c36b706ce9261397b38db6f'),
    'settings': (0x03160000, '18609b88583d4e8ae7e46980730a591eaff534b898c1d346c24dbe8efa35ca8a'),
    'game_demos': (0x03170000, '862547369863751678a13a51874bf0f6410b9ea6fdc0323384d337f60d9fb814'),
}
def check(path):
    raw = path.read_bytes()
    if len(raw) != 64 * 1024 * 1024:
        raise ValueError('Expected a complete physical 64 MiB capture')
    entries = {}
    for name, (address, expected) in SPANS.items():
        actual = hashlib.sha256(raw[address:address + 16384]).hexdigest()
        entries[name] = {'physical_address': hex(address), 'sha256': actual,
                         'expected_sha256': expected, 'matched': actual == expected}
    return {'memory_sha256': hashlib.sha256(raw).hexdigest(), 'entries': entries,
            'passed': all(v['matched'] for v in entries.values())}
if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('memory', type=Path)
    p.add_argument('--output', type=Path)
    a = p.parse_args()
    r = check(a.memory)
    text = json.dumps(r, indent=2) + '\n'
    if a.output: a.output.write_text(text)
    print(text, end='')
    raise SystemExit(0 if r['passed'] else 1)
