import pathlib,json,hashlib,re,sys,statistics,csv,shutil,argparse,tomllib,copy
root=pathlib.Path(__file__).resolve().parents[4]
ap=argparse.ArgumentParser()
ap.add_argument('--results',type=pathlib.Path,required=True)
args=ap.parse_args()
sys.path.insert(0,str(root))
from tools.write_performance import parse,CASES
src=args.results
out=root/'docs/provenance/write-performance-20261013/native-seven-pairs'
out.mkdir(parents=True,exist_ok=True)
runs={};common=None;normalized_common=None
for d in sorted(src.glob('probe-write-*')):
 m=re.fullmatch(r'probe-write-(\d+)-(baseline|preperf)-\d{8}-\d{6}',d.name)
 assert m,d
 pair,label=int(m[1]),m[2]
 assert (pair,label) not in runs
 parsed=parse((d/'serial.log').read_text())
 inputs=json.loads((d/'inputs.json').read_text());launch=json.loads((d/'launch.json').read_text());result=json.loads((d/'result.json').read_text())
 assert result['exited'] is True and result['exitCode']==0
 assert inputs['memoryMiB']==64
 config=tomllib.loads((d/'xemu.toml').read_text())
 assert config['sys']['files']['flashrom_path']==launch['bios']
 assert config['sys']['files']['eeprom_path'].endswith(d.name+'\\eeprom.bin')
 assert config['sys']['files']['hdd_path'].endswith(d.name+'\\hdd.qcow2')
 normalized=copy.deepcopy(config)
 for key in ['flashrom_path','eeprom_path','hdd_path']: normalized['sys']['files'][key]='<run-specific>'
 if normalized_common is None: normalized_common=normalized
 assert normalized==normalized_common, ('normalized configuration mismatch', d)
 post_config_sha=hashlib.sha256((d/'xemu.toml').read_bytes()).hexdigest()
 assert launch['probeSha256'].lower()=='4722e4048efc14a96f0c554a05b4d5c5a763ddefa0d10fc476ed881a000cbc55'
 signature=(inputs['backing'],inputs['backingLength'],inputs['backingModified'],inputs['eepromSha256'],inputs['memoryMiB'],launch['exeSha256'],launch['probeSha256'],launch['session'],parsed['frequency'])
 if common is None: common=signature
 assert signature==common,(d,signature,common)
 dest=out/d.name;dest.mkdir(exist_ok=True)
 hashes={}
 for f in ['serial.log','inputs.json','launch.json','result.json','xemu.toml']:
  if (d/f).resolve() != (dest/f).resolve(): shutil.copyfile(d/f,dest/f)
  hashes[f]=hashlib.sha256((d/f).read_bytes()).hexdigest()
 runs[pair,label]={'name':d.name,'pair':pair,'label':label,'prelaunch_config_sha256':inputs['configSha256'].lower(),'postexit_config_sha256':post_config_sha,'bios_sha256':launch['biosSha256'].lower(),'result':result,'capture_hashes':hashes,**parsed}
assert set(runs)=={(i,l) for i in range(7) for l in ['preperf','baseline']}
bios={l:{r['bios_sha256'] for (_,k),r in runs.items() if k==l} for l in ['preperf','baseline']}
assert all(len(x)==1 for x in bios.values())
assert next(iter(bios['preperf'])).startswith('1ed') and next(iter(bios['baseline'])).startswith('62ed')
rows=[]
for case in CASES:
 for metric in ['first_call_ms','warm_median_ms']:
  a=[runs[i,'preperf']['summary'][case][metric] for i in range(7)]
  b=[runs[i,'baseline']['summary'][case][metric] for i in range(7)]
  ratio=[y/x for x,y in zip(a,b)]
  row={'case':case,'metric':metric,'preperf_median_ms':statistics.median(a),'current_median_ms':statistics.median(b),'paired_median_ratio':statistics.median(ratio),'paired_median_delta_us':statistics.median([(y-x)*1000 for x,y in zip(a,b)]),'slower_pairs':sum(y>x for x,y in zip(a,b)),'preperf_min_ms':min(a),'preperf_max_ms':max(a),'current_min_ms':min(b),'current_max_ms':max(b),'paired_min_ratio':min(ratio),'paired_max_ratio':max(ratio),'preperf_samples':a,'current_samples':b,'paired_ratios':ratio}
  rows.append(row)
  print(case,metric, *(f'{row[k]:.6g}' for k in ['preperf_median_ms','current_median_ms','paired_median_ratio','paired_median_delta_us']),row['slower_pairs'], 'ranges',f'{min(a):.4g}..{max(a):.4g}',f'{min(b):.4g}..{max(b):.4g}')
report={'schema':1,'normalized_postexit_config':normalized_common,'comparison':{'preperf_sha256':next(iter(bios['preperf'])),'current_sha256':next(iter(bios['baseline'])),'pairs':7,'configuration':dict(zip(['backing','backing_length','backing_modified','eeprom_sha256','memory_mib','exe_sha256','probe_sha256','session','frequency'],common))},'summary':rows,'runs':[runs[i,l] for i in range(7) for l in ['preperf','baseline']]}
(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
with (out/'summary.csv').open('w') as f:
 fields=[k for k in rows[0] if not k.endswith('samples') and k!='paired_ratios'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in rows)

print(json.dumps(report['comparison'],indent=2))
