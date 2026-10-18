#!/usr/bin/env python3
"""Compile candidate request checks and reject two ownership-boundary mutations."""
import argparse
import json
from pathlib import Path
import subprocess
import os


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,required=True,help='assembled owned candidate source root')
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args(); root=args.output.resolve();root.mkdir(parents=True,exist_ok=True)
    src=args.source.resolve()/'drivers/storage/class/nxstorage'
    test=args.source.resolve()/'tests/host/nxstorage/request_test.c'
    original=(src/'request.c').read_text()
    mutations={'idle_unlock_before_clear':('d->pumping=0; unlock(d); return;',
                  'unlock(d); d->pumping=0; return;'),
               'locked_prepare':('nx_status prepared=d->port.prepare',
                  'lock(d); nx_status prepared=d->port.prepare')}
    variants={'candidate':original}
    for name,(old,new) in mutations.items():
        if original.count(old)!=1:raise SystemExit('Mutation anchor is not unique: '+name)
        variants[name]=original.replace(old,new)
    result={}
    for name,source in variants.items():
        path=root/(name+'.c');path.write_text(source);exe=root/(name+'-test')
        subprocess.run([os.environ.get('CC','clang'),'-std=c11','-O1','-g',
            '-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-fno-omit-frame-pointer',
            '-I'+str(src),str(path),str(test),'-o',str(exe)],check=True)
        run=subprocess.run([str(exe)],capture_output=True,text=True)
        (root/(name+'.log')).write_text(run.stdout+run.stderr)
        result[name]={'returncode':run.returncode,
            'idle_test_failed':'FAIL completion_at_idle_release_is_not_lost' in run.stdout}
        if (run.returncode==0)!=(name=='candidate'):
            raise SystemExit('Unexpected mutation verdict: '+name)
        if name=='idle_unlock_before_clear' and not result[name]['idle_test_failed']:
            raise SystemExit('Idle handoff test did not reject mutation')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
