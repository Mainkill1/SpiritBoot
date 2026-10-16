#!/usr/bin/env python3
"""Validate the safe and QEMU-gated ATA device-select settle paths."""

import argparse
from pathlib import Path
import re
import sys


def check(source_root: Path) -> None:
    header = source_root / "drivers/storage/ide/pciidex/pata.h"
    identify = source_root / "drivers/storage/ide/atapi/dev_identify.c"
    try:
        text = header.read_text(encoding="utf-8")
        identify_text = identify.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"cannot read assembled ATA source: {error}") from error

    required = re.compile(
        r"^\s*#\s*define\s+ATA_IO_WAIT\(\)\s+"
        r"KeStallExecutionProcessor\(1\)\s*$", re.MULTILINE)
    if required.search(text) is None:
        raise ValueError(
            "ATA_IO_WAIT must retain an elapsed guest delay through "
            "KeStallExecutionProcessor(1); port reads alone consume zero "
            "elapsed guest delay in xemu")
    if "#define ATA_IO_WAIT(Ctx)" in text:
        raise ValueError(
            "context-based ATA_IO_WAIT may replace the elapsed guest delay "
            "with zero-time emulator port reads")

    required_header_tokens = (
        "PataDeviceSelectWait",
        "NXK_EXPERIMENT_ATA_FORCE_SAFE",
        "NXK_EXPERIMENT_ATA_FORCE_ALL",
        "NxkQemuAtaDiskTargets",
        "ATA_IO_WAIT();",
    )
    for token in required_header_tokens:
        if token not in text:
            raise ValueError(f"missing QEMU ATA settle guard: {token}")
    helper = text[text.index("PataDeviceSelectWait"):]
    helper = helper[:helper.index("#else")]
    if helper.count("READ_PORT_UCHAR(ChanData->Regs.Control)") != 4:
        raise ValueError("QEMU fast settle must perform exactly four status reads")
    safe = helper.find("NXK_EXPERIMENT_ATA_FORCE_SAFE")
    qemu_present = helper.find("!NxkQemuAtaDiskTargets")
    force_all = helper.find("NXK_EXPERIMENT_ATA_FORCE_ALL")
    target = helper.find("NxkQemuAtaDiskTargets &")
    delay = helper.find("ATA_IO_WAIT();")
    if not (0 <= safe < qemu_present < force_all < target < delay):
        raise ValueError(
            "safe override and positive QEMU detection must dominate the "
            "all-device override and target gate before the delayed fallback")

    required_identify_tokens = (
        "AtaDetectQemuDisk",
        "DeviceType != DEV_ATA",
        'strstr(ModelNumber, "QEMU")',
        "NxkQemuAtaDiskTargets",
    )
    for token in required_identify_tokens:
        if token not in identify_text:
            raise ValueError(f"missing IDENTIFY QEMU HDD gate: {token}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", required=True, type=Path)
    args = parser.parse_args()
    try:
        check(args.source_root)
    except ValueError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print("PASS: ATA settle retains its delay and limits acceleration to "
          "IDENTIFY-proven QEMU HDD targets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
