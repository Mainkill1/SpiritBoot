#!/usr/bin/env python3
"""Join pinned adapter submissions to parent completions; never infer from screenshots."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

def analyze(trace, binding):
    active = {}
    depth, peak = Counter(), Counter()
    rejected, menus = [], []
    statuses = Counter()
    offsets = {int(v, 16): k for k, v in binding['menu_disk_offsets'].items()}
    submitted = completed = 0
    for number, line in enumerate(trace.open(errors='replace'), 1):
        if not line.startswith('spirit_menu '):
            continue
        fields = dict(token.split('=', 1) for token in line.split()[1:] if '=' in token)
        pc = fields['pc']
        irp = fields['irp']
        if pc == binding['pcs']['submit']:
            adapter = fields['eax']
            offset = int(fields['a1'], 16) | (int(fields['a2'], 16) << 32)
            length = int(fields['a3'], 16) | (int(fields['a4'], 16) << 32)
            if irp in active:
                raise ValueError(f'IRP resubmitted without observed completion at line {number}')
            depth[adapter] += 1
            peak[adapter] = max(peak[adapter], depth[adapter])
            row = {'line': number, 'adapter': adapter, 'irp': irp,
                   'including_new_request': depth[adapter], 'buffer': fields['buffer'],
                   'offset': f'{offset:x}', 'length': length}
            if offset in offsets and length == 16384:
                row['menu_entry'] = offsets[offset]
            active[irp] = row
            submitted += 1
        elif pc == binding['pcs']['complete'] and irp in active:
            row = active.pop(irp)
            depth[row['adapter']] -= 1
            row.update(completion_line=number, status=fields['status'],
                       actual_bytes=int(fields['info']))
            statuses[fields['status']] += 1
            completed += 1
            if fields['status'] == 'c000009a':
                rejected.append(row.copy())
            if 'menu_entry' in row:
                menus.append(row)
    return {'bios_sha256': binding['bios_sha256'],
            'trace_sha256': hashlib.sha256(trace.read_bytes()).hexdigest(),
            'submitted': submitted, 'completed': completed,
            'outstanding_at_end': len(active), 'peak_including_new_request': dict(peak),
            'completion_status_counts': dict(statuses),
            'resource_rejection_count': len(rejected),
            'rejection_depths': dict(Counter(r['including_new_request'] for r in rejected)),
            'menu_requests': menus, 'resource_rejections': rejected}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trace', required=True, type=Path)
    p.add_argument('--binding', required=True, type=Path)
    p.add_argument('--bios', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    b = json.loads(a.binding.read_text())
    if hashlib.sha256(a.bios.read_bytes()).hexdigest() != b['bios_sha256']:
        p.error('BIOS does not match the address/calling-convention binding')
    result = analyze(a.trace, b)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'resource_rejections'}, indent=2))
