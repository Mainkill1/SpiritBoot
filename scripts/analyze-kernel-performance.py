#!/usr/bin/env python3
"""Validate immutable paired captures and report conservative per-workload timings."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.kernel_performance import BASELINE, analyze, markdown


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pairs', type=Path)
    parser.add_argument('--runtime-inputs', type=Path, required=True)
    parser.add_argument('--candidate-build', type=Path)
    parser.add_argument('--baseline-hash', default=BASELINE)
    parser.add_argument('--candidate-hash')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--markdown', type=Path, required=True)
    args = parser.parse_args()
    try:
        report = analyze(args.pairs, args.runtime_inputs, args.candidate_build, args.baseline_hash, args.candidate_hash)
        table = markdown(report)
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as error:
        print(f'analysis refused: {error}', file=sys.stderr)
        return 1
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n')
    args.markdown.write_text(table)
    print(table)
    return 0


if __name__ == '__main__':
    sys.exit(main())
