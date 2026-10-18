#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Recompute paired 0168/0171 native generated-fixture qualification."""
import hashlib
import json
from pathlib import Path
import sys
root=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
sys.path.insert(0,str(root.parent/'initial-poll'))
from analyze import analyze
manifest=json.loads((root/'capture-manifest.json').read_text())
order=['control1','candidate1','control2','candidate2']
if manifest['order']!=order:raise SystemExit('unexpected trial order')
if manifest['firmware']['0171']!='903e8a9462a5457966a1327373297a19e53a48401724db8f6c2ec15e26752f37':raise SystemExit('unexpected candidate firmware')
if manifest['firmware']['0168']!='2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6':raise SystemExit('unexpected control firmware')
build=json.loads((root/'build0171.sanitized.json').read_text())
if (build['status']!='built' or build['variant']!='release' or build['memory_mib']!=64
        or build['flash_sha256']!=manifest['firmware']['0171'] or not build['storage_preflight_passed']):raise SystemExit('build receipt mismatch')
linked_path=root.parent.parent/'forza-native-submit-cost-20261017/compiler-0171/linked-summary.json'
if sha(linked_path)!=manifest['linked_receipt_sha256']:raise SystemExit('linked receipt mismatch')
linked=json.loads(linked_path.read_text())
if linked['builds']['0171']['flash_sha256']!=manifest['firmware']['0171']:raise SystemExit('linked artifact mismatch')
plan=json.loads((root/'plan.json').read_text())
if sha(root/'plan.json')!=manifest['plan_sha256'] or plan['order']!=order:raise SystemExit('qualification plan mismatch')
for previous,current in zip(order,order[1:]):
    if (manifest['runs'][current]['prior_job']!=manifest['runs'][previous]['job_id'] or
        manifest['runs'][current]['prior_finished_utc']!=manifest['runs'][previous]['finished_utc']):raise SystemExit('trials were not consecutive')
freeze=json.loads((root.parent/'initial-poll/release-identity.json').read_text())
if sha(root.parent/'initial-poll/analyze.py')!=freeze['sha256']['analyze.py']:raise SystemExit('frozen analyzer changed')
reference=json.loads((root.parent/'initial-poll/candidate-request.sanitized.json').read_text())
runs={}
for name in order:
    identity=manifest['runs'][name]
    req=json.loads((root/f'{name}-request.sanitized.json').read_text())
    want={f['Path']:f['Sha256'] for f in reference['files']}
    want['flash.bin']=manifest['firmware']['0168' if name.startswith('control') else '0171']
    if {f['Path']:f['Sha256'] for f in req['files']}!=want or req['files']!=identity['files']:raise SystemExit(f'{name}: input hash mismatch')
    if any(i['ExpectedSha256']!=want[i['Path']] for i in req['job']['Inputs']):raise SystemExit(f'{name}: launch input mismatch')
    if any(req['job'][key]!=reference['job'][key] for key in ('Arguments','Executable','ExpectedExecutableSha256','LaunchMode','TimeoutSeconds','RequiredFiles','WorkingDirectory','TargetOs','RuntimeState','Diagnostics','RequireInput','StartPaused')) or req['job']['SnapshotName'] is not None:raise SystemExit(f'{name}: launch contract mismatch')
    if req['sanitization']['source_request_sha256']!=identity['source_request_sha256']:raise SystemExit(f'{name}: request source mismatch')
    receipt=json.loads((root/f'{name}-runner-outcome.json').read_text())
    if (req['id']!=req['job']['Id'] or req['id']!=identity['job_id'] or receipt['jobId']!=req['id'] or
        receipt['runId']!=identity['result_id'] or receipt['state']!='tested' or receipt['outcome']['execution']!='completed' or
        identity['runner_result']!='completed'):raise SystemExit(f'{name}: run identity/execution mismatch')
    for kind,suffix in [('serial','log'),('summary','json')]:
        if sha(root/f'{name}-{kind}.{suffix}')!=identity[f'{kind}_sha256']:raise SystemExit(f'{name}: {kind} hash mismatch')
    summary=analyze((root/f'{name}-serial.log').read_text())
    if summary!=json.loads((root/f'{name}-summary.json').read_text()):raise SystemExit(f'{name}: summary mismatch')
    runs[name]=summary
