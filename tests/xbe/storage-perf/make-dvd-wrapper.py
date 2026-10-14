#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Build a fixed wrapper with an owned recorder and opaque released target.

The original ISO is provenance, never relabeled as the mounted wrapper.
Only public file/directory metadata and the first4096 target bytes are inspected.
Full executable bytes are copied/hashed, not decoded. XISO descriptor facts:
https://xboxdevwiki.net/XDVDFS
"""
import argparse,hashlib,json,pathlib,shutil,struct,subprocess,tempfile

REFERENCES={
 'clean':('8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475',565248,'33a591adbeba2e34173da62327be779ade079aa9961dbfbebda87e4dbab82df9'),
 'performance':('099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33',573440,'d5f57723bdde2539a598bfac9b7c4cf9753a9ed286cc30d072888fb4b10dfb2f')}

def sha(path):
 value=hashlib.sha256()
 with pathlib.Path(path).open('rb') as stream:
  for data in iter(lambda:stream.read(1048576),b''):value.update(data)
 return value.hexdigest()

def inspect_wrapper(path):
 path=pathlib.Path(path);size=path.stat().st_size;files={};visited=set();spans=[]
 with path.open('rb') as stream:
  stream.seek(32*2048);descriptor=stream.read(2048)
  if len(descriptor)!=2048 or descriptor[:20]!=b'MICROSOFT*XBOX*MEDIA' or descriptor[-20:]!=descriptor[:20]:raise ValueError('wrapper XISO descriptor magic differs')
  root_sector,root_bytes=struct.unpack_from('<II',descriptor,20);root_offset=root_sector*2048
  if root_sector<34 or not 0<root_bytes<=1048576 or root_offset+root_bytes>size:raise ValueError('wrapper root extent invalid')
  stream.seek(root_offset);directory=stream.read(root_bytes);pending=[0]
  while pending:
   offset=pending.pop()
   if offset in visited or offset+14>len(directory):raise ValueError('wrapper directory cycle/extent')
   visited.add(offset);left,right,sector,length,attributes,name_bytes=struct.unpack_from('<HHIIBB',directory,offset)
   if not name_bytes or offset+14+name_bytes>len(directory) or attributes&16:raise ValueError('wrapper requires ordinary bounded files')
   name=directory[offset+14:offset+14+name_bytes].decode('ascii')
   if name in files or name not in ('default.xbe','target.xbe'):raise ValueError('wrapper file set differs')
   start=sector*2048;end=start+length
   if not length or start<root_offset+root_bytes or end>size:raise ValueError('wrapper file extent invalid')
   if any(start<b and a<end for a,b in spans):raise ValueError('wrapper file extents overlap')
   spans.append((start,end));stream.seek(start);content=stream.read(length)
   files[name]={'sector':sector,'offset':start,'bytes':length,'sha256':hashlib.sha256(content).hexdigest(),'first4096_sha256':hashlib.sha256(content[:4096]).hexdigest()}
   for pointer in (left,right):
    if pointer:pending.append(pointer*4)
 if set(files)!= {'default.xbe','target.xbe'}:raise ValueError('wrapper must contain both distinct files')
 return {'sector_bytes':2048,'root_sector':root_sector,'root_bytes':root_bytes,'files':files}

def build_wrapper(*,source_iso,source_sha256,target_bytes,header_sha256,recorder,recorder_sha256,extractor,extractor_sha256,output):
 source_iso=pathlib.Path(source_iso);recorder=pathlib.Path(recorder);extractor=pathlib.Path(extractor);output=pathlib.Path(output)
 if sha(source_iso)!=source_sha256 or sha(recorder)!=recorder_sha256 or sha(extractor)!=extractor_sha256:raise ValueError('pinned wrapper input/tool differs')
 if output.exists():raise ValueError('wrapper output must be a new owned directory')
 output.mkdir(parents=True)
 with tempfile.TemporaryDirectory(prefix='pr248-wrapper-extraction-') as work:
  work=pathlib.Path(work);extracted=work/'source';subprocess.run([str(extractor.resolve()),'-x',str(source_iso.resolve()),'-d',str(extracted)],check=True,capture_output=True)
  target=extracted/'default.xbe'
  if target.is_symlink() or not target.is_file() or target.stat().st_size!=target_bytes:raise ValueError('extracted target byte extent differs')
  with target.open('rb') as stream:header=stream.read(4096)
  if len(header)!=4096 or hashlib.sha256(header).hexdigest()!=header_sha256:raise ValueError('released public target header differs')
  target_hash=sha(target);stage=work/'wrapper';stage.mkdir();shutil.copy2(recorder,stage/'default.xbe');shutil.copy2(target,stage/'target.xbe')
  wrapper=output/'wrapper.iso';subprocess.run([str(extractor.resolve()),'-c',str(stage),str(wrapper.resolve())],check=True,capture_output=True)
  actual=inspect_wrapper(wrapper)
  if actual['files']['default.xbe']['sha256']!=recorder_sha256 or actual['files']['target.xbe']['sha256']!=target_hash or actual['files']['target.xbe']['first4096_sha256']!=header_sha256:raise ValueError('actual wrapper extents/data differ')
  if sha(source_iso)!=source_sha256 or sha(recorder)!=recorder_sha256 or sha(extractor)!=extractor_sha256:raise ValueError('wrapper inputs/tool changed during build')
  receipt={'schema_version':1,'original_released_iso_sha256':source_sha256,'original_released_iso_bytes':source_iso.stat().st_size,'extracted_target_xbe_sha256':target_hash,'target_file_bytes':target_bytes,'reference_header_sha256':header_sha256,'reference_header_bytes':4096,'recorder_xbe_sha256':recorder_sha256,'boot_and_measured_wrapper_iso_sha256':sha(wrapper),'wrapper_iso_bytes':wrapper.stat().st_size,'layout':actual,'measured_path':'target.xbe','extractor_sha256':extractor_sha256,'extraction':'fresh temporary directory','exact_original_media_parity':False,'performance_acceptance_eligible':False}
  (output/'receipt.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n');return receipt

def main():
 p=argparse.ArgumentParser();p.add_argument('--kind',choices=REFERENCES,required=True);p.add_argument('--source-iso',type=pathlib.Path,required=True);p.add_argument('--recorder',type=pathlib.Path,required=True);p.add_argument('--recorder-sha256',required=True);p.add_argument('--extractor',type=pathlib.Path,required=True);p.add_argument('--extractor-sha256',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();source_hash,size,header_hash=REFERENCES[a.kind]
 value=build_wrapper(source_iso=a.source_iso,source_sha256=source_hash,target_bytes=size,header_sha256=header_hash,recorder=a.recorder,recorder_sha256=a.recorder_sha256,extractor=a.extractor,extractor_sha256=a.extractor_sha256,output=a.output);print(json.dumps(value,indent=2))
if __name__=='__main__':main()
