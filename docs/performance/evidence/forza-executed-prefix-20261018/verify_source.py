# SPDX-License-Identifier: MIT
"""Reconstruct the three observer files from public Git objects in a temporary tree."""
import argparse, hashlib, json, subprocess, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
IDENTITY=HERE.parent/'forza-request-identity-20261017'
def digest(data): return hashlib.sha256(data).hexdigest()
def reconstruct(repository, root):
    original=json.loads((IDENTITY/'xemu-source-provenance.json').read_text())
    staged=json.loads((HERE/'recorder-v2/staging.json').read_text())
    receipt=json.loads((HERE/'recorder-v2/build-receipt.json').read_text())
    for name,expected in original['base_sha256'].items():
        data=subprocess.check_output(['git','-C',str(repository),'show',original['base_commit']+':'+name])
        if digest(data)!=expected: raise ValueError('Public base differs: '+name)
        target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    for patch,expected,outputs in [
        (IDENTITY/original['patch'],original['patch_sha256'],staged['input_sha256']),
        (HERE/'recorder-v2/observer.patch',receipt['patch_sha256'],staged['output_sha256'])]:
        if digest(patch.read_bytes())!=expected: raise ValueError('Patch digest mismatch')
        subprocess.run(['git','apply','--check',str(patch)],cwd=root,check=True)
        subprocess.run(['git','apply',str(patch)],cwd=root,check=True)
        for name,wanted in outputs.items():
            if digest((root/name).read_bytes())!=wanted: raise ValueError('Result mismatch: '+name)
    if staged['output_sha256']!=receipt['source_sha256']: raise ValueError('Build source differs')
    return {'public_base':original['base_commit'],'exact_staged_sha256':staged['output_sha256'],
            'patches_applied':2,'rebuild_performed':False,'input_repository_unchanged':True}
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('repository',type=Path)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='prefix-public-source-') as tmp:
        print(json.dumps(reconstruct(args.repository,Path(tmp)),indent=2))
