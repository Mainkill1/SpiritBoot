"""Mutation checks: corrupted native evidence must fail closed."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import zipfile

root=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('sha_native',root/'analyze.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
with zipfile.ZipFile(root/'receipts.zip') as z: files={n:z.read(n) for n in z.namelist()}
first=next(n for n in files if 'micro-0-baseline-' in n and n.endswith('/serial.log'))
api=next(n for n in files if 'sha-api-' in n and n.endswith('/serial.log'))
micro=files[first].decode();apilog=files[api].decode()
a.parse_micro(micro);a.parse_api(apilog)
cases=[(a.parse_micro,micro.replace('checksum=811c9dc5','checksum=00000000',1)),
       (a.parse_micro,micro.replace('iterations=1000','iterations=999',1)),
       (a.parse_micro,micro.replace('correct=1','correct=0',1)),
       (a.parse_micro,micro.replace('sample=0','sample=1',1)),
       (a.parse_micro,micro.replace('== kernel-performance-portable end PASS ==','')),
       (a.parse_api,apilog.replace('not ok 178','ok 178',1)),
       (a.parse_api,apilog.replace('io/storage/flush_volume_readonly','io/storage/unknown',1)),
       (a.parse_api,apilog.replace('ok 639','not ok 639',1))]
for i,(parser,bad) in enumerate(cases):
 try:parser(bad)
 except ValueError:pass
 else:raise AssertionError(f'accepted corrupt semantic case {i}')
for suffix,key,value in [('launch.json','biosSha256','0'*64),('launch.json','session',0),('result.json','exited',False),('result.json','exitCode',1),('inputs.json','memoryMiB',128),('inputs.json','backingLength',1)]:
 changed=dict(files);name=first.rsplit('/',1)[0]+'/'+suffix;j=json.loads(changed[name]);j[key]=value;changed[name]=json.dumps(j).encode()
 with tempfile.TemporaryDirectory() as tmp:
  a.ROOT=Path(tmp)
  with zipfile.ZipFile(a.ROOT/'receipts.zip','w') as z:
   for n,b in changed.items():z.writestr(n,b)
  try:
   with contextlib.redirect_stdout(io.StringIO()):a.main()
  except ValueError:pass
  else:raise AssertionError(f'accepted corrupt receipt {suffix}/{key}')
print('PASS: 14 malformed semantic/receipt cases rejected; original API/micro controls accepted')
