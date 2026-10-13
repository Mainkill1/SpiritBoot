#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare exact built firmware image backing; verify ROM CRCs and DES constants.

Only reads artifacts. Permanent image RAM is static layout accounting, not a
runtime available-memory measurement. Requires public source/build directories.
"""
from pathlib import Path
import argparse,struct,json,lzma,hashlib,subprocess,zlib,re
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',type=Path,required=True)
parser.add_argument('--candidate',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
roots={'baseline':args.baseline,'candidate':args.candidate}
result={}
for label,root in roots.items():
 manifest=json.loads((root/'build.json').read_text())
 work=root/Path(manifest['build_directory']).parent.name; build=work/'build'
 assert work.is_dir(), 'build manifest work directory missing'
 pebytes=(build/'ntoskrnl/xboxkrnl.exe').read_bytes(); off=struct.unpack_from('<I',pebytes,60)[0]; opt=off+24
 count=struct.unpack_from('<H',pebytes,off+6)[0]; optsz=struct.unpack_from('<H',pebytes,off+20)[0]
 image_size,headers=struct.unpack_from('<II',pebytes,opt+56)
 sections=[]
 for i in range(count):
  sh=opt+optsz+40*i;name=pebytes[sh:sh+8].rstrip(b'\0').decode();size,rva,raw,raw_off=struct.unpack_from('<IIII',pebytes,sh+8);flags=struct.unpack_from('<I',pebytes,sh+36)[0]
  sections.append(dict(name=name,rva=rva,virtual_bytes=size,raw_bytes=raw,pages=(max(size,raw)+4095)//4096,flags=hex(flags),discardable=bool(flags&0x02000000),writable=bool(flags&0x80000000)))
 symbols={}
 nm=subprocess.check_output(['nm','--no-sort',str(build/'boot/nxldr/nxldr.elf')],text=True)
 for line in nm.splitlines():
  fields=line.split()
  if len(fields)==3:symbols[fields[2]]=int(fields[0],16)
 flash=(root/'flash.bin').read_bytes()
 assert hashlib.sha256(flash).hexdigest()==manifest['flash_sha256'], 'flash differs from manifest'
 payload=symbols['KernelPayloadOffset'];magic,csize,dsize=struct.unpack_from('<III',flash,payload)
 assert magic==0x5249584e
 prepared=lzma.decompress(flash[payload+12:payload+12+csize]);assert len(prepared)==dsize==image_size
 magic,version,nspans,flashsize=struct.unpack_from('<IIII',prepared,0x800);assert magic==0x5052584e and version==1 and flashsize==len(flash)
 spans=[]
 for i in range(nspans):
  rva,pages,physical,crc=struct.unpack_from('<IIII',prepared,0x810+16*i)
  assert zlib.crc32(flash[physical-0xff000000:physical-0xff000000+pages*4096])==crc
  spans.append(dict(rva=rva,pages=pages,physical=hex(physical),crc32=hex(crc)))
 ropages=sum(x['pages'] for x in spans);discardpages=sum(s['pages'] for s in sections if s['discardable'] or s['name']=='INIT')
 rostart=min(int(x['physical'],16)-0xff000000 for x in spans)
 syms={}
 nm=subprocess.check_output(['nm','-n',str(build/'ntoskrnl/xboxkrnl.unstripped.exe')],text=True)
 for line in nm.splitlines():
  fields=line.split()
  if len(fields)==3 and ('Des' in fields[2] or 'SHA1' in fields[2] or 'PrefetchMemoryNonTemporal' in fields[2]):syms[fields[2]]=fields[0]
 result[label]=dict(source_tree=manifest['source_tree'],flash_sha256=hashlib.sha256(flash).hexdigest(),flash_bytes=len(flash),kernel_pe_bytes=len(pebytes),image_size=image_size,image_pages=image_size//4096,headers=headers,sections=sections,rom_spans=spans,rom_pages=ropages,discard_pages=discardpages,permanent_image_RAM_pages=image_size//4096-ropages-discardpages,compressed_payload_bytes=csize+12,rom_start=rostart,payload_offset=payload,payload_capacity=rostart-payload,payload_free=rostart-payload-csize-12,symbols=syms)
 current=result[label]
 current['loader_bin_sha256']=hashlib.sha256((build/'boot/nxldr/nxldr.bin').read_bytes()).hexdigest()
 boot=(work/'source/boot/nxldr/boot-layout.h').read_text()
 warm=(work/'source/boot/nxldr/warm-handoff.h').read_text()
 workspace=int(re.search(r'#define NXBL_RETIRED_BOOT_PAGES (\d+)',boot)[1])
 current['warm_stage_required_pages']=ropages+discardpages+workspace
 current['warm_stage_capacity_pages']=int(re.search(r'#define PM_MAX_STAGES (\d+)u',warm)[1])
 if '_DesSp' in syms:
  source=(work/'source/ntoskrnl/xb/crypto.c').read_text()
  table=re.search(r'static const ULONG DesSp\[8\]\[64\] = \{(.*?)\n\};',source,re.S)
  words=[int(v,16) for v in re.findall(r'0x[0-9A-Fa-f]+',table[1])]
  assert len(words)==512
  rva=int(syms['_DesSp'],16)-0x84000000
  span=next(x for x in spans if x['rva']<=rva and rva+2048<=x['rva']+4096*x['pages'])
  physical=int(span['physical'],16)+rva-span['rva'];offset=physical-0xff000000
  contents=flash[offset:offset+2048]
  assert contents==struct.pack('<512I',*words), 'DES table differs from source'
  current['DesSp']=dict(virtual_start=hex(rva+0x84000000),virtual_end=hex(rva+0x84000000+2048),physical_start=hex(physical),physical_end=hex(physical+2048),bytes=2048,sha256=hashlib.sha256(contents).hexdigest(),backing='ROM',source_bytes_verified=True)
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(result,indent=2)+'\n')
print('Verified build identities, image layouts, ROM CRCs and DES table bytes:',args.output)
