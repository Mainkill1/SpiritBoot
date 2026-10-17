#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise and inspect the public kernel-contract patch.

The host C harness executes the actual PCI adapter postimage against an
instrumented port/lock boundary. It does not qualify native x86 execution.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / "patches/roswell/0137-xbox-public-kernel-contracts.patch"
FIXTURE = ROOT / "tests/host/fixtures/kernel-public-contracts"
FILES = {
    "pci.c": "ntoskrnl/xb/pci.c",
    "interrupt.c": "ntoskrnl/xb/interrupt.c",
    "ordinals.map": "ntoskrnl/xb/ordinals.map",
    "xbe.c": "ntoskrnl/xb/xbe.c",
}


def function(text, name):
    """Extract exactly one complete named C function."""
    hits = list(re.finditer(r"^" + re.escape(name) + r"\s*\([^;{}]*?\)\s*\{", text, re.M))
    if len(hits) != 1:
        raise ValueError("expected exactly one definition: " + name)
    hit = hits[0]
    start = text.rfind("\n\n", 0, hit.start()) + 2
    opening = text.index("{", hit.start())
    depth, end = 1, opening + 1
    while depth:
        if end >= len(text):
            raise ValueError("unbalanced production function: " + name)
        depth += (text[end] == "{") - (text[end] == "}")
        end += 1
    return text[start:end] + "\n"


def patch_postimages():
    result = {name: [] for name in FILES}
    wanted = {path: name for name, path in FILES.items()}
    current = None
    for line in PATCH.read_text().splitlines():
        if line.startswith("+++ b/"):
            current = wanted.get(line[6:])
        elif line.startswith("--- "):
            current = None
        elif current and line.startswith((" ", "+")) and not line.startswith("+++"):
            result[current].append(line[1:])
    return {name: "\n".join(lines) + "\n" for name, lines in result.items()}


def production_sources(source_root=None):
    if source_root is None:
        sources = patch_postimages()
        sources["pci-address.c"] = (FIXTURE / "baseline-functions.c").read_text()
        sources["_patch"] = PATCH.read_text()
        return sources
    root = Path(source_root)
    sources = {name: (root / path).read_text() for name, path in FILES.items()}
    sources["pci-address.c"] = sources["pci.c"]
    sources["_patch"] = ""
    sources["ketypes.h"] = (root / "sdk/include/ndk/i386/ketypes.h").read_text()
    return sources


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_static_contracts(sources):
    interrupt = function(sources["interrupt.c"], "XeKeRaiseIrqlToSynchLevel")
    interrupt_code = re.sub(r"/\*.*?\*/", "", interrupt, flags=re.S)
    require("KeRaiseIrql(CLOCK_LEVEL, &OldIrql)" in interrupt,
            "export-only wrapper must raise to CLOCK_LEVEL")
    require("SYNCH_LEVEL" not in interrupt_code,
            "export-only wrapper must not inherit internal SYNCH_LEVEL")
    ordinal = [line for line in sources["ordinals.map"].splitlines()
               if re.match(r"\s*130\s+", line)]
    require(len(ordinal) == 1 and "XeKeRaiseIrqlToSynchLevel" in ordinal[0],
            "ordinal 130 must map exactly once to the export-only wrapper")

    invalid = function(sources["xbe.c"], "IoInvalidDeviceRequest")
    require("Request->IoStatus.Status = STATUS_INVALID_DEVICE_REQUEST;" in invalid,
            "IoInvalidDeviceRequest must publish failure status")
    require("IoStatus.Information" not in invalid,
            "IoInvalidDeviceRequest must preserve IoStatus.Information")
    require(invalid.count("IofCompleteRequest(Request, IO_NO_INCREMENT);") == 1,
            "IoInvalidDeviceRequest must complete exactly once")
    require(invalid.rstrip().endswith("return STATUS_INVALID_DEVICE_REQUEST;\n}"),
            "IoInvalidDeviceRequest must return the published failure status")

    pci_export = function(sources["xbe.c"], "HalReadWritePCISpace")
    require(pci_export.count(
        "PciCfgReadWriteBuffer(BusNumber, SlotNumber, RegisterNumber,\n"
        "                          Buffer, Length, WritePCISpace);") == 1 and
        "HalGetBusDataByOffset" not in pci_export and
        "HalSetBusDataByOffset" not in pci_export,
        "HalReadWritePCISpace must route once to the direct PCI adapter")

    pci = sources["pci.c"]
    for token in ("ExAllocatePool", "ExAllocatePoolWithTag", "malloc(", "calloc("):
        require(token not in pci, "PCI adapter must not introduce allocation")
    require(not re.search(r"\bstatic\s+[^;\n]*\b(?:KSPIN_LOCK|LOCK)\b", pci),
            "PCI adapter must not introduce a persistent lock")
    require("UCHAR Bus = (UCHAR)BusNumber;" in pci and
            "Slot.u.bits.Reserved" not in pci and
            "BusNumber >" not in pci and
            "RegisterNumber >=" not in pci and
            "Length > 0x100" not in pci,
            "PCI adapter must preserve native 8-bit wrapping and ignore reserved slot bits")
    adapter = function(pci, "PciCfgReadWriteBuffer")
    require(adapter.count("KeAcquireSpinLockAtDpcLevel(&HalpPCIConfigLock);") == 1,
            "PCI adapter must use one shared HAL lock acquisition")
    require(adapter.count("KeReleaseSpinLock(&HalpPCIConfigLock, OldIrql);") == 1,
            "PCI adapter must restore IRQL through one shared HAL lock release")
    require("WRITE_PORT_ULONG((PULONG)PCI_CFG_ADDR, 0);" in adapter,
            "PCI adapter must clear CF8 before releasing the shared lock")
    require("RtlCopyMemory(&Value, Bytes, Width);" in adapter,
            "PCI writes must use exact-width caller bytes without unaligned loads")

    if sources.get("_patch"):
        changed = set(re.findall(r"^\+\+\+ b/(.+)$", sources["_patch"], re.M))
        require(not any(path.startswith("sdk/include/ndk/") for path in changed),
                "patch must leave internal SYNCH_LEVEL policy headers untouched")
    else:
        require("#define SYNCH_LEVEL             DISPATCH_LEVEL" in sources["ketypes.h"],
                "assembled UP kernel must retain its internal SYNCH_LEVEL policy")


