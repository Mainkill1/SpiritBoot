#!/usr/bin/env python3
"""Read-only checks tying a completed release artifact to patches and CI pins."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--repo',type=Path,required=True)
p.add_argument('--build',type=Path,required=True)
a=p.parse_args()
d=json.loads((a.build/'build.json').read_text())
src=a.build/Path(d['source_directory']).parent.name/'source'
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
assert d['status']=='built' and d['memory_mib']==64 and d['rom_kernel'] is True
assert sha(a.build/'flash.bin')==d['flash_sha256']
assert sha(a.repo/'sources/firmware-lock.json')==d['lock_sha256']
for patch in d['patches']: assert sha(a.repo/patch['path'])==patch['sha256'],patch
actual=subprocess.check_output(['git','-C',str(src),'write-tree'],text=True).strip()
assert actual==d['source_tree']
workflow=(a.repo/'.github/workflows/firmware.yml').read_text()
pins=re.findall(r"(?:actual_tree\" = |source_tree'\] == ')([a-f0-9]{40})",workflow)
assert pins==[actual,actual],pins
print(json.dumps({'flash_sha256':d['flash_sha256'],'source_tree':actual,'patches_verified':len(d['patches']),'lock_sha256':d['lock_sha256'],'workflow_sha256':sha(a.repo/'.github/workflows/firmware.yml'),'ci_tree_pins':pins},indent=2))
