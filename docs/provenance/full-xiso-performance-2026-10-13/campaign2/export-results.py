from pathlib import Path
import json,zipfile
root=Path(r'C:\xemu-lab\incoming\full-xiso-comparison-repeat-20261013')
complete=[p for p in root.glob('probe-*') if p.is_dir() and (p/'result.json').exists()]
with zipfile.ZipFile(root/'results.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in complete:
  for name in ('serial.log','launch.json','result.json','stdout.log','stderr.log','operator-quit-after-bugcheck.json','timeout-stop.json'):
   f=p/name
   if f.exists():z.write(f,str(f.relative_to(root)))
print(json.dumps({'completed':len(complete),'paired':sum('-paired-' in p.name for p in complete),'last':sorted(p.name for p in complete)[-3:]}))
