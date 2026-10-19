#!/usr/bin/env python3
"""Isolated native-ABI code-shape experiment; no firmware build or source edits."""
import hashlib,json,re,shlex,shutil,subprocess
from pathlib import Path

repo=Path('/work');out=Path('/experiment')
inputs={'0168':'artifacts/forza-bookkeeping-release64/work-14lo4o24',
        '0169':'artifacts/forza-static-ports-release64/work-d8nx2jrg'}
cc='/usr/bin/i686-w64-mingw32-gcc'
receipt={'compiler':subprocess.check_output([cc,'--version'],text=True).splitlines()[0],
         'scope':'Native ABI, three owned translation units, relocatable LTO code generation; not a complete kernel or latency measurement','variants':{}}
for version,rel in inputs.items():
    base=repo/rel;ninja=(base/'build/build.ninja').read_text()
    owned=base/'source/drivers/storage/class/nxstorage'
    for opt in ('Os','O2'):
        name=version+'-'+opt;target=out/name;target.mkdir(exist_ok=True)
        copy=target/'source';shutil.copytree(owned,copy,dirs_exist_ok=True)
        commands=[];objects=[]
        for unit in ('request','native_adapter','native_packet'):
            match=re.search(r'^build drivers/storage/class/nxstorage/CMakeFiles/nxstorage.dir/'+unit+r'\.c.obj:.*?\n(.*?)(?=\n\n)',ninja,re.M|re.S)
            assert match,unit
            variables=dict(re.findall(r'^  (\w+) = (.*)$',match[1],re.M))
            flags=shlex.split(variables['FLAGS']);assert flags.count('-Os')==1
            flags[flags.index('-Os')]='-'+opt
            includes=shlex.split(variables['INCLUDES'])
            includes=[('-I'+str(copy))if x=='-I'+str(owned)else x for x in includes]
            obj=target/(unit+'.o');objects.append(str(obj))
            cmd=[cc,*shlex.split(variables['DEFINES']),*includes,*flags,'-fstack-usage','-o',str(obj),'-c',str(copy/(unit+'.c'))]
            commands.append(cmd);subprocess.run(cmd,check=True)
        linked=target/'owned-linked.o'
        cmd=[cc,'-nostdlib','-r','-flto','-flinker-output=nolto-rel','-'+opt,'-o',str(linked),*objects]
        commands.append(cmd);subprocess.run(cmd,check=True)
        for label,args in [('assembly',['objdump','-dr',str(linked)]),('symbols',['nm','-S','--size-sort',str(linked)]),('sections',['size','-A',str(linked)])]:
            (target/(label+'.txt')).write_text(subprocess.check_output(args,text=True))
        receipt['variants'][name]={'input':rel,'commands':commands,'linked_sha256':hashlib.sha256(linked.read_bytes()).hexdigest(),
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()for p in copy.glob('*')if p.is_file()}}
        (out/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(name+' complete',flush=True)
