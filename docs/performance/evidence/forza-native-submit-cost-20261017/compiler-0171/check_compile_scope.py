#!/usr/bin/env python3
"""Exercise the actual nxstorage CMake consumer and check effective commands."""
import argparse,json,re,shlex,subprocess,tempfile
from pathlib import Path

TARGET={'request.c','native_adapter.c','native_packet.c'}
ABI=['-march=pentium','-mtune=generic','-flto','-ffat-lto-objects',
     '-fno-strict-aliasing','-fno-common','-mlong-double-64','-ffunction-sections',
     '-fno-aggressive-loop-optimizations',
     '-fno-optimize-sibling-calls','-fno-omit-frame-pointer','-mstackrealign',
     '-mpreferred-stack-boundary=3','-fno-set-stack-executable',
     '-momit-leaf-frame-pointer','-fno-asynchronous-unwind-tables','-fno-unwind-tables']

def check(source,output):
    output.mkdir()
    cases=[('xbox','Release','gcc'),('xbox','Debug','gcc'),('pc','Release','gcc'),('xbox','Release','clang')]
    receipt={}
    for arch,config,compiler in cases:
        name='-'.join((arch,config,compiler));case=output/name;case.mkdir()
        text='cmake_minimum_required(VERSION 3.20)\nproject(scope C)\n'
        text+='set(CMAKE_EXPORT_COMPILE_COMMANDS ON)\n'
        text+='set(CMAKE_C_FLAGS "'+' '.join(['-Os',*ABI])+'")\n'
        text+='set(CMAKE_C_FLAGS_RELEASE "")\nset(CMAKE_C_FLAGS_DEBUG "")\n'
        text+='set(SARCH '+arch+')\n'
        text+='add_custom_target(psdk)\nadd_custom_target(xdk)\nadd_custom_target(bugcodes)\n'
        text+='add_subdirectory("'+str(source/'drivers/storage/class/nxstorage')+'" owned)\n'
        (case/'CMakeLists.txt').write_text(text)
        subprocess.run(['cmake','-G','Ninja','-S',str(case),'-B',str(case/'build'),
            '-DCMAKE_BUILD_TYPE='+config,'-DCMAKE_C_COMPILER='+compiler],check=True,stdout=subprocess.DEVNULL)
        rows=json.loads((case/'build/compile_commands.json').read_text())
        assert {Path(r['file']).name for r in rows}>=TARGET
        result={}
        for row in rows:
            filename=Path(row['file']).name;args=shlex.split(row['command'])
            options=[a for a in args if re.fullmatch(r'-O(?:[0-3sgz]|fast)',a)]
            selected=(arch,config,compiler)==('xbox','Release','gcc') and filename in TARGET
            want=['-Os','-O2']if selected else['-Os']
            assert options==want,(name,filename,options,want)
            assert all(args.count(a)==1 for a in ABI),(name,filename,'ABI option modified')
            assert '-DNX_NATIVE_PORT_BINDING=1'not in args
            result[filename]={'optimization_options':options,'abi_options':ABI,'command':row['command']}
        receipt[name]=result
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('PASS: four real CMake configurations; only three Xbox/GNU Release units use O2; all ABI options preserved')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();check(a.source.resolve(),a.output.resolve())
