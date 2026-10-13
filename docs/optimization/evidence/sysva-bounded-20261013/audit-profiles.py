#!/usr/bin/env python3
"""Static image RAM accounting for all four build profiles, respecting ROM mode."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

def profile(root):
    d=json.loads((root/'build.json').read_text());flash=(root/'flash.bin').read_bytes()
    assert hashlib.sha256(flash).hexdigest()==d['flash_sha256']
    assert d['status']=='built'
    work=root/Path(d['build_directory']).parent.name;pe=(work/'build/ntoskrnl/xboxkrnl.exe').read_bytes()
    off=struct.unpack_from('<I',pe,60)[0];opt=off+24;size=struct.unpack_from('<I',pe,opt+56)[0]
    count=struct.unpack_from('<H',pe,off+6)[0];optsz=struct.unpack_from('<H',pe,off+20)[0]
    sections=[]
    for i in range(count):
        sh=opt+optsz+40*i;name=pe[sh:sh+8].rstrip(b'\0').decode();vsize,rva,raw=struct.unpack_from('<III',pe,sh+8)
        flags=struct.unpack_from('<I',pe,sh+36)[0]
        sections.append(dict(name=name,virtual_bytes=vsize,rva=rva,raw_bytes=raw,pages=(max(vsize,raw)+4095)//4096,discardable=bool(flags&0x02000000)))
    discard=sum(s['pages'] for s in sections if s['discardable'])
    # The release64 ROM-backed profile is verified separately by the CRC/span
    # audit. Other profiles retain their non-discardable code/data in RAM.
    rom=sum(s['pages'] for s in sections if s['name'] in ['.text','.rdata']) if d['rom_kernel'] else 0
    resident=size//4096-discard-rom
    return dict(variant=d['variant'],memory_mib=d['memory_mib'],source_tree=d['source_tree'],flash_sha256=d['flash_sha256'],
                flash_bytes=len(flash),rom_kernel=d['rom_kernel'],image_bytes=size,discard_pages=discard,
                rom_pages=rom,permanent_image_RAM_pages=resident,permanent_image_RAM_KiB=resident*4,sections=sections)
def main():
    p=argparse.ArgumentParser();p.add_argument('baseline_root',type=Path);p.add_argument('candidate_root',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    result={}
    for name in ['release64','release128','debug64','debug128']:
        result[name]={'baseline':profile(a.baseline_root/('final-'+name)),
                      'candidate':profile(a.candidate_root/('sysva-selected-'+name))}
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    for name,v in result.items():print(name,v['baseline']['permanent_image_RAM_KiB'],'->',v['candidate']['permanent_image_RAM_KiB'],'KiB',v['candidate']['flash_sha256'])
if __name__=='__main__':main()
