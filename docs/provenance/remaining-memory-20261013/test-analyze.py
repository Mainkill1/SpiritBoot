#!/usr/bin/env python3
"""Mutation checks for the release evidence gate; never modifies real captures."""
import hashlib,json,re,shutil,subprocess,sys,tempfile
from pathlib import Path
here=Path(__file__).resolve().parent
results,manifest,bios,tree=map(str,sys.argv[1:])
with tempfile.TemporaryDirectory(prefix='remaining-gate-') as td:
 d=Path(td);r=d/'results';r.mkdir()
 for p in Path(results).glob('probe-*'):
  if p.name.startswith(('probe-closing-','probe-integrated-')):shutil.copytree(p,r/p.name)
 def run():return subprocess.run([sys.executable,str(here/'analyze.py'),str(r),str(d/'output'),manifest,bios,tree],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 x=run();assert x.returncode==0,x.stderr
 clean=next(r.glob('probe-closing-api-clean-combined-*'));perf=next(r.glob('probe-closing-kernel-performance-portable-0-combined-*'))
 def mutation(name,p,f):
  old=p.read_bytes();p.write_bytes(f(old));x=run();p.write_bytes(old);assert x.returncode!=0,name+' falsely accepted';print('REJECT '+name)
 def jedit(b,k,v):
  x=json.loads(b.decode('utf-8-sig'));x[k]=v;return json.dumps(x).encode()
 mutation('wrong BIOS',clean/'launch.json',lambda b:jedit(b,'biosSha256','0'*64))
 mutation('128-MiB runtime',clean/'inputs.json',lambda b:jedit(b,'memoryMiB',128))
 mutation('wrong ordinary TAP name',clean/'serial.log',lambda b:b.replace(b'ok 1 - rtl/status/success',b'ok 1 - wrong',1))
 mutation('extra malformed LEAF',clean/'serial.log',lambda b:b.replace(b'== api-regression end PASS ==',b'# LEAF malformed\n== api-regression end PASS =='))
 mutation('failed ordinary TAP',clean/'serial.log',lambda b:b.replace(b'ok 1 - ',b'not ok 1 - ',1))
 mutation('missing TAP',clean/'serial.log',lambda b:re.sub(br'^ok 1 - .*\n',b'',b,count=1,flags=re.M))
 mutation('incorrect micro checksum',perf/'serial.log',lambda b:re.sub(br'checksum=[0-9a-f]{8}',b'checksum=ffffffff',b,count=1))
 mutation('unqualified fixture',clean/'launch.json',lambda b:jedit(b,'probeSha256','0'*64))
 mutation('incomplete process',clean/'result.json',lambda b:jedit(b,'exited',False))
 mutation('frozen config hash mismatch',clean/'inputs.json',lambda b:jedit(b,'configSha256','0'*64))
 mutation('overlapping captures',next(r.glob('probe-closing-api-clean-complex-*'))/'result.json',lambda b:jedit(b,'elapsedSeconds',299))
 p=next(r.glob('probe-integrated-system-va-validity-*'));park=d/'park';p.rename(park);x=run();park.rename(p);assert x.returncode!=0;print('REJECT missing integrated contract')
 assert run().returncode==0
print('PASS real 47-receipt gate; 12 corrupted/incomplete evidence variants rejected')
