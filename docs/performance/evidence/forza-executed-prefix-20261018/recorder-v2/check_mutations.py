# SPDX-License-Identifier: MIT
"""Diagnostic guards must fail when admission/exclusion invariants are removed."""
from pathlib import Path
import json,subprocess,tempfile,shutil
HERE=Path(__file__).resolve().parent
mutations=[
 ('warmup_admission','actual-identity-fragment.c',
  '        if(getenv("XEMU_FORZA_PREFIX")&&!forza_prefix_admission_allowed(fid_read(env,&event,esp+4)))return;',
  '        (void)forza_prefix_admission_allowed;', 'test_actual_identity.c',None),
 ('inactive_metadata_allocation','recorder.c',
  ' if(!px_owned_pc(pc))return 0;',' /* Mutant allocates excluded boot/title metadata. */','test_recorder.c','excluded'),
 ('excluded_alias','recorder.c',
  '  if(px_owned_pc(px_progress[4])){px_fail(PX_I_EXCLUDED_ALIAS);return;}',
  '  /* Mutant silently excludes an owned mapping alias. */','test_recorder.c','excluded_alias')]
results=[]
for name,file,old,new,test,case in mutations:
 with tempfile.TemporaryDirectory(prefix='forza-prefix-mutant-') as tmp:
  d=Path(tmp)
  for item in ['recorder.c','integration.c','test_recorder.c','test_actual_identity.c','actual-identity-fragment.c']:
   shutil.copy2(HERE/item,d/item)
  s=(d/file).read_text();assert s.count(old)==1;(d/file).write_text(s.replace(old,new))
  subprocess.run(['clang','-std=c11','-O2','-Wall','-Wextra','-Werror',str(d/test),'-o',str(d/'test')],check=True)
  out=subprocess.run([str(d/'test')]+([case] if case else []),capture_output=True,text=True)
  assert out.returncode!=0,(name,'survived')
  results.append({'mutation':name,'returncode':out.returncode,'stderr':out.stderr})
(HERE/'mutation-results.json').write_text(json.dumps(results,indent=2)+'\n')
print(json.dumps(results,indent=2))
