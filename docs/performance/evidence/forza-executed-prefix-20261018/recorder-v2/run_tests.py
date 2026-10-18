# SPDX-License-Identifier: MIT
"""Reconstruct public observer sources and run all C tests without repository writes."""
import argparse, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from verify_source import reconstruct

def run(repository):
    with tempfile.TemporaryDirectory(prefix='prefix-portable-tests-') as temporary:
        root=Path(temporary); source=root/'staged'; source.mkdir()
        receipt=reconstruct(repository,source)
        for name in ['recorder.c','integration.c','test_recorder.c','test_integration.c',
                     'test_actual_identity.c','test_driver.py','check_mutations.py']:
            shutil.copy2(HERE/name,root/name)
        env=dict(os.environ,PREFIX_ANALYZER=str(HERE.parent/'analysis-tools/analyze_prefix.py'))
        subprocess.run([sys.executable,str(root/'test_driver.py')],check=True,env=env)
        # This is the actual reconstructed helper fragment, not an independently maintained mock.
        if (root/'actual-identity-fragment.c').read_bytes()!=(HERE/'actual-identity-fragment.c').read_bytes():
            raise ValueError('Reconstructed actual identity fragment differs from captured test input')
        subprocess.run([sys.executable,str(root/'check_mutations.py')],check=True,env=env)
        receipt['tests']=json.loads((root/'test-results.json').read_text())
        receipt['mutations']=[{'mutation':r['mutation'],'rejected':r['returncode']!=0}
                              for r in json.loads((root/'mutation-results.json').read_text())]
        return receipt
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('repository',type=Path)
    args=parser.parse_args();print(json.dumps(run(args.repository),indent=2))
