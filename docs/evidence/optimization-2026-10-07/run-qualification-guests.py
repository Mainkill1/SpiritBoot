import json
from pathlib import Path
import sys
sys.path.insert(0,'/work')
from tools.firmware import run_firmware
root=Path('/work')
images={'release':root/'artifacts/optimization/final-release-v1/flash.bin','checked':root/'artifacts/optimization/final-debug-v1/flash.bin'}
summary=[]
for variant,flash in images.items():
    for name,filename,plan,ok,todo in [('api','final-api.iso',632,626,6),('contracts','final-contracts.iso',23,23,0),('warm','final-warm.iso',5,5,0)]:
        capture=root/f'artifacts/optimization/qualification-{variant}-{name}-v1'
        result=run_firmware('/xemu/usr/bin/xemu',flash,'/seed.qcow2',root/'artifacts/optimization/guests'/filename,capture,timeout=240,tap=True)
        tap=result.get('tap',{})
        assert result['status']=='passed' and result['returncode']==0,(variant,name,result)
        assert tap['plan']==plan and tap['ran']==plan and tap['ok']==ok and tap['todo']==todo and tap['skipped']==0 and not tap['errors'],(variant,name,tap)
        summary.append({'variant':variant,'guest':name,'status':result['status'],'tap':tap,'elapsed_seconds':result['elapsed_seconds']})
        (root/'artifacts/optimization/qualification-guests-v1.json').write_text(json.dumps(summary,indent=2)+'\n')
        print(variant,name,tap,flush=True)