def behavior_source(sources):
    functions = [function(sources["pci-address.c"], "PciCfgAddress")]
    functions += [function(sources["pci.c"], name) for name in (
        "PciCfgAccessBlocked", "PciCfgTransferWidth", "PciCfgReadWriteBuffer")]
    return ((FIXTURE / "shim.h").read_text() + "\n" + "\n".join(functions) +
            "\n" + (FIXTURE / "cases.c").read_text())


def run_check(source_root=None, output=None):
    sources = production_sources(source_root)
    validate_static_contracts(sources)
    source_text = behavior_source(sources)
    with tempfile.TemporaryDirectory(prefix="kernel-public-contracts-") as temporary:
        directory = Path(temporary)
        source, binary = directory / "check.c", directory / "check"
        source.write_text(source_text)
        subprocess.run([
            "cc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-Wno-int-to-pointer-cast",
            "-fsanitize=address,undefined", "-fno-omit-frame-pointer",
            str(source), "-o", str(binary),
        ], check=True)
        run = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
        match = re.search(r"checks=(\d+) cells=(\d+)", run.stdout)
        if not match:
            raise ValueError("host behavior checker did not report its coverage")
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
            (output / "production-pci-check.c").write_text(source_text)
    bodies = {
        name: function(sources[path], name)
        for name, path in (
            ("XeKeRaiseIrqlToSynchLevel", "interrupt.c"),
            ("IoInvalidDeviceRequest", "xbe.c"),
            ("PciCfgReadWriteBuffer", "pci.c"),
        )
    }
    bodies["PciCfgAddress"] = function(sources["pci-address.c"], "PciCfgAddress")
    return {
        "source_mode": "assembled-source" if source_root else "patch-postimage",
        "pci_transfer_cells": int(match.group(2)),
        "behavior_checks": int(match.group(1)),
        "function_sha256": {name: hashlib.sha256(body.encode()).hexdigest()
                            for name, body in bodies.items()},
        "native_execution_qualified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    print(json.dumps(run_check(args.source_root, args.output), sort_keys=True))


if __name__ == "__main__":
    main()
