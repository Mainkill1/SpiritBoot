#!/usr/bin/env python3
"""Fail if boot-menu code or private data escapes the discardable INIT section."""

import argparse
from pathlib import Path
import re
import shutil
import subprocess


MENU_SYMBOL = re.compile(
    r"^_(?:NxkBootSetupRun|Bs|sb_(?:boot|setup|ohci|xid)|label_|text_|languages|masks)"
)


def output(command: list[str]) -> str:
    return subprocess.check_output(command, text=True, stderr=subprocess.STDOUT)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kernel", type=Path)
    parser.add_argument("--objdump")
    parser.add_argument("--nm")
    args = parser.parse_args()
    objdump = args.objdump or shutil.which("i686-w64-mingw32-objdump") or \
        shutil.which("objdump")
    nm = args.nm or shutil.which("i686-w64-mingw32-nm") or shutil.which("nm")
    if not objdump or not nm:
        raise SystemExit("objdump and nm are required")

    sections = output([objdump, "-h", str(args.kernel)])
    init = None
    for line in sections.splitlines():
        match = re.match(
            r"^\s*\d+\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)", line
        )
        if match and match.group(1) == "INIT":
            size = int(match.group(2), 16)
            start = int(match.group(3), 16)
            init = (start, start + size)
            break
    if init is None:
        raise SystemExit("kernel has no INIT section")

    found = []
    escaped = []
    symbols = output([nm, "-n", "--defined-only", str(args.kernel)])
    for line in symbols.splitlines():
        match = re.match(r"^([0-9a-fA-F]+)\s+\S\s+(\S+)$", line)
        if not match or not MENU_SYMBOL.match(match.group(2)):
            continue
        address = int(match.group(1), 16)
        found.append((address, match.group(2)))
        if not init[0] <= address < init[1]:
            escaped.append((address, match.group(2)))

    if not any(name.startswith("_NxkBootSetupRun") for _, name in found):
        raise SystemExit("boot-menu entry symbol is missing")
    if len(found) < 20:
        raise SystemExit(f"only {len(found)} boot-menu symbols were audited")
    if escaped:
        details = "\n".join(f"  0x{address:08x} {name}"
                            for address, name in escaped)
        raise SystemExit("boot-menu symbols escaped INIT:\n" + details)
    print(
        f"boot-menu placement: {len(found)} symbols in "
        f"INIT 0x{init[0]:08x}-0x{init[1]:08x}"
    )


if __name__ == "__main__":
    main()
