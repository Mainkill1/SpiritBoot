"""Validate paired final-ROM micro captures; no remote operations."""
import argparse,copy,csv,hashlib,json,re,statistics as st,tomllib
from datetime import datetime,timedelta
from pathlib import Path
import zipfile
from micro_parser import parse_micro,CONTRACT,need
ROOT=Path(__file__).resolve().parent
BIOS={'baseline':'62edb78f3ac8dd5739c2b6b9d1a838a4447f3c7662db4e4166e3c795081db027',
      'combined':'be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827'}
ISO='65da3568167cd7e25eec3da4baaffbe65c7fae931078659885297e657412a705'
EXE='14777b55740706608cdfde97349eefa3d5115ece4c889679c9c8b96641a85f2d'
EEPROM='67412e911568a47719ef0b3e0c6396e70996c2f7c29a4e48441bf9cc3d585642'

def summarize(runs,cohort):
    pairs=sorted({(r['cohort'],r['pair']) for r in runs})
    index={(r['cohort'],r['pair'],r['arm']):r for r in runs}
    rows=[]
    for name in runs[0]['workload_us']:
        arms={arm:[index[c,p,arm]['workload_us'][name] for c,p in pairs] for arm in BIOS}
        a,b=arms['baseline'],arms['combined'];ratios=[y/x for x,y in zip(a,b)]
        nonoverlap='overlap'
        if max(a)<min(b):nonoverlap='current slower, disjoint ranges'
        if max(b)<min(a):nonoverlap='current faster, disjoint ranges'
        rows.append(dict(cohort=cohort,workload=name,pairs=len(pairs),baseline_us=st.median(a),combined_us=st.median(b),aggregate_percent=100*(st.median(b)/st.median(a)-1),paired_median_percent=100*(st.median(ratios)-1),faster_pairs=sum(y<x for x,y in zip(a,b)),slower_pairs=sum(y>x for x,y in zip(a,b)),baseline_min_us=min(a),baseline_max_us=max(a),combined_min_us=min(b),combined_max_us=max(b),paired_min_percent=100*(min(ratios)-1),paired_max_percent=100*(max(ratios)-1),ranges=nonoverlap,baseline_boot_us=a,combined_boot_us=b))
    return rows

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--results',type=Path);args=ap.parse_args()
    if args.results:
        names=sorted(d.name for d in args.results.iterdir() if re.fullmatch(r'probe-(layout-micro|performance-kernel-performance-portable)-[0-2]-(baseline|combined)-\d{8}-\d{6}',d.name))
        with zipfile.ZipFile(ROOT/'receipts.zip','w',zipfile.ZIP_DEFLATED) as z:
            for name in names:
                for f in ['inputs.json','launch.json','result.json','serial.log','xemu.toml']:
                    z.write(args.results/name/f,name+'/'+f)
    runs=[];common=None;normalized_common=None;timeline=[]
    with zipfile.ZipFile(ROOT/'receipts.zip') as z:
        names=sorted({n.split('/')[0] for n in z.namelist()})
        for name in names:
            m=re.fullmatch(r'probe-(layout-micro|performance-kernel-performance-portable)-([0-2])-(baseline|combined)-\d{8}-\d{6}',name);need(m,'unexpected run')
            cohort,pair,arm=m[1],int(m[2]),m[3]
            raw={f:z.read(name+'/'+f) for f in ['inputs.json','launch.json','result.json','serial.log','xemu.toml']}
            inp,launch,res=[json.loads(raw[f]) for f in ['inputs.json','launch.json','result.json']]
            need(res['exited'] is True and res['exitCode']==0 and 0<res['elapsedSeconds']<180,'process exit')
            for key,want in [('biosSha256',BIOS[arm]),('exeSha256',EXE),('probeSha256',ISO)]:need(launch[key].lower()==want,key)
            need(inp['memoryMiB']==64 and inp['eepromSha256'].lower()==EEPROM,'memory/EEPROM')
            context=(inp['backing'],inp['backingLength'],inp['backingModified'],launch['session'])
            if common is None:common=context
            need(context==common,'backing/session mismatch')
            config=tomllib.loads(raw['xemu.toml'].decode('utf-8-sig'))
            need(config['sys']['files']['flashrom_path']==launch['bios'],'BIOS config')
            for f,leaf in [('eeprom_path','eeprom.bin'),('hdd_path','hdd.qcow2')]:need(config['sys']['files'][f].endswith(name+'\\'+leaf),'private run paths')
            need(config['sys']['files']['dvd_path'].endswith('\\kernel-performance-portable.iso'),'DVD path')
            normalized=copy.deepcopy(config)
            for f in ['flashrom_path','eeprom_path','hdd_path','dvd_path']:normalized['sys']['files'][f]='<run-specific>'
            if normalized_common is None:normalized_common=normalized
            need(normalized==normalized_common,'configuration mismatch')
            log=raw['serial.log'].decode('utf-8-sig');medians=parse_micro(log)
            samples=[dict(workload=n,sample=int(s),iterations=int(i),ticks=int(t),checksum=h) for n,s,i,t,h in re.findall(r'^# PERF workload=(\S+) sample=(\d+) iterations=(\d+) ticks=(\d+) correct=1 checksum=(\S+)$',log,re.M)]
            frequency=int(re.search(r'frequency=(\d+)',log)[1]);need(frequency==3374488,'clock mismatch')
            end=datetime.fromisoformat(res['utc'].replace('Z','+00:00'));start=end-timedelta(seconds=res['elapsedSeconds']);timeline.append((start,end,name,cohort,pair,arm))
            runs.append(dict(name=name,cohort=cohort,pair=pair,arm=arm,frequency=frequency,workload_us=medians,samples=samples,inputs=inp,launch=launch,result=res,hashes={f:hashlib.sha256(v).hexdigest() for f,v in raw.items()}))
    cohorts=sorted({r['cohort'] for r in runs});need(cohorts,'no cohorts')
    for c in cohorts:
        got=[(r['pair'],r['arm']) for r in runs if r['cohort']==c]
        need(len(got)==6 and set(got)=={(p,a) for p in range(3) for a in BIOS},'incomplete/duplicate pairs')
    timeline.sort();need(all(a[1]<=b[0] for a,b in zip(timeline,timeline[1:])),'overlapping runs')
    for c in cohorts:
        for p in range(3):need([r[5] for r in timeline if r[3:5]==(c,p)]==(['baseline','combined'] if p%2==0 else ['combined','baseline']),'pair order')
    rows=[]
    for c in cohorts:rows+=summarize([r for r in runs if r['cohort']==c],c)
    if len(cohorts)>1:rows+=summarize(runs,'all-cohorts')
    report=dict(validated=True,identities=dict(bios=BIOS,iso=ISO,exe=EXE),runs=len(runs),samples=sum(len(r['samples']) for r in runs),cohorts=cohorts,normalized_postexit_config=normalized_common,workloads=rows,receipts=runs,method='Per-run median of three normalized samples (object-cold-64: one); median across matched runs. Ranges descriptive, not confidence intervals; no empty-loop subtraction.',limitations='Receipt hashes identify remote emulator bytes; backing content not independently hashed. Postexit config normalized and compared; prelaunch hashes differ because xemu rewrites config. These micro measurements do not establish title-level speedup or hardware timing.')
    (ROOT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    with (ROOT/'workloads.csv').open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
    print(json.dumps({'validated':True,'runs':len(runs),'samples':report['samples'],'cohorts':cohorts},indent=2))
    for row in rows:
        if row['workload'].startswith(('sha','des')):print(row['cohort'],row['workload'],f"{row['aggregate_percent']:+.2f}%",f"{row['faster_pairs']}fast/{row['slower_pairs']}slow",row['ranges'],f"pair {row['paired_min_percent']:+.2f}..{row['paired_max_percent']:+.2f}%")
if __name__=='__main__':main()
