#!/usr/bin/env python3
"""Validate separate UART lock diagnostics; internal NT PIT clock, not title PMT."""
import argparse
import csv
import json
from pathlib import Path
import re
import hashlib

FREQUENCY=1125000
FIXTURE='138733b225a59eb9be6f735a38a428999777545b0134e23fc162bf43f82532a3'
BIOS={'baseline':'dead8f7d67c090d16fbe6ea89fe7e7023499da0a7d1f9fc608c716b2364ab8d2',
      'raw':'61786b167f9ff2ad9196c23629941f03cad5b1072d40b409ab9ec0586dd9c3c0'}
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(v,why):
    if not v:raise ValueError(why)
def main():
    p=argparse.ArgumentParser();p.add_argument('results',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
    rows=[];captures=[]
    for side,bios in BIOS.items():
        paths=list(a.results.glob('probe-sysva-phase-'+side+'-*'));require(len(paths)==1,'one diagnostic per BIOS required')
        directory=paths[0];launch=read(directory/'launch.json');inputs=read(directory/'inputs.json');result=read(directory/'result.json')
        require(launch['biosSha256'].lower()==bios and launch['probeSha256'].lower()==FIXTURE and launch['session']>0,'diagnostic image/fixture identity')
        require(inputs['memoryMiB']==64 and result['exited'] is True and result['exitCode']==0,'diagnostic profile/exit')
        require(sha(directory/'launch-xemu.toml')==inputs['configSha256'].lower(),'diagnostic immutable config')
        text=(directory/'serial.log').read_text();require('# checks=59 failures=0' in text and not re.search(r'^not ok',text,re.M),'diagnostic common contract')
        observations=re.findall(r'^# SYSVA-LOCK phase=(alloc|free) bytes=(\d+) result=(\d+) locks=(\d+) max_ticks=(\d+)',text,re.M)
        require(len(observations)==25,'missing diagnostic observations')
        for index,(phase,size,value,locks,ticks) in enumerate(observations):
            rows.append(dict(side=side,observation=index,phase=phase,size=int(size),result=int(value),locks=int(locks),
                             max_ticks=int(ticks),max_us=int(ticks)*1e6/FREQUENCY))
        captures.append(dict(side=side,path=str(directory),bios=bios,serial_sha256=sha(directory/'serial.log'),
                             launch_sha256=sha(directory/'launch.json'),inputs_sha256=sha(directory/'inputs.json'),result_sha256=sha(directory/'result.json')))
    for baseline,raw in zip(rows[:25],rows[25:]):
        require(all(baseline[k]==raw[k] for k in ['observation','phase','size','result','locks']),'diagnostic work/lock count changed')
    a.output.mkdir(parents=True,exist_ok=True)
    with (a.output/'lock-observations.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    report=dict(clock='internal NT KeQueryPerformanceCounter (Xbox HAL PIT)',frequency=FREQUENCY,
                frequency_source='hal/halx86/include/halhw.h SARCH_XBOX PIT_FREQUENCY; hal/halx86/xbox.cmake selects generic/timer.c',
                title_clock_distinct='Portable benchmark uses XeKeQueryPerformanceCounter PMT at 3374488 Hz on SpiritBoot.',
                captures=captures,all_counts_identical=True,observations=50,
                first={s:next(r for r in rows if r['side']==s) for s in BIOS},
                maximum={s:max((r for r in rows if r['side']==s),key=lambda r:r['max_ticks']) for s in BIOS},
                limits='One instrumented capture per BIOS; interrupts and QPC overhead may affect maxima. Not a bound or speed aggregate.')
    (a.output/'lock-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ['clock','frequency','first','maximum']},indent=2))
if __name__=='__main__':main()
