# SPDX-License-Identifier: MIT
"""Generate staged xemu files and a review patch; never alter the input tree."""
import argparse
import difflib
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
FILES=['target/i386/tcg/misc_helper.c','target/i386/tcg/translate.c']

def stage(source, output):
    source,output=Path(source).resolve(),Path(output).resolve()
    if output==source or source in output.parents:
        raise ValueError('Staging output must be outside the source worktree')
    sites=json.loads((HERE/'sites.json').read_text())
    before={name:(source/name).read_text() for name in FILES}
    for name,text in before.items():
        actual=hashlib.sha256((source/name).read_bytes()).hexdigest()
        if actual!=sites['input_xemu_sha256'][name]:
            raise ValueError('Input changed since review: '+name)
        if 'XEMU_FORZA_IDENTITY' in text:
            raise ValueError('Identity observer already installed')
    helper=before[FILES[0]]
    needle='void helper_spirit_menu_trace(CPUX86State *env, uint32_t pc)\n{'
    if helper.count(needle)!=1:raise ValueError('Unexpected helper insertion context')
    helper=helper.replace(needle,(HERE/'observer.c').read_text()+'\n'+needle+
       '\n    if(getenv("XEMU_FORZA_IDENTITY")){forza_identity_profile(env,pc);return;}',1)
    translate=before[FILES[1]]
    needle='        if(getenv("XEMU_FORZA_OWNED_PROFILE")) {'
    if translate.count(needle)!=1:raise ValueError('Unexpected translation insertion context')
    switch='\n'.join('            case '+site['pc']+':' for site in sites['sites'])
    addition='''        if(getenv("XEMU_FORZA_IDENTITY")) {
            switch(pc){
'''+switch+'''
                gen_helper_spirit_menu_trace(tcg_env,tcg_constant_i32(pc));break;
            }
            goto forza_instrumentation_done;
        }
'''
    translate=translate.replace(needle,addition+needle,1)
    after=dict(zip(FILES,[helper,translate]))
    output.mkdir(parents=True,exist_ok=True)
    patch=''
    for name,text in after.items():
        dest=output/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(text)
        patch+=''.join(difflib.unified_diff(before[name].splitlines(True),text.splitlines(True),
                      fromfile='a/'+name,tofile='b/'+name))
    (output/'observer.patch').write_text(patch)
    result={'source':str(source),'source_unchanged':all((source/n).read_text()==before[n] for n in FILES),
            'output_sha256':{n:hashlib.sha256((output/n).read_bytes()).hexdigest() for n in FILES}}
    (output/'staging.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    args=parser.parse_args();print(json.dumps(stage(args.source,args.output),indent=2))
