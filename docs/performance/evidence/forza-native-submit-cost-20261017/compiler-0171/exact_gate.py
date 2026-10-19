#!/usr/bin/env python3
"""Reconstruct isolated0171 and run unchanged owned gates at O2."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository',type=Path,required=True);p.add_argument('--lock',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
a=p.parse_args();repo=a.repository.resolve();out=a.output.resolve();out.mkdir();source=out/'source';source.mkdir()
lock=json.loads(a.lock.read_text());patches=lock['repositories']['roswell']['patches']
assert patches[-2]['path'].endswith('0168-coalesce-native-adapter-bookkeeping.patch')
assert patches[-1]['path'].endswith('0171-owned-submission-o2.patch')
subprocess.run(['git','init','-q',str(source)],check=True)
for entry in patches:
    patch=repo/entry['path'];data=patch.read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256']
    subprocess.run(['git','-C',str(source),'apply','--index','--include=drivers/storage/class/nxstorage/*',
        '--include=tests/host/nxstorage/*','--include=tests/host/nxstorage-sense/*','-'],input=data,check=True)
here=Path(__file__).resolve().parent;cc=str(here/'clang-o2');env=dict(os.environ,CC=cc,MSAN_CC=cc)
subprocess.run([sys.executable,str(here/'check_compile_scope.py'),'--source',str(source),'--output',str(out/'scope')],check=True)
for script,name in [('nxstorage/check.py','core'),('nxstorage/check_adapter.py','adapter'),
    ('nxstorage/check_packet.py','packet'),('nxstorage/check_owner.py','owner'),('nxstorage-sense/check.py',None)]:
    cmd=[sys.executable,str(source/'tests/host'/script)]
    if name:cmd.append(str(out/name))
    print('RUN',script,'with O2 compiler wrapper',flush=True)
    subprocess.run(cmd,check=True,env=env)
print('PASS exact isolated0171 source gates atO2; selected lock unchanged',flush=True)
