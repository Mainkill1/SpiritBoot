#!/usr/bin/env python3
"""Generate exact function/code-entry addresses from an unstripped PE/COFF kernel."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


SECTION_RE = re.compile(
    r"^\s*(\d+)\s+(\S+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+"
    r"[0-9a-fA-F]+\s+[0-9a-fA-F]+\s+2\*\*(\d+)$")
SYMBOL_RE = re.compile(
    r"^\[\s*\d+\]\(sec\s+(-?\d+)\).*?\(ty\s+([0-9a-fA-F]+)\)"
    r"\(scl\s+(\d+)\).*?\)\s+0x([0-9a-fA-F]+)\s+(.+)$")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def output(*args: str) -> str:
    return subprocess.check_output(args, text=True, errors="strict")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("kernel", type=Path)
    parser.add_argument("entries", type=Path)
    parser.add_argument("--metadata", type=Path)
    args = parser.parse_args()

    sections: dict[int, tuple[str, int, int]] = {}
    for line in output("objdump", "-h", str(args.kernel)).splitlines():
        match = SECTION_RE.match(line)
        if match:
            index, name, size, vma, _alignment = match.groups()
            sections[int(index) + 1] = (name, int(vma, 16), int(size, 16))
    code_sections = {
        index for index, (name, _vma, _size) in sections.items()
        if name in {".text", "PAGE", "INIT"}
    }
    text_section = next(index for index, item in sections.items()
                        if item[0] == ".text")

    addresses: dict[int, set[str]] = {}
    typed_functions = 0
    assembly_entries = 0
    for line in output("objdump", "-t", str(args.kernel)).splitlines():
        match = SYMBOL_RE.match(line)
        if not match:
            continue
        section, symbol_type, storage_class, offset, name = match.groups()
        section_id = int(section)
        if section_id not in code_sections:
            continue
        is_typed_function = symbol_type == "20"
        is_global_text_entry = (symbol_type == "0" and storage_class == "2" and
                                section_id == text_section)
        if not (is_typed_function or is_global_text_entry):
            continue
        section_name, vma, size = sections[section_id]
        address = vma + int(offset, 16)
        if not (vma <= address < vma + size):
            raise RuntimeError(f"symbol outside {section_name}: {line}")
        addresses.setdefault(address, set()).add(name)
        typed_functions += int(is_typed_function)
        assembly_entries += int(is_global_text_entry)

    required = {
        "_KeDelayExecutionThread@12", "_NxNativeAdapterSubmit",
        "_NxkPageSupplyCanPin", "_NxkPageSupplyPin",
        "_HalpCalibrateStallExecution@0",
    }
    names = {name for aliases in addresses.values() for name in aliases}
    missing = sorted(required - names)
    if missing:
        raise RuntimeError(f"missing required function entries: {missing}")
    forbidden = {"SubtractLoop", "_eeprom", "__init_end__", ".l7"}
    present = sorted(forbidden & names)
    if present:
        raise RuntimeError(f"internal/data symbols admitted: {present}")

    args.entries.parent.mkdir(parents=True, exist_ok=True)
    with args.entries.open("w") as stream:
        for address, aliases in sorted(addresses.items()):
            stream.write(f"0x{address:08x} {'|'.join(sorted(aliases))}\n")

    metadata = {
        "schema": 1,
        "kernel": str(args.kernel.resolve()),
        "kernel_sha256": digest(args.kernel),
        "objdump": output("objdump", "--version").splitlines()[0],
        "selection": {
            "typed_functions": "PE/COFF type 0x20 in .text, PAGE, or INIT",
            "assembly_entries": "external storage-class code entries in .text",
            "aliases": "collapsed by virtual address",
        },
        "raw_typed_function_symbols": typed_functions,
        "raw_global_assembly_entry_symbols": assembly_entries,
        "unique_function_entry_addresses": len(addresses),
        "entries_sha256": digest(args.entries),
    }
    metadata_path = args.metadata or args.entries.with_suffix(".metadata.json")
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
