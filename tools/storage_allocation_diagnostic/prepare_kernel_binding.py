# SPDX-License-Identifier: GPL-2.0-only
"""Bind the selected, existing PE images; inspect files only, never a target."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

UNSTRIPPED_SHA = "35631dbff4499ccb6d45624c6b3c9e61146b75796be1ee1d63580b0499b35c5f"
FINAL_SHA = "7fba000d149eef7af5ca6145e7fffce6314424bab671c85c3aab901eb575e3f8"


def image_reader(data):
    if data[:2] != b"MZ":
        raise ValueError("PE image required")
    pe = struct.unpack_from("<I", data, 60)[0]
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("PE signature required")
    opt = pe + 24
    if struct.unpack_from("<H", data, opt)[0] != 0x10b:
        raise ValueError("PE32 required")
    base = struct.unpack_from("<I", data, opt + 28)[0]
    start = opt + struct.unpack_from("<H", data, pe + 20)[0]
    sections = [struct.unpack_from("<IIII", data, start + i * 40 + 8)
                for i in range(struct.unpack_from("<H", data, pe + 6)[0])]

    def read(address, count):
        rva = address - base
        for _, va, size, raw in sections:
            if va <= rva and rva + count <= va + size:
                offset = raw + rva - va
                result = data[offset:offset + count]
                if len(result) == count:
                    return result
        raise ValueError("unbacked address")
    return base, read


def prepare(unstripped, final, transport):
    old, selected = Path(unstripped).read_bytes(), Path(final).read_bytes()
    if hashlib.sha256(old).hexdigest() != UNSTRIPPED_SHA or hashlib.sha256(selected).hexdigest() != FINAL_SHA:
        raise ValueError("selected reference kernel hash mismatch")
    base, read = image_reader(old)
    final_base, final_read = image_reader(selected)
    if final_base != base:
        raise ValueError("PE bases differ")
    sites = [dict(name="ExAllocatePoolWithTag", symbol="_ExAllocatePoolWithTag@12",
                  address=0x84011824, argument_bytes=12, call="allocate"),
             dict(name="ExFreePoolWithTag", symbol="_ExFreePoolWithTag@8",
                  address=0x84011fe8, argument_bytes=8, call="free"),
             dict(name="KeGetCurrentThread", symbol="_KeGetCurrentThread@0",
                  address=0x8401f530, argument_bytes=0, call="proof-only"),
             dict(name="NxkIdeIsr", symbol="_NxkIdeIsr@8",
                  address=0x8402f8a4, argument_bytes=8, call="proof-only")]
    for site in sites:
        raw = read(site["address"], 32)
        if raw != final_read(site["address"], 32):
            raise ValueError("selected final instruction bytes differ")
        site["entry_bytes"] = raw.hex()
    if read(0x8401f530, 6).hex() != "a124f1dfffc3":
        raise ValueError("compiled thread reader no longer matches")
    if read(0x8402f8b9, 6).hex() != "ff05ac870684":
        raise ValueError("compiled ISR increment operand no longer matches")
    return dict(schema_version=1, reference_tree="7e891ec86f42b1313e5cd3453347836ac451ba79",
                unstripped_sha256=UNSTRIPPED_SHA, final_sha256=FINAL_SHA, image_base=base,
                current_thread_address=0xffdff124, service_count_address=0x840687ac,
                service_count_field_offset=172, sites=sites,
                transport_sha256=hashlib.sha256(Path(transport).read_bytes()).hexdigest(),
                scope="local file binding only; ownership/route/native coverage unqualified")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("unstripped", type=Path)
    parser.add_argument("final", type=Path)
    parser.add_argument("transport", type=Path)
    args = parser.parse_args()
    print(json.dumps(prepare(args.unstripped, args.final, args.transport), indent=2))
