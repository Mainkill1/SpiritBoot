# SPDX-License-Identifier: MIT
"""Compare owned PE code against snapshot mappings; emit scalar metadata only."""
import argparse, hashlib, json, struct
from pathlib import Path

ROM_BASE=0xff000000
ROM_OVERLAY_BASE=0xfffff000
EXPECTED={'ram':'8d052ca631542918f234d7acf5896d609bfe043bc362b4bcaba4b833f17a1090','flash':'add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296','image':'2089f56cb374b73212eb05bf746f3f6230e4bb1e727be2f8be08b2c000783bcc'}
def digest(data):return hashlib.sha256(data).hexdigest()
def u32(data,offset):
    if offset<0 or offset+4>len(data):raise ValueError('Out-of-range scalar read')
    return struct.unpack_from('<I',data,offset)[0]
def translate(ram,cr3,va):
    if not 0<=va<2**32 or not 0<=cr3<2**32:raise ValueError('Expected 32-bit addressing')
    pde=u32(ram,(cr3&0xfffff000)+((va>>22)&1023)*4)
    if not pde&1:raise ValueError('Nonpresent PDE')
    if pde&0x80:
        if pde&0x001fe000:raise ValueError('Unsupported extended large-page address')
        return (pde&0xffc00000)|(va&0x3fffff)
    pte=u32(ram,(pde&0xfffff000)+((va>>12)&1023)*4)
    if not pte&1:raise ValueError('Nonpresent PTE')
    return (pte&0xfffff000)|(va&4095)
def backing(ram,flash,physical,size):
    if size<0 or (physical&4095)+size>4096:raise ValueError('Read must stay within one physical page')
    if 0<=physical and physical+size<=len(ram):return ram[physical:physical+size],'ram'
    if ROM_BASE<=physical and physical+size<=ROM_OVERLAY_BASE:
        if len(flash)!=512*1024:raise ValueError('Expected pinned 512 KiB ROM')
        offset=(physical-ROM_BASE)%len(flash)
        if offset+size>len(flash):raise ValueError('Read crosses ROM mirror')
        return flash[offset:offset+size],'rom'
    raise ValueError('Unknown physical backing or possible MCPX overlay')
def sections(image):
    if image[:2]!=b'MZ':raise ValueError('Missing DOS header')
    pe=u32(image,0x3c)
    if image[pe:pe+4]!=b'PE\0\0':raise ValueError('Missing PE signature')
    count=struct.unpack_from('<H',image,pe+6)[0];optional=struct.unpack_from('<H',image,pe+20)[0]
    if struct.unpack_from('<H',image,pe+24)[0]!=0x10b:raise ValueError('Expected PE32')
    base=u32(image,pe+24+28);table=pe+24+optional
    for n in range(count):
        p=table+n*40;name=image[p:p+8].rstrip(b'\0').decode('ascii')
        virtual_size,rva,raw_size,raw=struct.unpack_from('<IIII',image,p+8)
        if name not in ('.text','PAGE'):continue
        if virtual_size>raw_size or raw+virtual_size>len(image):raise ValueError('Code exceeds file backing')
        yield name,base+rva,image[raw:raw+virtual_size]
def compare(ram,flash,image,cr3=0xf000):
    hashes={k:digest(v)for k,v in [('ram',ram),('flash',flash),('image',image)]}
    if hashes!=EXPECTED:raise ValueError('Inputs differ from pinned snapshot/owned build')
    result={'sha256':hashes,'cr3':hex(cr3),'sections':[],'mismatches':[]}
    startup_patch=False
    for name,va,data in sections(image):
        if va&4095:raise ValueError('Expected page-aligned code section')
        mapped=bytearray();pages=[]
        for offset in range(0,len(data),4096):
            physical=translate(ram,cr3,va+offset);chunk,kind=backing(ram,flash,physical,min(4096,len(data)-offset))
            pages.append({'virtual_page':hex(va+offset),'physical_page':hex(physical),'backing':kind});mapped.extend(chunk)
        mismatches=[i for i,(a,b)in enumerate(zip(data,mapped))if a!=b]
        if name=='.text':
            patch=0x84002600-va
            # Owned initialization replaces the single-byte return with NOP.
            startup_patch=(mismatches==[patch] and data[patch]==0xc3 and mapped[patch]==0x90)
        result['sections'].append({'name':name,'virtual_start':hex(va),'bytes':len(data),'file_sha256':digest(data),'mapped_sha256':digest(mapped),'mismatch_bytes':len(mismatches),'rom_pages':sum(p['backing']=='rom'for p in pages),'ram_pages':sum(p['backing']=='ram'for p in pages),'pages':pages})
        for i in mismatches:result['mismatches'].append({'section':name,'virtual_address':hex(va+i),'physical_address':hex(translate(ram,cr3,va+i)),'section_offset':hex(i)})
    result['expected_owned_prefetch_entry_enablement']=startup_patch
    result['limitations']=['Preserved RAM page tables plus exact known flash, not a fresh live code dump.','Rejects physical addresses in the possible MCPX overlay page.','No code bytes or RAM payload are emitted. One differing byte does not by itself prove unchanged instruction boundaries.']
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('ram',type=Path);p.add_argument('flash',type=Path);p.add_argument('image',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    text=json.dumps(compare(a.ram.read_bytes(),a.flash.read_bytes(),a.image.read_bytes()),indent=2)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')
