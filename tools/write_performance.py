"""Strict v1 focused native write fixture parser; never infer success from timing."""
import argparse
import json
from pathlib import Path
import re
from statistics import median

CASES = {'leaf-flush': 65536, 'leaf-overwrite': 131072, 'leaf-open-same-eof': 131072,
         'flush-written-64k': 65536, 'write-64k': 65536, 'overwrite-existing-128k': 131072,
         'reextend-128k': 131072, 'parent-open': 0, 'close-written-64k': 65536}


def parse(text):
    lines = text.replace('\r', '').splitlines()
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    require(lines.count('== write-performance begin ==') == 1, 'missing/duplicate begin')
    require(lines.count('== write-performance end PASS ==') == 1, 'missing/duplicate passing end')
    begin = lines.index('== write-performance begin ==')
    end = lines.index('== write-performance end PASS ==')
    require(begin < end, 'invalid boundaries')
    region = lines[begin:end + 1]
    relevant = [x for x in lines if x.startswith(('# WRITE', 'ok ', 'not ok ', '1..', 'TAP version', '== write-performance'))]
    require(relevant == [x for x in region if x in relevant], 'records outside capture')
    require(region[1:3] == ['TAP version 14', '1..81'], 'TAP header/plan mismatch')
    meta = re.fullmatch(r'# WRITE-META version=1 frequency=(\d+) repeats=9 cases=9', region[3])
    require(meta is not None and int(meta[1]) > 0, 'invalid clock metadata')
    frequency = int(meta[1])
    records = [x for x in region[4:-1] if x.startswith(('# WRITE', 'ok ', 'not ok ', '1..', 'TAP version'))]
    require(len(records) == 163 and records[-1] == '# WRITE-SUMMARY samples=81 failures=0', 'incomplete or surplus records')
    samples = []
    n = 0
    for case, size in CASES.items():
        for sample in range(9):
            row = re.fullmatch(r'# WRITE case=([\w-]+) sample=(\d+) ticks=(\d+) bytes=(\d+) correct=1', records[n * 2])
            require(row is not None, 'invalid sample')
            require((row[1], int(row[2]), int(row[4])) == (case, sample, size), 'case/sample/size mismatch')
            require(int(row[3]) > 0, 'nonpositive ticks')
            require(records[n * 2 + 1] == f'ok {n + 1} - {case}/{sample}', 'failed/mismatched TAP result')
            samples.append({'case': case, 'sample': sample, 'ticks': int(row[3]), 'bytes': size})
            n += 1
    summary = {}
    for case in CASES:
        rows = [s['ticks'] for s in samples if s['case'] == case]
        summary[case] = {'first_call_ms': rows[0] * 1000 / frequency,
                         'warm_median_ms': median(rows[1:]) * 1000 / frequency,
                         'warm_min_ms': min(rows[1:]) * 1000 / frequency,
                         'warm_max_ms': max(rows[1:]) * 1000 / frequency}
    return {'frequency': frequency, 'samples': samples, 'summary': summary}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('serial', type=Path)
    args = ap.parse_args()
    print(json.dumps(parse(args.serial.read_text()), indent=2))


if __name__ == '__main__':
    main()
