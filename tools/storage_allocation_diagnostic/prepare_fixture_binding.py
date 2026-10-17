# SPDX-License-Identifier: GPL-2.0-only
"""Read-only binding of the existing owned fixture object to its selected XBE."""
import hashlib
import json
import struct
from pathlib import Path


def bind(xbe_path, object_path):
    xbe, obj = Path(xbe_path).read_bytes(), Path(object_path).read_bytes()
    if hashlib.sha256(xbe).hexdigest() != "88b287b7555636ba7b78fe3ed2c37bb76a67a446318a8adccb48f6f4fdd44ce9":
        raise ValueError("exact owned selected XBE required")
    if hashlib.sha256(obj).hexdigest() != "621b9c78f57392efa52a6e7715d5a91e56a3db7e5a7153b052419980331c8363":
        raise ValueError("exact owned compiled pilot object required")
    if xbe[:4] != b"XBEH" or struct.unpack_from("<H", obj)[0] != 0x14c:
        raise ValueError("XBE/COFF format differs")
    base = struct.unpack_from("<I", xbe, 0x104)[0]
    count, table = struct.unpack_from("<II", xbe, 0x11c)
    executable = []
    for index in range(count):
        flags, va, virtual_size, raw, raw_size = struct.unpack_from("<5I", xbe, table-base+index*56)
        if flags & 4:
            executable.append((va, xbe[raw:raw+raw_size]))
    sections = struct.unpack_from("<H", obj, 2)[0]
    text = None
    for index in range(sections):
        offset = 20 + index*40
        if obj[offset:offset+8].rstrip(b"\0") == b".text":
            size, raw, reloc = struct.unpack_from("<III", obj, offset+16)
            nreloc = struct.unpack_from("<H", obj, offset+32)[0]
            data = obj[raw:raw+size]
            mask = bytearray(b"\x01"*size)
            for i in range(nreloc):
                at, symbol, kind = struct.unpack_from("<IIH", obj, reloc+i*10)
                if kind not in (6, 20) or at+4 > size:
                    raise ValueError("unsupported owned-object relocation")
                mask[at:at+4] = b"\0"*4
            text = data, mask
    if text is None:
        raise ValueError("owned-object text absent")
    data, mask = text
    runs, beginning = [], None
    for i, value in enumerate(mask+b"\0"):
        if value and beginning is None:
            beginning = i
        elif not value and beginning is not None:
            runs.append((i-beginning, beginning)); beginning=None
    length, anchor = max(runs)
    matches = []
    for va, content in executable:
        start = 0
        while True:
            hit = content.find(data[anchor:anchor+length], start)
            if hit < 0:
                break
            beginning=hit-anchor;start=hit+1
            if beginning >= 0 and beginning+len(data) <= len(content) and all(
                    not mask[i] or data[i] == content[beginning+i] for i in range(len(data))):
                matches.append((va+beginning, content[beginning:beginning+len(data)]))
    if len(matches) != 1:
        raise ValueError("owned pilot object does not match exactly once")
    pilot_base, linked = matches[0]
    # Numeric sites are reviewed from this owned object's _measure symbol and
    # call relocations, not from a commercial title or retained class body.
    sites={"measure_entry":0x8e0,"operation_issue":0xa37,"consumer_verified":0xac0}
    if linked[0xa37:0xa39] != b"\xff\xd0" or linked[0xac0] != 0xe8:
        raise ValueError("owned reviewed instruction sites differ")
    entry=struct.unpack_from("<I",xbe,0x128)[0]^0xa8fc57ab
    def read(va,n):
        for section_va, content in executable:
            if section_va <= va and va+n <= section_va+len(content):
                return content[va-section_va:va-section_va+n]
        raise ValueError("unbacked owned entry")
    return dict(schema_version=1,xbe_sha256=hashlib.sha256(xbe).hexdigest(),
                object_sha256=hashlib.sha256(obj).hexdigest(),image_base=base,entry_address=entry,
                entry_bytes=read(entry,16).hex(),pilot_text_address=pilot_base,
                text_match=dict(nonrelocated_bytes=sum(mask),relocated_bytes=len(mask)-sum(mask),
                                matches=1,semantics="exact full object text match outside COFF relocation words"),
                sites={name:dict(address=pilot_base+offset,bytes=linked[offset:offset+16].hex()) for name,offset in sites.items()},
                operation_count=1024,block_bytes=4096,index_stack_offset=0x6c,
                result_mask_stack_offset=0x58,status_stack_offset=0x5c,iosb_stack_offset=0x88,
                selected_case="small-hdd-read.cold-ish",performance_acceptance_eligible=False,
                scope="owned fixture only; native runtime execution/coverage remains unproved")


if __name__ == "__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("xbe");parser.add_argument("object")
    args=parser.parse_args()
    print(json.dumps(bind(args.xbe,args.object),indent=2))
