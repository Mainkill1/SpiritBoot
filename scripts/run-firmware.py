#!/usr/bin/env python3
"""Capture an open Xbox firmware run in xemu, with optional strict TAP grading."""

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.firmware import run_firmware


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("xemu", "flash", "hdd", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--dvd", type=Path)
    parser.add_argument("--timeout", type=float, default=240)
    parser.add_argument("--memory-mib", type=int, choices=(64, 128), default=128,
                        help="xemu RAM capacity; must match the selected firmware layout")
    parser.add_argument("--expect-tap", action="store_true")
    parser.add_argument("--preserve-hdd", action="store_true",
                        help="retain guest writes on a private HDD copy in the capture directory")
    parser.add_argument("--tb-plugin", type=Path,
                        help="explicit optional TB-frequency plugin; requires plugin-enabled xemu")
    args = parser.parse_args()
    try:
        result = run_firmware(args.xemu, args.flash, args.hdd, args.dvd,
                              args.output, args.timeout, args.expect_tap, args.preserve_hdd,
                              tb_plugin=args.tb_plugin, memory_mib=args.memory_mib)
    except (OSError, ValueError) as error:
        print(f"launch failed: {error}", file=sys.stderr)
        return 1
    print(f"{result['status']}: {args.output / 'run.json'}")
    if "tap" in result:
        print(result["tap"])
    return 0 if result["status"] in ("captured", "passed") else 1


if __name__ == "__main__":
    sys.exit(main())
