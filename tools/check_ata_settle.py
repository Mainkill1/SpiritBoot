#!/usr/bin/env python3
"""Validate safe-default and explicitly enabled ATA select settle paths."""

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
        "NXK_EXPERIMENT_ATA_FORCE_ALL",
        "ATA_IO_WAIT();",
    )
    for token in required_header_tokens:
        if token not in text:
            raise ValueError(f"missing explicit ATA settle guard: {token}")
    helper = text[text.index("PataDeviceSelectWait"):]
    helper = helper[:helper.index("#else")]
    if helper.count("READ_PORT_UCHAR(ChanData->Regs.Control)") != 4:
        raise ValueError(
            "the explicit ATA fast path must perform exactly four status reads")
    force_all = helper.find("NXK_EXPERIMENT_ATA_FORCE_ALL")
    delay = helper.find("ATA_IO_WAIT();")
    if not (0 <= force_all < delay):
        raise ValueError(
            "the explicit all-device flag must be checked before the delayed "
            "default fallback")
    if "NxkQemuAtaDiskTargets" in helper or "ATA_QEMU_HDD" in helper:
        raise ValueError(
            "the ATA fast path must not automatically activate from QEMU "
            "detection; it requires the explicit advanced setting")

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
    print("PASS: ATA settle defaults to a real delay and acceleration requires "
          "the explicit advanced all-device setting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
