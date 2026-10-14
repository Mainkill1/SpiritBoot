#!/usr/bin/env python3
"""Generic frozen native caller: functional grade and post-END context only."""
import argparse,datetime,hashlib,importlib.util,json,math,os,pathlib,re,sys
sys.dont_write_bytecode=True
ROOT=None
PLAN_SHA=None
PLAN=None
VERSION=None
native=None
def sha(path):return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
def unique_json(pairs):
 value={}
 for key,item in pairs:
  if key in value:raise ValueError('duplicate JSON field')
  value[key]=item
 return value
def read(path):return json.loads(pathlib.Path(path).read_bytes(),object_pairs_hook=unique_json)
def read_jsonl(path):
 rows=[]
 for number,line in enumerate(pathlib.Path(path).read_text().splitlines(),1):
  try:rows.append(json.loads(line,object_pairs_hook=unique_json))
  except (ValueError,TypeError) as error:raise ValueError(f'{path} line {number}: {error}') from error
 return rows
def load_source(name):
 path=ROOT/'tool-source'/name
 if sha(path)!=PLAN['method_source_pins'][name]:raise ValueError('frozen method source differs '+name)
 spec=importlib.util.spec_from_file_location('functional_'+name.replace('-','_'),path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def configure(plan_root,plan_sha256):
 global ROOT,PLAN_SHA,PLAN,VERSION,native
 root=pathlib.Path(plan_root).resolve()
 if not re.fullmatch('[0-9a-f]{64}',plan_sha256) or sha(root/'qualification-plan.json')!=plan_sha256:raise ValueError('externally pinned plan hash differs')
 value=read(root/'qualification-plan.json')
 if value.get('schema_version')!=1 or value.get('purpose')!='native_fixture_qualification':raise ValueError('unsupported frozen plan')
 ROOT,PLAN_SHA,PLAN=root,plan_sha256,value
 VERSION=PLAN['revision'].replace('.','');native=load_source('storage_native_runner.py')
 return PLAN

def validate_leaf_records(parsed,attempt):
 observed=parsed['cases'][attempt['expected_case']['id']];expected=attempt['expected_case']
 if observed['flushes_completed'] is not None or observed['durability_verified'] is not None:raise ValueError('fixture cannot supply physical flush/durability telemetry')
 if expected['kind']=='fatx-read':
  for row in observed['operation_records']:
   if 'submit_status' not in row or int(row['submit_status'],16) not in (0,0x103):raise ValueError('actual async submit status differs from success/pending')
 if expected['kind']=='write-flush':
  counts=expected['public_api_counts_expected']
  if (observed['flush_api_calls_completed']!=counts['flush_api_calls_completed']
      or observed['counters'].get('file_read_calls')!=counts['file_read_calls']
      or observed['counters'].get('file_write_calls')!=counts['file_write_calls']
      or observed['reopen_readback_verified'] is not True):raise ValueError('actual API write/flush/reopen byte-fill contract differs')
 return {'functional_scope':'generation2 exact byte-fill/status/IOSB/APC/QD/pressure only','real_flushes':None,'durability_verified':None,'private_structural_counters':None,'performance_acceptance_eligible':False,'normative_clock_qualified':False,'timing_values_scope':'retained fixture metadata conversion, not accepted metrology'}

def observe(evidence,row):
 row.update(run_id=evidence.name,artifacts=str(evidence));result=read(evidence/'result.json')
 row.update(raw_runner_assessment=result['assessment'],runner_status=result['status'],runner_execution=result['assessment']['Execution'],raw_exit_code=result['exitCode'],started_utc=result['startedUtc'],finished_utc=result['endedUtc'],wrapper_pid=result['processId'],result_sha256=sha(evidence/'result.json'))
 manifest=read(evidence/'input-manifest.json');row['input_manifest_sha256']=sha(evidence/'input-manifest.json');cleanup=read(evidence/'runtime-cleanup.json');row.update(runtime_cleanup=cleanup,runtime_cleanup_sha256=sha(evidence/'runtime-cleanup.json'));raw=(evidence/'native-serial.log').read_text(errors='replace');row['serial_sha256']=sha(evidence/'native-serial.log')
 row['job_sha256']=sha(evidence/'job.json');row['launch_sha256']=sha(evidence/'launch.json')
 row['context_artifact_sha256']={name:sha(evidence/name) for name in ('native-host-controls.txt','diagnostics/run-state/report.json','job.json','launch.json') if (evidence/name).is_file()}
 row['method_artifact_sha256']={p.name:sha(p) for p in evidence.glob('native-storage-post-*.json')}
 row['managed_diagnostic_artifact_sha256']={p.relative_to(evidence).as_posix():sha(p) for p in (evidence/'diagnostics').rglob('*.json') if p.name in ('request.json','result.json','qmp-result.json')}
 if (evidence/'operator-events.jsonl').is_file():row['operator_events_sha256']=sha(evidence/'operator-events.jsonl')
 return raw,result,manifest,cleanup

def validate_operator_events(events,result,attempt,request):
 ids=attempt['diagnostic_ids'];definitions={d['id']:d for d in request['job']['diagnostics']}
 if (not isinstance(events,list) or len(events)!=len(ids) or result['operations'].get('AllowManualInput') is not False
     or result['operations'].get('AllowPauseResume') is not False):raise ValueError('actual DVD operation/intervention receipts differ')
 moments=[];elapsed=[]
 for event,identity in zip(events,ids):
  definition=definitions[identity];expected={'Id':identity,'Type':definition['type'],'Reason':definition['reason']}
  if event.get('kind')!='diagnostic' or event.get('detail')!=expected:raise ValueError('actual request-bound diagnostic event differs')
  moment=datetime.datetime.fromisoformat(event['timestampUtc']);duration=event['elapsedMs']
  if moment.tzinfo is None or isinstance(duration,bool) or not isinstance(duration,(int,float)) or not math.isfinite(duration) or duration<0:raise ValueError('actual diagnostic event time differs')
  moments.append(moment);elapsed.append(duration)
 if moments!=sorted(moments) or elapsed!=sorted(elapsed):raise ValueError('actual diagnostic event order differs')
 started=datetime.datetime.fromisoformat(result['startedUtc']);ended=datetime.datetime.fromisoformat(result['endedUtc'])
 if any(moment<started or moment>ended for moment in moments):raise ValueError('actual diagnostic event outside owned run')

def validate_post_context(attempt,evidence,result,manifest):
 helper=load_source('dvd-post-route-observer.py');observer=load_source('storage-post-context.py');guard=load_source('clock-observer.py')
 package=pathlib.Path(manifest['PackageDirectory']);device=attempt['expected_media_device_hypothesis'];request=read(ROOT/attempt['request_path']);job=read(evidence/'job.json');launch=read(evidence/'launch.json')
 steps=[{'type':'wait_for_artifact','condition':{'scope':'result','path':'native-serial.log','mustExist':True,'containsText':'STORAGE-PERF-END cases=1 failures=0'},'pollIntervalMs':100,'timeoutMs':150000},{'type':'diagnostic','diagnosticId':'storage-status-post'},{'type':'diagnostic','diagnosticId':'storage-block-post'},{'type':'diagnostic','diagnosticId':'storage-context-post'},{'type':'quit'}]
 if (job.get('Id')!=attempt['id'] or job.get('StartPaused') is not False or launch.get('startPaused') is not False
     or launch.get('jobSha256')!=sha(evidence/'job.json') or job.get('Plan')!=attempt['expected_effective_plan']
     or job.get('Workload',{}).get('RequirePlanCompletion') is not True or request['job']['plan']!=steps
     or request['job']['arguments'].count('-no-shutdown')!=1 or '-S' in request['job']['arguments']):raise ValueError('actual END wait/post context/final quit/launch binding differs')
 checks=[row for row in result['workload']['Checks'] if row.get('Name')=='plan_completion']
 if len(checks)!=1 or checks[0].get('Passed') is not True:raise ValueError('actual final quit plan completion missing')
 contexts=[row for row in result['diagnostics'] if row['Id']=='storage-status-post']
 if len(contexts)!=1:raise ValueError('actual post diagnostic context missing')
 remote=str(pathlib.Path(contexts[0]['Directory']).parent.parent)
 if pathlib.Path(remote).name!=result['runId']:raise ValueError('actual post result/run binding differs')
 observed=read(evidence/'native-storage-post-context.json');binding=observed['binding']
 if (observed.get('guard_complete') is not True or observed.get('error') is not None or observed.get('stage')!='post'
     or observed.get('continuous_observation') is not False or observed.get('performance_acceptance_eligible') is not False
     or observed['target_pid']!=result['processId'] or binding['pid']!=result['processId'] or binding['manifest']!=manifest or binding['launch']!=launch
     or binding['package']!=str(package) or binding['result']!=remote or observed['start_time_at_end']!=binding['start_time_before'] or observed['exe_path_at_end']!=binding['exe_path']):raise ValueError('actual post context/run/input/lifetime binding differs')
 guard.validate_target_binding(binding,{'job_id':attempt['id'],'emulator_sha256':PLAN['hosts'][attempt['host']]['emulator_sha256'],'config_sha256':attempt['expected_inputs']['xemu.toml']})
 if read(evidence/'native-storage-post-target.json')!=binding:raise ValueError('actual post target receipt differs')
 serial=observed['serial_end'];raw=evidence/'native-serial.log'
 stamps=[observed['started_monotonic_ns'],serial['read_started_monotonic_ns'],serial['eof_read_started_monotonic_ns'],serial['eof_read_ended_monotonic_ns'],serial['read_ended_monotonic_ns'],observed['heavy_hash_started_monotonic_ns'],observed['ended_monotonic_ns']]
 if (serial.get('strict_successful_END_verified') is not True or serial.get('path')!=str(pathlib.Path(remote)/'native-serial.log')
     or serial.get('sha256')!=sha(raw) or serial.get('bytes')!=raw.stat().st_size or serial.get('offset_at_eof')!=raw.stat().st_size
     or serial.get('uid')!=binding['uid'] or serial.get('nlink')!=1 or any(type(x) is not int or x<=0 for x in stamps) or stamps!=sorted(stamps)):raise ValueError('actual complete END/prefix/EOF/order witness differs')
 declared={row['Path']:row for row in request['files']};recorder=observed['recorder']
 if recorder['path']!=str(package/'storage-perf.iso') or recorder['sha256']!=attempt['expected_inputs']['storage-perf.iso'] or recorder['bytes']!=declared['storage-perf.iso']['Length']:raise ValueError('actual post fixture input differs')
 observer.validate_clock_context(observed['clock_context'])
 state=helper.read_recipe(evidence,'storage-status-post','query-status',{},remote);query=helper.read_recipe(evidence,'storage-block-post','query-block',{},remote)
 if (observed['managed_state']!=state or observed['post_state']!=observer.validate_post_state(state['response']) or observed['managed_query']!=query
     or observed['actual_route']!=helper.validate_media_route(query['response'],package,package/'storage-perf.iso',device)):raise ValueError('actual post readonly VM state/media route/raw recipe differs')
 if datetime.datetime.fromisoformat(state['result']['EndedUtc'])>datetime.datetime.fromisoformat(query['result']['StartedUtc']):raise ValueError('actual post query order differs')
 diagnostics=[row for row in result['diagnostics'] if row['Id'] in attempt['diagnostic_ids']]
 if [row['Id'] for row in diagnostics]!=attempt['diagnostic_ids'] or any(row['Status']!='completed' for row in diagnostics):raise ValueError('actual post diagnostic sequence differs')
 validate_operator_events(read_jsonl(evidence/'operator-events.jsonl'),result,attempt,request)
 return {'post':observed,'scope':'post_END_controlled_lab_context','continuous_observation':False,'performance_acceptance_eligible':False}

def validate_fixed_workload(attempt):
 boot=attempt['dvd_binding'];case=attempt['expected_case'];vectors=case['request_vectors']
 if (boot.get('mode')!='DVD-fixed-wrapper' or boot.get('exact_original_media_parity') is not False
     or boot.get('recorder_xbe_sha256')!=PLAN['boot_method']['recorder_xbe_sha256']
     or case.get('original_released_file')!='default.xbe' or case.get('measured_path')!=boot.get('measured_path')
     or case.get('extracted_target_xbe_sha256')!=boot.get('extracted_target_xbe_sha256')
     or boot.get('measured_path')!='\\Device\\CdRom0\\target.xbe'
     or boot.get('boot_wrapper_iso_sha256')!=attempt['expected_inputs']['storage-perf.iso']
     or attempt['fixture_sha256']!=boot['boot_wrapper_iso_sha256']
     or case['fixture_iso_sha256']!=boot['boot_wrapper_iso_sha256']
     or boot.get('original_released_iso_sha256')!=attempt['expected_inputs']['target.iso']
     or boot.get('reference_header_sha256')!=case['header_sha256']):raise ValueError('fixed wrapper workload/media identity differs')
 if (case['operations']!=1024 or len(vectors)!=1024
     or any(row!={'file':'target.xbe','index':i,'offset':0,'bytes':4096} for i,row in enumerate(vectors))):raise ValueError('fixed wrapper actual request vectors differ')
 return True

def evaluate(attempt,evidence,observed):
 raw,result,manifest,cleanup=observed
 if attempt['expected_case']['kind']=='dvd-xiso':validate_fixed_workload(attempt)
 if result['job']!=attempt['id'] or result['runId']!=evidence.name or cleanup['runId']!=evidence.name:raise ValueError('actual job/run/cleanup binding differs')
 native.validate_frozen_attempt(manifest,plan_path=ROOT/'qualification-plan.json',plan_sha256=PLAN_SHA,attempt_id=attempt['id']);native.validate_successful_execution(result);native.validate_owned_exit(cleanup)
 launcher=PLAN['hosts'][attempt['host']]['launcher_sha256']
 if result['executableSha256']!=launcher or manifest['ExecutableSha256']!=launcher:raise ValueError('actual launcher differs')
 parsed=native.parse_serial(raw);integrity=native.infer_integrity_for_attempt(raw,manifest,plan_path=ROOT/'qualification-plan.json',plan_sha256=PLAN_SHA,attempt_id=attempt['id']);fields=validate_leaf_records(parsed,attempt)
 context=validate_post_context(attempt,evidence,result,manifest);media=context if attempt['expected_case']['kind']=='dvd-xiso' else None
 runtime=[v for v in manifest['RuntimeFiles'] if v.get('Destination')=='hdd.qcow2']
 if len(runtime)!=1 or not isinstance(runtime[0].get('Sha256'),str) or not re.fullmatch('[0-9a-f]{64}',runtime[0]['Sha256']) or runtime[0]['Sha256']==PLAN['hosts']['deck']['hdd_seed_sha256']:raise ValueError('actual prepared HDD bytes/hash missing or unchanged seed')
 return {'parsed':parsed,'integrity':integrity,**fields,'dvd_media':media,'post_context':context,'actual_prepared_hdd':runtime[0],'recorder_source_sha256':PLAN['boot_method']['recorder_xbe_sha256'] if media is not None else None,'recorder_binding':'fixed wrapper independently parsed and pinned; source recipe/readback is construction evidence' if media is not None else 'immutable generation2 V2 suite/source; no DVD wrapper inference','qualification':'native_functional_byte_fill_only','acceptance_eligible':False}

def validate_previous(row,attempt):
 if (row.get('host')!='deck' or row.get('parser_sha256')!=PLAN['parser_sha256'] or row.get('collector_sha256')!=sha(__file__)
     or row.get('phase')!=attempt['phase'] or row.get('expected_case_id')!=attempt['expected_case']['id']
     or row.get('qualification')!='native_functional_byte_fill_only' or row.get('acceptance_eligible') is not False
     or row.get('performance_acceptance_eligible') is not False):raise ValueError('prior qualified row has different method identity/scope')
 identity=row.get('run_id')
 if not isinstance(identity,str) or pathlib.Path(identity).name!=identity or identity in ('','.','..'):raise ValueError('prior actual run identity missing')
 evidence=ROOT.parent/'evidence'/identity
 if row.get('artifacts')!=str(evidence):raise ValueError('prior evidence directory differs')
 actual={};observed=observe(evidence,actual)
 for key,value in actual.items():
  if row.get(key)!=value:raise ValueError('prior evidence binding changed '+key)
 for key,value in evaluate(attempt,evidence,observed).items():
  if row.get(key)!=value:raise ValueError('prior qualification differs from preserved actual evidence '+key)

def execute(attempt):
 sys.path.insert(0,'xemu-test-runner-mesa-review/scripts');from runner_transport import RunnerApi,inside,declaration;from runner_workflows import Workflows
 api=RunnerApi('http://10.0.0.42:9368');work=Workflows(api,progress=False);identity=attempt['id'];status=api.json('/api/v1/status')
 if status.get('CurrentJob') or status.get('Queue',{}).get('Pending',0):raise RuntimeError('runner busy; preserve current/queued processes')
 request_path=ROOT/attempt['request_path']
 if sha(request_path)!=attempt['request_sha256']:raise ValueError('frozen request changed')
 request=read(request_path);payload=ROOT/attempt['input_directory'];state=request['job']['runtimeState']
 if not state['enabled'] or not state['isolation']['requirePrivateGuestState'] or not state['diskAssets'] or not state['files']:raise ValueError('private HDD/EEPROM missing')
 local=[]
 for row in request['files']:
  path=inside(payload,row['Path'])
  if path.is_file():
   if declaration(payload,row['Path'],row.get('Executable',False))!=row:raise ValueError('frozen payload differs '+row['Path'])
   local.append(row)
 api.json('/api/v1/jobs','POST',request);current=work.status(identity)
 if current['state']=='draft':
  api.json('/api/v1/jobs/'+identity+'/reuse','POST',{'sourceJobId':attempt['reuse_source_job_id']});work.operation(identity)
  for row in local:api.upload(identity,payload,row)
  work.submit_draft(identity)
 elif current['state'] not in ('queued','testing','tested'):raise RuntimeError('owned job needs attention '+current['state'])
 while work.status(identity)['state']!='tested':
  current=work.wait(identity,45);print(json.dumps({'id':identity,'state':current['state']}),flush=True)
  if current.get('blocker') or current['state'] in ('draft','held','blocked','unavailable','cancelled'):raise RuntimeError('runner attention required '+json.dumps(current))
 receipt=work.collect(identity,ROOT.parent/'evidence',[],True);return ROOT.parent/'evidence'/receipt['runId'],receipt

def validate_review(review):
 if (review.get('plan_sha256')!=PLAN_SHA or review.get('parser_sha256')!=PLAN['parser_sha256']
     or review.get('collector_sha256')!=sha(__file__) or review.get('manifest_sha256')!=sha(ROOT/'manifest.json')
     or review.get('status')!='reviewed_no_critical_or_important_findings'):raise ValueError('review does not approve exact plan/parser/collector/manifest')
 manifest=read(ROOT/'manifest.json');seen=set()
 for item in manifest['files']:
  name=item['path'];relative=pathlib.PurePosixPath(name)
  if (not isinstance(name,str) or relative.is_absolute() or '..' in relative.parts or relative.as_posix()!=name
      or name in seen or name=='manifest.json'):raise ValueError('approved outer entry path is invalid/duplicate')
  seen.add(name);path=ROOT/name
  if path.is_symlink() or not path.resolve().is_relative_to(ROOT.resolve()) or not path.is_file():raise ValueError('approved outer entry missing/escaped '+name)
  if path.stat().st_size!=item['bytes'] or sha(path)!=item['sha256']:raise ValueError('approved outer entry bytes differ '+name)

def main():
 p=argparse.ArgumentParser();p.add_argument('host',choices=['deck']);p.add_argument('--attempt');p.add_argument('--phase',required=True);p.add_argument('--plan-root',type=pathlib.Path,required=True);p.add_argument('--plan-sha256',required=True);p.add_argument('--execute',action='store_true',required=True);p.add_argument('--review-receipt',type=pathlib.Path,required=True);p.add_argument('--review-sha256',required=True);args=p.parse_args()
 configure(args.plan_root,args.plan_sha256)
 if sha(args.review_receipt)!=args.review_sha256:raise ValueError('review receipt hash differs')
 review=read(args.review_receipt)
 validate_review(review)
 ledger=ROOT.parent/('deck-v'+VERSION+'-qualification.jsonl');previous=read_jsonl(ledger) if ledger.exists() else []
 if any(r.get('plan_sha256')!=PLAN_SHA for r in previous):raise ValueError('prior ledger plan differs')
 if any(r.get('status')=='failed_qualification' for r in previous):print(json.dumps({'status':'stopped_after_prior_failure','native_dispatch':False}));return 2
 if any(r.get('status')!='qualified_for_declared_scope' for r in previous):raise ValueError('prior ledger contains unqualified outcome')
 declared={r['id']:r for r in PLAN['attempts']};finished=set()
 for prior in previous:
  identity=prior.get('attempt_id')
  if identity not in declared or identity in finished:raise ValueError('prior unknown or duplicate attempt identity')
  validate_previous(prior,declared[identity]);finished.add(identity)
 for attempt in PLAN['attempts']:
  if attempt.get('phase')!=args.phase:continue
  if attempt['id'] in finished or (args.attempt and args.attempt!=attempt['id']):continue
  row={'schema_version':1,'attempt_id':attempt['id'],'host':'deck','plan_sha256':PLAN_SHA,'parser_sha256':PLAN['parser_sha256'],'collector_sha256':sha(__file__),'expected_case_id':attempt['expected_case']['id'],'phase':attempt['phase'],'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'tracing_enabled':False,'performance_acceptance_eligible':False,'acceptance_eligible':False,'timing_calibration_eligible':PLAN.get('timing_calibration_eligible',False),'timing_scope':PLAN.get('timing_scope')}
  try:
   evidence,receipt=execute(attempt);row['collection']=receipt;observed=observe(evidence,row);row.update(evaluate(attempt,evidence,observed),status='qualified_for_declared_scope')
  except Exception as error:row.update(status='failed_qualification',error=str(error))
  with ledger.open('a') as stream:stream.write(json.dumps(row,separators=(',',':'),allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())
  print(json.dumps({key:row.get(key) for key in ['attempt_id','run_id','status','error']}),flush=True)
  if row['status']=='failed_qualification':return 2
 return 0
if __name__=='__main__':sys.exit(main())
