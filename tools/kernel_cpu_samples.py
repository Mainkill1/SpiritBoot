"""Attribute perf leaf sample periods; not kernel duration or frame-critical cost."""

import argparse
from bisect import bisect_right
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess

try:
    from .kernel_hotpaths import parse_sections, parse_symbols
except ImportError:
    from kernel_hotpaths import parse_sections, parse_symbols

LINE = re.compile(r'\s*(.+?)\s+(\d+)/(\d+)\s+(\d+)\.(\d{1,9}):\s+(\d+)\s+'
                  r'([a-fA-F0-9]+)\s+(.*)\s+\((.*?)\)\s*')
GUEST = re.compile(r'guest-0x([a-fA-F0-9]+)(?:\+0x([a-fA-F0-9]+))?')
MAP = re.compile(r'perf-(\d+)\.map')


def parse_samples(lines, expected_pid, max_samples=1000000):
    """Consume the explicit perf script -G field contract, preserving unknowns."""
    if type(expected_pid) is not int or expected_pid < 1:
        raise ValueError('invalid expected process identity')
    rows = []
    for number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        match = LINE.fullmatch(line)
        if not match or len(line) > 16384:
            raise ValueError(f'malformed sample on line {number}')
        comm, pid, tid, seconds, fraction, period, ip, symbol, dso = match.groups()
        if not symbol.strip() or not dso.strip():
            raise ValueError(f'malformed sample on line {number}')
        pid, tid, period, ip = int(pid), int(tid), int(period), int(ip, 16)
        if pid != expected_pid or tid < 1 or not 0 < period < 2**64 or ip >= 2**64:
            raise ValueError(f'invalid sample identity/period on line {number}')
        mapping = MAP.fullmatch(Path(dso).name)
        if mapping and int(mapping[1]) != expected_pid:
            raise ValueError(f'stale guest map on line {number}')
        guest = GUEST.fullmatch(symbol) if mapping else None
        # QEMU maps each generated host instruction span to its guest PC.
        # perf's optional suffix is a host offset inside that span.
        pc = int(guest[1], 16) if guest else None
        if pc is not None and pc > 0xffffffff:
            raise ValueError(f'invalid guest PC on line {number}')
        rows.append(dict(comm=comm, pid=pid, tid=tid, period=period, ip=ip,
                         time_ns=int(seconds) * 10**9 + int(fraction.ljust(9, '0')),
                         symbol=symbol, dso=dso, guest_pc=pc, guest_map=bool(mapping)))
        if len(rows) > max_samples:
            raise ValueError('sample budget exceeded')
    if not rows:
        raise ValueError('empty sample export')
    return rows


def rank_samples(rows, symbols, start_ns=None, end_ns=None, host_executable=None):
    if host_executable is not None and (not isinstance(host_executable, str) or
                                       not Path(host_executable).is_absolute()):
        raise ValueError('host executable must be the recorded absolute DSO path')
    if any(x is not None and (type(x) is not int or x < 0) for x in (start_ns, end_ns)):
        raise ValueError('invalid monotonic window')
    if start_ns is not None and end_ns is not None and end_ns < start_ns:
        raise ValueError('reversed monotonic window')
    selected = [x for x in rows if (start_ns is None or x['time_ns'] >= start_ns) and
                (end_ns is None or x['time_ns'] <= end_ns)]
    if not selected:
        raise ValueError('window contains no samples')
    starts = [x['start'] for x in symbols]
    categories, counts, modules, kernel, host, guests = (Counter() for _ in range(6))
    total = sum(x['period'] for x in selected)
    for row in selected:
        pc, period = row['guest_pc'], row['period']
        if pc is not None:
            guests[pc] += period
            index = bisect_right(starts, pc) - 1
            if index >= 0 and pc < symbols[index]['end']:
                category = 'kernel_jit'
                kernel[index] += period
            else:
                category = 'other_guest_jit'
        elif row['guest_map']:
            category = 'unresolved_guest_jit'
        elif row['dso'] == '[unknown]':
            category = 'unresolved'
        elif (row['dso'] == host_executable if host_executable is not None else
              Path(row['dso']).name == 'xemu'):
            category = 'xemu_host'
            host[row['symbol']] += period
        else:
            category = 'host_library'
            host[row['dso'] + ':' + row['symbol']] += period
        categories[category] += period
        counts[category] += 1
        modules[row['dso']] += period

    def ranked(counter):
        return [dict(name=str(k), period=p, share_pct=p * 100 / total)
                for k, p in counter.most_common(20)]

    return dict(schema=1, measurement='Sampled CPU event periods, not function duration or calls',
                attribution='Mapped guest instruction PCs use next-symbol PE interval estimates',
                limitations=['Host helpers and library samples are not charged back to guest callers',
                             'Sampling does not measure blocking, exclusive kernel time or frame-critical cost',
                             'Outside the pinned image remains other guest code, without inferred title identity',
                             'Counter frequency and event/clock/lost-sample qualification require recorder evidence'],
                host_executable=host_executable, default_host_basename='xemu',
                samples=len(selected), excluded_samples=len(rows) - len(selected),
                weighted_period=total, window=dict(start_ns=start_ns, end_ns=end_ns),
                categories={k: dict(period=p, samples=counts[k], share_pct=p * 100 / total)
                            for k, p in categories.items()},
                kernel=[dict(**symbols[k], period=p, share_pct=p * 100 / total)
                        for k, p in kernel.most_common(20)], host=ranked(host),
                modules=ranked(modules), guest_pcs=ranked(guests))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--samples', type=Path, required=True)
    parser.add_argument('--pid', type=int, required=True, help='PID from the recorder manifest')
    parser.add_argument('--kernel', type=Path, required=True, help='Exact unstripped kernel PE')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--start-ns', type=int)
    parser.add_argument('--end-ns', type=int)
    parser.add_argument('--host-executable', help='Exact recorded executable DSO path; default basename xemu')
    args = parser.parse_args()
    try:
        with args.samples.open() as stream:
            rows = parse_samples(stream, args.pid)
        sections = parse_sections(subprocess.check_output(['objdump', '-h', str(args.kernel)], text=True))
        symbols = parse_symbols(subprocess.check_output(['nm', '-n', '--defined-only', str(args.kernel)],
                                                       text=True), sections)
        if not symbols:
            raise ValueError('no named executable kernel symbols')
        result = rank_samples(rows, symbols, args.start_ns, args.end_ns, args.host_executable)
        result['inputs'] = {name: dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                            for name, path in (('samples', args.samples), ('kernel', args.kernel))}
        result['expected_pid'] = args.pid
        with args.output.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f'CPU attribution failed: {error}\n')


if __name__ == '__main__':
    main()
