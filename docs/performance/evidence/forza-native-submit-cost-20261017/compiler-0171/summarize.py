#!/usr/bin/env python3
"""Summarize native-ABI relocatable LTO output; static sites are not path counts."""
import argparse,json,re
from collections import Counter
from pathlib import Path

def functions(text):
    result={}
    for match in re.finditer(r'^([0-9a-f]+) <([^>]+)>:\n(.*?)(?=\n[0-9a-f]+ <|\Z)',text,re.M|re.S):
        instructions=[];lines=match[3].splitlines();calls=[]
        for i,line in enumerate(lines):
            ins=re.match(r'^\s*([a-f0-9]+):\s+(?:[a-f0-9]{2}\s+)+\t(\S.*)',line)
            if not ins:continue
            mnemonic=ins[2];instructions.append(mnemonic)
            if re.match(r'call\s',mnemonic):
                relocation=re.search(r'DISP32\s+(\S+)',lines[i+1])if i+1<len(lines)else None
                target=relocation[1]if relocation else re.search(r'<([^>]+)>',mnemonic)
                target=target if isinstance(target,str)else target[1]if target else 'indirect'
                calls.append(target)
        reserve=[int(m[1],16)for line in instructions[:20]if(m:=re.search(r'sub\s+\$0x([a-f0-9]+),%esp',line))]
        result[match[2]]={'static_instructions_excluding_nops':sum(not line.startswith(('nop','xchg   %ax,%ax'))for line in instructions),
            'call_sites':len(calls),'indirect_call_sites':calls.count('indirect'),'call_targets':dict(Counter(calls)),
            'initial_stack_reservation_bytes':reserve[0]if reserve else 0}
    return result

def summarize(root):
    output={}
    for name in ('0168-Os','0168-O2','0169-Os','0169-O2'):
        folder=root/name;sections=(folder/'sections.txt').read_text();fs=functions((folder/'assembly.txt').read_text())
        chosen=['_run_pump','_nx_start','_NxNativeAdapterSubmit','_admit_waiting_requests','_lock','_unlock','_pending',
            '_port_enter','_port_leave','_nx_native_port_enter','_nx_native_port_leave','_nx_packet_prepare']
        output[name]={'text_bytes':int(re.search(r'^\.text\s+(\d+)',sections,re.M)[1]),
            'functions':{key:fs.get(key)for key in chosen}}
    return {'scope':'Three owned native-ABI translation units, relocatable LTO. Kernel callees opaque; not complete-kernel code or native latency.',
        'variants':output,'limitations':['Static sites grow when shared helpers inline; they are not executed path counts.',
        'Stack reservation is the immediate function allocation, not cumulative peak stack usage.',
        'Whole-kernel LTO can further inline kernel spinlock helpers and internalize public engine functions.']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path)
    a=p.parse_args();text=json.dumps(summarize(a.directory),indent=2,sort_keys=True)+'\n'
    if a.output:a.output.write_text(text)
    else:print(text,end='')
