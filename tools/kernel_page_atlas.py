"""Offline exact-image page attribution using the existing bounded TB capture.

Weights are TB-entry instruction weights, not calls, CPU time, instruction-byte
coverage, or proof that unobserved code can be removed. No firmware is modified.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from kernel_hotpaths import parse_capture


PAGE = 4096


def sha(data):
    return hashlib.sha256(data).hexdigest()


def integer(value):
    if type(value) is not int or not 0 <= value <= 0xffffffff:
        raise ValueError("invalid image integer")
    return value


def pe_layout(data):
    try:
        offset = struct.unpack_from("<I", data, 60)[0]
        optional = offset + 24
        if data[:2] != b"MZ" or data[offset:offset+4] != b"PE\0\0":
            raise ValueError("not a PE image")
        machine, count = struct.unpack_from("<HH", data, offset+4)
        size = struct.unpack_from("<H", data, offset+20)[0]
        if machine != 0x14c or size < 96 or optional+size > len(data):
            raise ValueError("requires a complete i386 PE32 image")
        if struct.unpack_from("<H", data, optional)[0] != 0x10b:
            raise ValueError("requires PE32")
        base, alignment = struct.unpack_from("<II", data, optional+28)
        image_size, headers = struct.unpack_from("<II", data, optional+56)
        if alignment != PAGE or base % PAGE or not 0 < headers <= image_size:
            raise ValueError("unsupported image alignment/header size")
        sections = {}
        for index in range(count):
            address = optional + size + index*40
            name = data[address:address+8].rstrip(b"\0").decode("ascii")
            length, rva = struct.unpack_from("<II", data, address+8)
            flags = struct.unpack_from("<I", data, address+36)[0]
            if name in sections or rva % PAGE or rva+length > image_size:
                raise ValueError("invalid PE section")
            sections[name] = (base+rva, length, flags)
        return base, headers, sections
    except (struct.error, UnicodeDecodeError) as error:
        raise ValueError("truncated or malformed PE") from error


def identity_matches(value, identity):
    for key, expected in identity.items():
        if value.get(key) != expected:
            raise ValueError(f"mismatched {key}")


def build_atlas(inventory, build, kernel, shipped, flash, captures):
    if inventory.get("schema") != 2 or build.get("status") not in ("built", "complete"):
        raise ValueError("requires schema2 compiler inventory and completed build")
    identity = dict(source_tree=build["source_tree"], pe_sha256=sha(kernel),
                    flash_sha256=sha(flash))
    if not re.fullmatch(r"[a-f0-9]{40}", identity["source_tree"]):
        raise ValueError("invalid source tree")
    if build.get("flash_sha256") != identity["flash_sha256"]:
        raise ValueError("flash differs from completed build")
    identity_matches(inventory, identity)
    if inventory.get("shipped_pe_sha256") != sha(shipped):
        raise ValueError("mismatched shipped PE identity")
    base, _, pe_sections = pe_layout(kernel)
    shipped_base, headers, shipped_sections = pe_layout(shipped)
    if shipped_base != base:
        raise ValueError("shipped image base differs from compiler image")
    sections = [dict(name="PE headers", start=base, virtual_bytes=headers,
                     flags=0, executable=False, discardable=False)]
    names = set()
    for section in inventory["sections"]:
        name = section["name"]
        start, length = integer(section["start"]), integer(section["virtual_bytes"])
        compiler = pe_sections.get(name)
        if name in names or compiler is None or compiler[:2] != (start, length):
            raise ValueError("section ledger differs from exact PE")
        names.add(name)
        flags = integer(section["flags"])
        if shipped_sections.get(name) != (start, length, flags):
            raise ValueError("section ledger differs from shipped PE geometry/attributes")
        if (bool(flags & 0x20000000) != section["executable"] or
                bool(flags & 0x02000000) != section["discardable"]):
            raise ValueError("inconsistent section attributes")
        sections.append(section)
    if names != set(shipped_sections):
        raise ValueError("section ledger omits a shipped section")
    claims = inventory["functions_and_input_extents"] + inventory["sizeof_proved_tables"]
    extents = {}
    aliases = {}
    for claim in claims:
        start, end = integer(claim["va"]), integer(claim["extent_end"])
        length = integer(claim["bytes"])
        section = next((s for s in sections if s["name"] == claim["section"]), None)
        if (section is None or end-start != length or
                not section["start"] <= start <= end <= section["start"]+section["virtual_bytes"]):
            raise ValueError("extent outside its section or inconsistent length")
        if "compiler_extent_bytes" in claim:
            if claim["compiler_extent_bytes"] != length or claim.get("length_kind") != "COFF compiler input-section extent":
                raise ValueError("requires certified compiler extent, not inferred symbol span")
        elif claim.get("sizeof_bytes") != length:
            raise ValueError("data claims require independently proved sizeof")
        symbols = set(claim.get("symbols", [])) | {claim["name"]}
        aliases.setdefault(start, set()).update(symbols)
        if length:
            key = (claim["section"], start, end)
            entry = extents.setdefault(key, dict(symbols=set(), sources=set(), confidence=set()))
            entry["symbols"].update(symbols)
            entry["sources"].update(claim.get("source_definition_candidates", []))
            entry["confidence"].add(claim.get("source_attribution_confidence", "supplied extent ledger"))
    pages = []
    for section in sections:
        first, length = section["start"], section["virtual_bytes"]
        for start in range(first, first+length, PAGE):
            content_end = min(start+PAGE, first+length)
            owners, intervals = [], []
            for (name, a, z), detail in sorted(extents.items()):
                overlap = min(content_end, z)-max(start, a)
                if name != section["name"] or overlap <= 0:
                    continue
                intervals.append((max(start, a), min(content_end, z)))
                owners.append(dict(start=a, end=z, overlap_bytes=overlap,
                                   symbols=sorted(detail["symbols"] | aliases[a]),
                                   sources=sorted(detail["sources"]),
                                   confidence=sorted(detail["confidence"])))
            known, last = 0, start
            for a, z in sorted(intervals):
                known += max(0, z-max(a, last))
                last = max(last, z)
            padding = start+PAGE-content_end
            flags = section["flags"]
            placement = ("ineligible-discardable" if section["discardable"] else
                         "ineligible-mutable" if flags & 0x80000000 else
                         "requires-ownership-and-access-qualification")
            pages.append(dict(rva=start-base, va=start, section=section["name"],
                              resident=not section["discardable"],
                              physical_backing="unknown", owners=owners,
                              known_union_bytes=known, unknown_bytes=content_end-start-known,
                              tail_padding_bytes=padding, known_fraction=known/PAGE,
                              executable=section["executable"], placement=placement,
                              phase_weights={}))
    by_va = {page["va"]: page for page in pages}
    if len(by_va) != len(pages):
        raise ValueError("overlapping image pages")
    coverage, seen = [], set()
    for meta, text in captures:
        identity_matches(meta, identity)
        if meta.get("schema") != 1 or meta.get("capture_sha256") != sha(text.encode()):
            raise ValueError("capture bytes differ from identity sidecar")
        if meta["capture_sha256"] in seen:
            raise ValueError("duplicate capture would double-count work")
        seen.add(meta["capture_sha256"])
        if not re.fullmatch(r"[a-f0-9]{64}", meta.get("xemu_sha256", "")):
            raise ValueError("requires xemu executable identity")
        phase, window = meta.get("phase"), meta.get("window", {})
        if phase == "whole-process":
            if window != dict(kind="whole-process"):
                raise ValueError("invalid whole-process boundary")
        elif phase in ("boot", "title"):
            if (window.get("kind") != "bounded-recording" or
                    not window.get("start") or not window.get("end") or
                    not re.fullmatch(r"[a-f0-9]{64}", window.get("evidence_sha256", ""))):
                raise ValueError("phase requires explicit recording-boundary evidence")
        else:
            raise ValueError("unsupported recording phase")
        rows, footer = parse_capture(text)
        if phase != "whole-process":
            header = json.loads(next(line for line in text.splitlines() if line.strip()))
            if header.get("phase") != phase or header.get("window") != window:
                raise ValueError("producer did not declare the bounded recording phase")
        total, outside = footer["untracked_weight"], 0
        for row in rows:
            weight = row["instructions"]*row["executions"]
            total += weight
            page = by_va.get(int(row["pc"], 16) // PAGE * PAGE)
            if page is None or not page["va"] <= int(row["pc"], 16) < page["va"]+PAGE-page["tail_padding_bytes"]:
                outside += weight
            else:
                page["phase_weights"][phase] = page["phase_weights"].get(phase, 0)+weight
        coverage.append(dict(phase=phase, window=window,
                             capture_sha256=meta["capture_sha256"], xemu_sha256=meta["xemu_sha256"],
                             total_weight=total, outside_image_weight=outside,
                             untracked_weight=footer["untracked_weight"],
                             dropped_translations=footer["dropped_translations"],
                             complete_coverage=not footer["dropped_translations"]))
    hot = [p for p in pages if p["resident"] and p["executable"] and p["phase_weights"].get("title", 0)]
    candidate = max(hot, key=lambda p: p["phase_weights"]["title"]) if hot else None
    return dict(schema=1, identity={**identity, "shipped_pe_sha256": sha(shipped)},
                page_bytes=PAGE, pages=pages, coverage=coverage,
                candidate_hot_page=candidate["rva"] if candidate else None,
                candidate_cold_page=None,
                confidence_limits="No title phase evidence means no gameplay hot-page claim. "
                "Zero observations never establish a safe cold page. Physical backing is unknown "
                "without a paired live mapping census. Producer-declared phase boundaries are "
                "recording attestations, not guest-progress proof. Extents come from the supplied compiler "
                "ledger; source/assembly/data gaps remain unknown. TB weights belong to their "
                "entry page, not all spanned bytes, calls, exclusive CPU time or retired instructions.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("inventory", "build", "kernel", "shipped-kernel", "flash", "output"):
        parser.add_argument("--"+option, type=Path, required=True)
    parser.add_argument("--capture", type=Path, action="append", default=[])
    args = parser.parse_args()
    try:
        captures = []
        for path in args.capture:
            meta = json.loads(path.read_text())
            captures.append((meta, (path.parent/meta["capture"]).read_bytes().decode("utf-8")))
        report = build_atlas(json.loads(args.inventory.read_text()),
                             json.loads(args.build.read_text()), args.kernel.read_bytes(),
                             args.shipped_kernel.read_bytes(), args.flash.read_bytes(), captures)
        with args.output.open("x") as stream:
            json.dump(report, stream, indent=2)
            stream.write("\n")
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.exit(2, f"page atlas rejected: {error}\n")


if __name__ == "__main__":
    main()
