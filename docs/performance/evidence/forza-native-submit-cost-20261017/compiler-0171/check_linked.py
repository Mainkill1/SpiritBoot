#!/usr/bin/env python3
"""Check actual release command scope and summarize owned final linked shapes."""
import argparse,hashlib,json,re,shlex,subprocess
from pathlib import Path
from summarize import functions

def native_commands(text):
    result={}
    for m in re.finditer(r'^build drivers/storage/class/nxstorage/CMakeFiles/[^\n]+?/(\w+\.c)\.obj:.*?\n(.*?)(?=\n\n)',text,re.M|re.S):
        variables=dict(re.findall(r'^  (\w+) = (.*)$',m[2],re.M))
        args=shlex.split(variables['FLAGS'])
        result[m[1]]={'flags':[x for x in args if not x.startswith('-ffile-prefix-map=')],
            'defines':shlex.split(variables['DEFINES'])}
    assert len(result)==9,len(result)
    return result

def run(repo):
    output={};raw={}
    for name,directory in [('0168','forza-bookkeeping-release64'),('0171','forza-owned-o2-release64')]:
        folder=repo/'artifacts'/directory;receipt=json.loads((folder/'build.json').read_text())
        assert receipt['status']=='built'
        flash=folder/'flash.bin';assert hashlib.sha256(flash.read_bytes()).hexdigest()==receipt['flash_sha256']
        build=repo/receipt['build_directory'].removeprefix('/work/');image=build/'ntoskrnl/xboxkrnl.unstripped.exe'
        commands=native_commands((build/'build.ninja').read_text())
        asm=subprocess.check_output(['objdump','-d',str(image)],text=True);fs=functions(asm);raw[name]=fs
        sections={m[1]:int(m[2])for m in re.finditer(r'^(\S+)\s+(\d+)\s+\d+$',subprocess.check_output(['size','-A',str(image)],text=True),re.M)}
        wanted=['_run_pump','_lock','_unlock','_pending','_cache_sync','_zero_bytes','_NxNativeAdapterSubmit',
            '_admit_waiting_requests','_port_enter','_port_leave','_port_prepare','_port_submit','_nx_packet_prepare',
            '@KfAcquireSpinLock@4','@KfReleaseSpinLock@8','@KfLowerIrql@4']
        selected={k:v for k,v in fs.items()if any(k==n or k.startswith(n+'.')for n in wanted)}
        output[name]={'flash_sha256':receipt['flash_sha256'],'source_tree':receipt['source_tree'],
            'image_sha256':hashlib.sha256(image.read_bytes()).hexdigest(),'sections':sections,
            'commands':commands,'functions':selected}
    assert output['0168']['source_tree']=='2716b75a7159254904b4c7a9282f2c51961ee510'
    assert output['0171']['source_tree']=='807f37784296969446caa6036abc701e5ad42b5b'
    for filename,old in output['0168']['commands'].items():
        new=output['0171']['commands'][filename]
        assert new['defines']==old['defines'],filename
        flags=new['flags']
        if filename in {'request.c','native_adapter.c','native_packet.c'}:
            assert flags[-1]=='-O2',filename;flags=flags[:-1]
        assert flags==old['flags'],filename
    assert all(n in raw['0168']and n not in raw['0171']for n in ['_lock','_unlock','_pending'])
    enter=raw['0171']['_port_enter.lto_priv.0'];leave=raw['0171']['_port_leave.lto_priv.0']
    assert '@KfAcquireSpinLock@4'in enter['call_targets']
    assert '@KfReleaseSpinLock@8'in leave['call_targets']
    assert '@KfLowerIrql@4'in raw['0171']['@KfReleaseSpinLock@8']['call_targets']
    return {'scope':'Actual linked release kernels and effective commands; no native performance conclusion',
        'builds':output,'text_delta_bytes':output['0171']['sections']['.text']-output['0168']['sections']['.text'],
        'caveat':'Core/adapter helper inlining is offset by out-of-line kernel acquire/release helpers; ordinary lock call depth is not clearly reduced.'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,required=True);p.add_argument('--output',type=Path)
    a=p.parse_args();text=json.dumps(run(a.repository.resolve()),indent=2,sort_keys=True)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')
