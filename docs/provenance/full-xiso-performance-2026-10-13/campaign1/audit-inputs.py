import pathlib,hashlib,json,re,subprocess,tomllib
s=pathlib.Path(r'C:\xemu-lab\incoming\full-xiso-comparison-20261013')
base=pathlib.Path(r'C:\xemu-lab\incoming\forza-api-native-20261013\doa-human-20261013-163331')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def norm(p):
 config=tomllib.loads(p.read_text(encoding='utf-8-sig'))
 for key in ['flashrom_path','eeprom_path','hdd_path','dvd_path']:config['sys']['files'][key]='<per-run>'
 return json.dumps(config,sort_keys=True)

rows=[];expected=norm(base/'xemu.toml')
for p in sorted(s.glob('probe-*')):
 if not p.is_dir() or not (p.name.startswith('probe-leaf-') or p.name.startswith('probe-paired-')):continue
 config=norm(p/'xemu.toml');assert config==expected,p.name
 info=json.loads(subprocess.check_output([r'C:\xemu-lab\tools\qemu-img.exe','info','--output=json',str(p/'hdd.qcow2')]))
 backing=info.get('full-backing-filename',info.get('backing-filename'))
 assert pathlib.Path(backing)==base/'hdd.qcow2',(p.name,backing)
 rows.append({'run':p.name,'normalized_config_sha256':hashlib.sha256(config.encode()).hexdigest(),'backing':backing,'overlay_bytes':info['actual-size'],'eeprom_after_run_sha256':digest(p/'eeprom.bin')})
out={'audit_time':'after campaign','base_eeprom_sha256':digest(base/'eeprom.bin'),'base_hdd_size':(base/'hdd.qcow2').stat().st_size,'base_hdd_mtime_ns':(base/'hdd.qcow2').stat().st_mtime_ns,'runs':rows}
(s/'input-audit.json').write_text(json.dumps(out,indent=2))
print(json.dumps({'audited_runs':len(rows),'normalized_configs':len({r['normalized_config_sha256'] for r in rows}),'post_run_eeprom_hashes':len({r['eeprom_after_run_sha256'] for r in rows})}))
