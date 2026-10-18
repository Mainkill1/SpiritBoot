#!/usr/bin/env python3
"""Assemble exact isolated patch bytes and run owned host gates, without selecting it."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import os


def main():
    here=Path(__file__).resolve().parent
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repository',type=Path,default=here.parents[3])
    ap.add_argument('--lock',type=Path,default=here/'core-lock-build-lock.json')
    ap.add_argument('--output',type=Path,required=True,help='new output directory')
    args=ap.parse_args();repo=args.repository.resolve();out=args.output.resolve();out.mkdir()
    lock=json.loads(args.lock.read_text());source=out/'source';source.mkdir()
    subprocess.run(['git','init','-q',str(source)],check=True)
    patches=lock['repositories']['roswell']['patches']
    if not patches[-2]['path'].endswith('0168-coalesce-native-adapter-bookkeeping.patch'):
        raise SystemExit('Candidate must be based directly on selected0168')
    for entry in patches:
        path=(repo/entry['path']).resolve()
        if not path.is_relative_to(repo):raise SystemExit('Patch path escapes repository')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:
            raise SystemExit('Patch hash mismatch: '+str(path))
        subprocess.run(['git','-C',str(source),'apply','--index',
            '--include=drivers/storage/class/nxstorage/*',
            '--include=tests/host/nxstorage/*','--include=tests/host/nxstorage-sense/*','-'],
            input=data,check=True)
    print('Exact candidate patch bytes assembled',flush=True)
    for script,name in [('nxstorage/check.py','core'),('nxstorage/check_adapter.py','adapter'),
        ('nxstorage/check_packet.py','packet'),('nxstorage/check_owner.py','owner'),
        ('nxstorage-sense/check.py',None)]:
        command=[sys.executable,str(source/'tests/host'/script)]
        if name:command.append(str(out/name))
        subprocess.run(command,check=True,env=dict(os.environ,CC=os.environ.get('CC','clang')))
    subprocess.run([sys.executable,str(here/'check_core_lock_mutations.py'),
        '--source',str(source),'--output',str(out/'mutations')],check=True)
    # Prove the adapted late-cancel test still exercises the original0168 path.
    candidate=source/'drivers/storage/class/nxstorage/request.c'
    test=source/'tests/host/nxstorage/native_adapter_test.c'
    candidate_text=candidate.read_bytes();test_text=test.read_text()
    patch=(repo/patches[-1]['path']).read_bytes()
    subprocess.run(['git','-C',str(source),'apply','--reverse',
        '--include=drivers/storage/class/nxstorage/request.c','-'],input=patch,check=True)
    test.write_text(test_text.replace('CHECK(used<=12);','CHECK(used<=14);'))
    try:
        subprocess.run([sys.executable,str(source/'tests/host/nxstorage/check_adapter.py'),
            str(out/'baseline-adapter')],check=True)
        baseline=subprocess.run([str(out/'baseline-adapter/adapter-plain')],check=True,capture_output=True,text=True)
        print(baseline.stdout,end='')
        if '14 adapter lock entries' not in baseline.stdout:raise SystemExit('Baseline count changed')
    finally:
        candidate.write_bytes(candidate_text);test.write_text(test_text)
    observed=subprocess.run([str(out/'adapter/adapter-plain')],check=True,capture_output=True,text=True)
    print(observed.stdout,end='')
    if '12 adapter lock entries' not in observed.stdout:raise SystemExit('Candidate count changed')
    print('All exact isolated candidate gates passed; selected firmware lock unchanged')


if __name__=='__main__':main()