rows=[]
for index in range(8):
    values={name:summary['cases'][index] for name,summary in runs.items()};keys=('id','target','budget_us')
    if any(any(v[k]!=values['control1'][k] for k in keys) for v in values.values()):raise SystemExit('case matrix mismatch')
    row={k:values['control1'][k] for k in keys};row['runs']=values
    costs={name:sum(size['submit_sum'] for size in case['sizes'])*1e6/runs[name]['frequency']/case['operations'] for name,case in values.items()}
    row['native_return_mean_us']=costs
    row['first_size_frame_counts']={name:{'65536':case['frames']-case['zero_issue_frames']-case['pair_split'],'512':case['pair_split']} for name,case in values.items()}
    for name,counts in row['first_size_frame_counts'].items():
        case=values[name]
        if sum(counts.values())!=case['frames']-case['zero_issue_frames']:raise SystemExit('first-size frame sum mismatch')
        for size,count in counts.items():
            total=next(entry['count'] for entry in case['sizes'] if entry['bytes']==int(size))
            if not 0<=count<=total:raise SystemExit('first-size count outside read population')
    row['paired_changes']={}
    for number in (1,2):
        control=f'control{number}';candidate=f'candidate{number}'
        row['paired_changes'][candidate]={
            'control':control,
            'native_return_mean_percent':100*(costs[candidate]/costs[control]-1),
            'reads_per_second_percent':100*(values[candidate]['operations_per_second']/values[control]['operations_per_second']-1),
            'submit_mean_65536_percent':100*(values[candidate]['sizes'][0]['submit_mean_us']/values[control]['sizes'][0]['submit_mean_us']-1),
            'submit_mean_512_percent':100*(values[candidate]['sizes'][1]['submit_mean_us']/values[control]['sizes'][1]['submit_mean_us']-1)}
    rows.append(row)
regressions=[]
for row in rows:
    for name,changes in row['paired_changes'].items():
        for metric,value in changes.items():
            if isinstance(value,(int,float)) and ((metric=='reads_per_second_percent' and value < -20) or (metric!='reads_per_second_percent' and value>20)):
                regressions.append({'target':row['target'],'budget_us':row['budget_us'],'candidate':name,'metric':metric,'change_percent':value})
primary=[{key:row[key] for key in ('target','paired_changes')} for row in rows if row['budget_us']==450]
maxima=[]
for row in rows:
    for pair in (1,2):
        control=row['runs'][f'control{pair}'];candidate=row['runs'][f'candidate{pair}']
        for a,b in zip(control['sizes'],candidate['sizes']):
            change=100*(b['submit_max_us']/a['submit_max_us']-1)
            if change>20:maxima.append({'target':row['target'],'budget_us':row['budget_us'],'pair':pair,'bytes':a['bytes'],
                'control_max_us':a['submit_max_us'],'candidate_max_us':b['submit_max_us'],'change_percent':change})
if '--write' in sys.argv:
    decision={'selected':False,'decision':'Unselected candidate; see README for measured qualification conclusion.',
              'all_four_runs_full_oracle_passed':True,'cases_per_run':8,'minimum_case_seconds':10,
              'primary_450_pairs':primary,'regressions_over_20_percent':regressions,
              'selected_firmware_lock_changed':False,'overall_Forza_fix_established':False,
              'regressions_over_20_percent_scope':'Weighted/per-size mean read-return costs and throughput; observed maxima are listed separately.',
              'observed_submit_max_increases_over_20_percent':maxima}
    (root/'decision.json').write_text(json.dumps(decision,indent=2)+'\n')
decision=json.loads((root/'decision.json').read_text())
if (decision['selected'] is not False or decision['selected_firmware_lock_changed'] is not False or
    decision['overall_Forza_fix_established'] is not False or decision['regressions_over_20_percent']!=regressions or
    decision['primary_450_pairs']!=primary or decision['observed_submit_max_increases_over_20_percent']!=maxima or not decision['all_four_runs_full_oracle_passed'] or
    decision['cases_per_run']!=8 or decision['minimum_case_seconds']!=10):raise SystemExit('decision evidence mismatch')
result={'status':'paired_synthetic_qualification_not_Forza_fix','order':order,'cases':rows}
encoded=json.dumps(result,indent=2)+'\n'
saved=root/'comparison.json'
if '--write' in sys.argv:saved.write_text(encoded)
elif not saved.exists() or saved.read_text()!=encoded:raise SystemExit('saved comparison differs from exact reproduction')
print(encoded,end='')
