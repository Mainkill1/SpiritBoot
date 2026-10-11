#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compile real setup sources, exercise their host contract, audit i386 objects.

This is not an Xbox input/rendering/EEPROM or physical page-ownership test.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src/boot/setup"
CC = shlex.split(os.environ.get("CC", "cc"))
COMMON = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-I" + str(SOURCE)]
SOURCES = [str(SOURCE / name) for name in ("boot_setup.c", "boot_arena.c")]
TEST = str(Path(__file__).with_name("test_boot_setup.c"))


def run(args: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(args, input=stdin, text=True, capture_output=True,
                            timeout=60, check=False)
    if result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {shlex.join(args)}\n"
                           f"{result.stdout}{result.stderr}")
    return result.stdout


def check(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for name, flags in (("sanitized", ["-O1", "-g", "-fsanitize=address,undefined",
                                       "-fno-omit-frame-pointer"]),
                        ("optimized", ["-Os"])):
        binary = output / ("test-" + name)
        run(CC + COMMON + flags + [TEST] + SOURCES + ["-o", str(binary)])
        text = run([str(binary)])
        checks = re.findall(r"^ok (\d+) - (.+)$", text, re.M)
        plans = re.findall(r"^1\.\.(\d+)$", text, re.M)
        assert len(plans) == 1 and int(plans[0]) == len(checks), text
        assert [int(n) for n, _ in checks] == list(range(1, len(checks) + 1)), text
        assert "TAP version 13\n" in text and not re.search(r"^not ok", text, re.M), text
        print(f"{name}: {len(checks)} tests passed")
        if name == "sanitized":
            print(text, end="")

    demo = output / "boot-setup-demo"
    run(CC + COMMON + ["-Os", str(ROOT / "tools/boot_setup_demo.c")] + SOURCES +
        ["-o", str(demo)])
    scenarios = (
        ("skip", "n\n", ("setup arena never allocated",)),
        ("save", "h\ne\nx\ne\n", ("remaining owned bytes=0", "simulated commits=1",
                                      "Requested action: reboot")),
        ("discard", "h\ne\nb\ne\n", ("remaining owned bytes=0", "simulated commits=0",
                                         "Requested action: continue boot")),
    )
    for name, commands, expected in scenarios:
        text = run([str(demo)], stdin=commands)
        assert all(part in text for part in expected), text
        print(f"host demonstration {name}: passed")

    total = 0
    maximum_frame = 0
    for source in SOURCES:
        obj = output / (Path(source).stem + "-i386.o")
        flags = ["-m32", "-Os", "-ffreestanding", "-fno-builtin", "-fno-pic", "-fno-pie",
                 "-fno-asynchronous-unwind-tables", "-fstack-usage"]
        run(CC + COMMON + flags + ["-c", source, "-o", str(obj)])
        assert not run(["nm", "-u", str(obj)]).strip(), "unexpected runtime dependency"
        symbols = run(["nm", "--defined-only", str(obj)])
        assert not re.search(r"^[0-9a-fA-F]+\s+[BbCcDdGgSs]\s+", symbols, re.M), symbols
        sections = run(["size", "-A", str(obj)])
        for line in sections.splitlines():
            match = re.match(r"(\.(?:text|rodata)(?:[.][\w.]+)?)\s+(\d+)\s+", line)
            if match:
                total += int(match[2])
        for line in obj.with_suffix(".su").read_text().splitlines():
            _, count, kind = line.split("\t")
            assert kind in ("static", "dynamic,bounded"), line
            maximum_frame = max(maximum_frame, int(count))
        print(f"i386 {obj.name}: no writable globals or undefined symbols")
    assert total <= 12 * 1024, f"core code/rodata budget exceeded: {total}"
    assert maximum_frame <= 256, f"individual core frame exceeded: {maximum_frame}"
    print(f"i386 core text+rodata={total} bytes; maximum individual frame={maximum_frame} bytes")
    print("Object sizes exclude native adapters, graphics, overlay linking and allocator overhead.")
    print(f"Interactive host demo: {demo}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="keep binaries here; otherwise use a temporary directory")
    args = parser.parse_args()
    if args.output:
        check(args.output.resolve())
    else:
        with tempfile.TemporaryDirectory(prefix="spiritboot-setup-") as directory:
            check(Path(directory))
        print("Temporary test binaries removed.")


if __name__ == "__main__":
    main()
