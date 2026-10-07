#!/usr/bin/env python3
"""Build a pinned Roswell flash image; retain provenance and build diagnostics."""

import argparse
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.firmware import DEFAULT_LOCK, build_firmware


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--variant", choices=("release", "debug"), default="release")
    parser.add_argument("--lock", type=Path, default=DEFAULT_LOCK)
    args = parser.parse_args()
    try:
        result = build_firmware(args.source, args.output, args.variant, args.lock)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"build failed: {error}", file=sys.stderr)
        return 1
    print(f"built {args.output / 'flash.bin'}: sha256={result['flash_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
