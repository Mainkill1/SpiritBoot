#!/usr/bin/env python3
"""Replay a recorded runner job with hash-verified local payloads and a new ID."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--runner-scripts',required=True,type=Path)
p.add_argument('--url',required=True)
p.add_argument('--request',required=True,type=Path)
p.add_argument('--package',required=True,type=Path)
p.add_argument('--job-id',required=True)
p.add_argument('--output',required=True,type=Path)
a=p.parse_args()
sys.path.insert(0,str(a.runner_scripts.resolve()))
from runner_transport import RunnerApi,job_url
from runner_workflows import Workflows
request=json.loads(a.request.read_text())
# Verify before publishing any job. Firmware-bound probes must use the recorded
# executable and BIOS; changed inputs need an intentionally revised manifest.
for item in request['files']:
    path=(a.package/item['Path']).resolve()
    if not path.is_relative_to(a.package.resolve()):p.error('payload escapes package')
    if path.stat().st_size!=item['Length'] or hashlib.sha256(path.read_bytes()).hexdigest()!=item['Sha256']:
        p.error('payload hash/length mismatch: '+item['Path'])
request['id']=a.job_id;request['job']['Id']=a.job_id
a.output.mkdir(parents=True,exist_ok=True)
(a.output/'request.json').write_text(json.dumps(request,indent=2)+'\n')
api=RunnerApi(a.url,timeout=120);work=Workflows(api,operation_seconds=600,progress=True)
api.json('/api/v1/jobs','POST',request)
state=work.status(a.job_id)
if state['state']=='busy':work.operation(a.job_id);state=work.status(a.job_id)
if state['state']=='draft':
    available={v['path']:v for v in api.json(job_url(a.job_id)+'/files')}
    for item in request['files']:
        old=available.get(item['Path'])
        if not old or not old['status']['complete'] or old['sha256']!=item['Sha256']:
            api.upload_path(job_url(a.job_id)+'/files/'+item['Path'],a.package/item['Path'],item['Length'],item['Sha256'])
work.submit_draft(a.job_id)
while True:
    state=work.wait(a.job_id,30)
    print(json.dumps(state),flush=True)
    if state.get('state')=='tested' or state.get('blocker') or state.get('state') in {'held','blocked','cancelled','unavailable','draft'}:break
(a.output/'status.json').write_text(json.dumps(state,indent=2)+'\n')
if state.get('state')!='tested':raise SystemExit('runner did not finish; inspect status.json')
work.collect(a.job_id,a.output/'evidence',[],True)
print('Collected evidence. Run check_menu.py, check_buffers.py and/or analyze_requests.py; runner completion alone is not a correctness pass.')
