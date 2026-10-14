"""Local retained-native replay; no runner, emulator or remote process is started."""
import copy
import hashlib
import importlib.util
import json
import os
import pathlib
import tempfile
import unittest

import test_storage_perf_artifacts as artifact_fixtures
import test_storage_perf_counter_policy as counter_fixtures
import test_storage_perf_compare as comparator_fixtures

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load_tool():
    spec = importlib.util.spec_from_file_location("storage_native_import", ROOT / "tools/storage_native_import.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(folder, name, value):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return path


# This explicitly pinned, invented collector is a host interface double. It is
# never evidence of machine execution; actual archive tests use reviewed code.
DOUBLE = '''import json,hashlib,pathlib
ROOT=PLAN=PLAN_SHA=None
def read(p):return json.loads(pathlib.Path(p).read_text())
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def configure(root,pin):
 global ROOT,PLAN,PLAN_SHA
 ROOT,PLAN_SHA=root,pin;PLAN=read(root/'qualification-plan.json')
def validate_review(review):
 if review['collector_sha256']!=sha(__file__):raise ValueError('double code pin')
def observe(evidence,row):
 result=read(evidence/'result.json');manifest=read(evidence/'input-manifest.json');cleanup=read(evidence/'runtime-cleanup.json')
 row.update(run_id=evidence.name,result_sha256=sha(evidence/'result.json'),input_manifest_sha256=sha(evidence/'input-manifest.json'),runtime_cleanup_sha256=sha(evidence/'runtime-cleanup.json'),runner_status=result['status'],raw_exit_code=result['exitCode'],serial_sha256=sha(evidence/'native-serial.log'))
 return (evidence/'native-serial.log').read_text(),result,manifest,cleanup
def evaluate(attempt,evidence,observed):
 raw,result,manifest,cleanup=observed
 if result['status']!='completed' or result['exitCode']!=0:raise ValueError('actual failed outcome')
 parsed=native.parse_serial(raw)
 if not parsed['complete']:raise ValueError('actual incomplete serial')
 integrity=native.infer_integrity(raw,attempt['expected_case'],manifest,fixture_sha256=attempt['expected_inputs']['storage-perf.iso'],seed_sha256=manifest['RuntimeFiles'][0]['SeedSha256'])
 return dict(parsed=parsed,integrity=integrity,actual_prepared_hdd=manifest['RuntimeFiles'][0],dvd_media=None,functional_scope='invented host interface double; actual product integrity parser return shape')
'''


def portable_capture(folder, tool, *, kind=None, cache_policy=None, pressure_pages=None, variant=None):
    """Invented native receipts exercising the general importer in a clean checkout."""
    comp = comparator_fixtures.load_tool()
    (folder / "collector.py").write_text(DOUBLE)
    collector = folder / "collector.py"
    spec = counter_fixtures.specification(comp, folder,
        base_spec=artifact_fixtures.specification(comp, folder))
    spec["runner_sha256"] = sha(collector)
    contract_path = folder / spec["counter_policy"]["context_contract"]["path"]
    contract = json.loads(contract_path.read_text())
    verifier = folder / "importer.py"; verifier.write_bytes((ROOT / "tools/storage_native_import.py").read_bytes())
    contract["verifier_artifact"] = {"path": verifier.name, "sha256": sha(verifier)}
    contract["runtime_requirements"] = {"method": "deck-post-END-construction-v1",
        "libc_sha256": "c" * 64, "host_cache_mode":"cold", "host_controls": {"policy": "dynamic powersave"}}
    contract["review_receipt"] = artifact_fixtures.public.artifact(folder,"clock-review.json", {
        "status":"reviewed_for_conditional_arithmetic","reviewed_utc":"2025-12-31T00:00:00+00:00",
        "contract_facts_sha256":comp.digest({k:v for k,v in contract.items() if k!='review_receipt'})})
    spec["counter_policy"]["context_contract"] = artifact_fixtures.public.artifact(folder,contract_path.name,contract)
    parser_descriptor=artifact_fixtures.file_artifact(folder,'actual-parser.py',(ROOT/'tools/storage_native_runner.py').read_bytes())
    public_descriptor=spec['durability_policy']['timing_contract']
    public_contract=json.loads((folder/public_descriptor['path']).read_text())
    public_contract['parser_artifact']=parser_descriptor
    spec['durability_policy']['timing_contract']=artifact_fixtures.public.artifact(folder,public_descriptor['path'],public_contract)
    schedule = comp.make_schedule(spec);schedule["created_utc"]="2026-01-01T00:00:00+00:00"
    comparator_fixtures.reseal_fixture(schedule)
    job = next(job for job in schedule['jobs'] if (kind is None or job['case']['kind']==kind)
               and (cache_policy is None or job['cache_policy']==cache_policy)
               and (pressure_pages is None or job['case'].get('pressure_pages')==pressure_pages)
               and (variant is None or job['case'].get('variant')==variant))
    case=job["case"];entry=spec["artifact_policy"]["cases"][case["id"]]
    native_id, run = "invented-native-attempt", "invented-native-run"
    binding = {"schema_version":1,"scheduled_attempt_id":job["attempt_id"],
        "schedule_sha256":schedule["sha256"],"manifest_sha256":job["manifest_sha256"],
        "case_sha256":comp.digest(case),"environment_sha256":comp.digest(spec["environment"]),
        "runner_sha256":spec["runner_sha256"],
        **{k:job[k] for k in ("artifact_set_sha256","case_artifact_sha256","workload_identity_sha256")}}
    request=write(folder,"request.json",{"job":{"runtimeState":{"enabled":True,
        "isolation":{"requirePrivateGuestState":True,"cacheMode":"cold"}}},
        "files":[{"Path":"aa-binding.json","Sha256":None}]})
    aa=write(folder,"inputs/aa-binding.json",binding)
    req=json.loads(request.read_text());req['files'][0].update(Sha256=sha(aa),Length=aa.stat().st_size);write(folder,'request.json',req)
    expected = {"id":case['id'],"kind":case['kind'],"operations":case['operations'],
        "queue_depth":case.get('queue_depth',1),"cache_policy":case['cache_policy'],
        "expected_operation_bytes":[case['bytes_per_operation']]*case['operations'],
        "bytes_completed_expected":case['bytes_per_operation']*case['operations'],
        "assertions_expected":case['assertions'],"expected_sha256":case['expected_sha256']}
    if case.get('pressure_pages',0)>0:expected['pressure_target_pages']=case['pressure_pages']
    if 'request_vectors' in case:expected['request_vectors']=copy.deepcopy(case['request_vectors'])
    attempt={"id":native_id,"request_path":"request.json","request_sha256":sha(request),
        "input_directory":"inputs","expected_inputs":{"aa-binding.json":sha(aa),"xemu":job['manifest']['xemu_sha256'],
        "flash.bin":job['manifest']['flash_sha256'],"storage-perf.iso":entry['boot_iso']['sha256']},
        "recorder_xbe_sha256":entry['recorder_xbe']['sha256'],"expected_case":expected,
        "seed_request_mode":"prepared_xiso","performance_acceptance_eligible":False,"tracing_enabled":False}
    if case['kind']=='dvd-xiso':
        attempt['expected_inputs']['target.iso']=entry['original_released_iso']['sha256']
        attempt['expected_media_device_hypothesis']='ide0-cd1'
        attempt['dvd_binding']={'mode':'DVD-fixed-wrapper','exact_original_media_parity':False,
            'boot_wrapper_iso_sha256':entry['boot_iso']['sha256'],
            'original_released_iso_sha256':entry['original_released_iso']['sha256']}
    plan={"schema_version":1,"parser_sha256":sha(ROOT/'tools/storage_native_runner.py'),"attempts":[attempt],
        "method_source_pins":{"storage-post-context.py":sha(ROOT/'tests/xbe/storage-perf/storage-post-context.py')},
        "timing_calibration_eligible":True,"timing_scope":"within-host-relative-AA",
        "schedule_sha256":schedule['sha256'],"context_contract_sha256":spec['counter_policy']['context_contract']['sha256']}
    write(folder,'qualification-plan.json',plan)
    manifest={"files":[{"path":p.relative_to(folder).as_posix(),"sha256":sha(p),"bytes":p.stat().st_size}
        for p in sorted(folder.rglob('*')) if p.is_file()]}
    write(folder,'manifest.json',manifest)
    review=write(folder,'review.json',dict(status='reviewed_no_critical_or_important_findings',
        collector_sha256=sha(collector),plan_sha256=sha(folder/'qualification-plan.json'),
        manifest_sha256=sha(folder/'manifest.json'),parser_sha256=plan['parser_sha256']))
    evidence=folder/'evidence'/run;evidence.mkdir(parents=True)
    result=dict(status='completed',exitCode=0,processId=42,runId=run,job=native_id,
        executableSha256='1'*64,startPaused=False,operations=dict(AllowManualInput=False,AllowPauseResume=False),
        startedUtc='2026-01-01T00:00:01+00:00',endedUtc='2026-01-01T00:00:10+00:00')
    write(evidence,'result.json',result);write(evidence,'runtime-cleanup.json',dict(runId=run,targetStopped=True,evidenceFinalized=True))
    prepared=dict(Sha256='2'*64,Bytes=1310720,SeedSha256=entry['hdd_seed']['sha256'],
        DiskAssetId=entry['hdd_seed']['asset_id'],Destination='hdd.qcow2')
    inputs=[dict(Path=k,Sha256=v,ExpectedSha256=v,Verified=True) for k,v in attempt['expected_inputs'].items()]
    input_manifest=dict(PackageDirectory='/invented/package',RuntimeFiles=[prepared,dict(Destination='eeprom.bin',Sha256=job['manifest']['eeprom_sha256'],Bytes=256)],Inputs=inputs)
    write(evidence,'input-manifest.json',input_manifest)
    launch=dict(runId=run,job=native_id,executableSha256='1'*64,startPaused=False)
    write(evidence,'launch.json',launch)
    write(evidence,'crash/native/ready.json',dict(pid=42,identity='invented-owned-lifetime'))
    write(evidence,'crash/native/exit-native.json',dict(pid=42,identity='invented-owned-lifetime',exitCode=0,signal=None))
    raw='STORAGE-PERF-META version=1 fixture_generation=2 counter=rdtsc frequency=733444576 overhead_ticks=1\n'
    length=case['bytes_per_operation']
    raw+=''.join(f'STORAGE-PERF-OP id={case["id"]} index={i} ticks=183333 status=00000000 io_status=00000000 information={length}\n' for i in range(1024))
    public_fields='flush_calls=1024 persistence=1 read_calls=1024 write_calls=1024 ' if kind=='write-flush' else ''
    raw+=f'STORAGE-PERF-CASE id={case["id"]} operations=1024 bytes={length*1024} assertions={case["assertions"]} failures=0 ticks=187732992 cache={case["cache_policy"]} qd_actual={expected["queue_depth"]} available_pages=16000 {public_fields}\nSTORAGE-PERF-END cases=1 failures=0\n'
    (evidence/'native-serial.log').write_text(raw)
    maps=[dict(path='/usr/lib/libc.so.6',device='00:1a',inode='23',permissions='r-xp',address='1-2'),
        dict(path='[vdso]',device='00:00',inode='0',permissions='r-xp')]
    clock=dict(schema_version=1,errors={},monotonic_reads_ns=[10,11],clock=dict(implementation='clock_gettime(CLOCK_MONOTONIC)',monotonic=True,adjustable=False,resolution_seconds=1e-9),
        observer_boot_id='invented-boot',target_boot_id='invented-boot',observer_time_namespace='time:[1]',target_time_namespace='time:[1]',target_seccomp=0,
        interposition_variables_present=dict(LD_PRELOAD=False,LD_AUDIT=False),maps=maps,libc_mappings=maps[:1],vdso_mappings=maps[1:],
        libc_file=dict(path=maps[0]['path'],device=maps[0]['device'],inode='23',mapped_device='00:1a',mapped_inode='23',
            binding_method='maps-and-stat-device-inode-equal',bytes=100,sha256='c'*64),continuous_observation=False,constructor_branch_observed_directly=False)
    fd=dict(st_dev=os.makedev(0,26),st_ino=23,st_mode=0o100644,st_size=100,st_mtime_ns=1,st_ctime_ns=1)
    clock.update(libc_file_observations=dict(path=maps[0]['path'],mapped_device='00:1a',mapped_inode='23',before_fd=fd,after_fd=fd),target_mountinfo='')
    post=dict(schema_version=1,stage='post',guard_complete=True,error=None,target_pid=42,
        binding=dict(pid=42,uid=1000,exe_sha256=job['manifest']['xemu_sha256'],manifest=input_manifest,launch=launch,
            start_time_before='123',exe_path='/invented/xemu'),
        start_time_at_end='123',exe_path_at_end='/invented/xemu',clock_context=clock,
        serial_end=dict(strict_successful_END_verified=True,sha256=sha(evidence/'native-serial.log'),bytes=len(raw.encode()),offset_at_eof=len(raw.encode())),
        post_state=dict(status='shutdown',running=False))
    if case['kind']=='dvd-xiso':
        name='/invented/package/storage-perf.iso'
        post['recorder']={'path':name,'sha256':entry['boot_iso']['sha256'],'bytes':entry['boot_iso']['bytes']}
        post['actual_route']={'device':'ide0-cd1','actual_inserted_path':name,'raw_block':{
            'device':'ide0-cd1','removable':True,'locked':False,
            'inserted':{'file':name,'ro':True,'drv':'raw'}}}
    write(evidence,'native-storage-post-context.json',post)
    (evidence/'native-host-controls.txt').write_text('pid=42\nuid=1000\npolicy=dynamic powersave\n')
    write(evidence,'diagnostics/run-state/report.json',dict(Status='complete',ComparisonReady=True,DriverNamespaceVerified=True,CacheMode='cold',Issues=[]))
    # Produce the coherent preserved original ledger with the same reviewed double.
    collector_module=importlib.util.module_from_spec(importlib.util.spec_from_file_location('invented_collector',collector))
    collector_module.__spec__.loader.exec_module(collector_module);collector_module.configure(folder,sha(folder/'qualification-plan.json'))
    collector_module.native=tool.load_owned('storage_native_runner.py')
    row=dict(attempt_id=native_id,plan_sha256=sha(folder/'qualification-plan.json'),parser_sha256=plan['parser_sha256'],
        collector_sha256=sha(collector),performance_acceptance_eligible=False,status='qualified_for_declared_scope')
    observed=collector_module.observe(evidence,row);row.update(collector_module.evaluate(attempt,evidence,observed))
    ledger=folder/'ledger.jsonl';ledger.write_text(json.dumps(row)+'\n')
    return dict(folder=folder,collector=collector,review=review,ledger=ledger,schedule=schedule,job=job,
                evidence=evidence,native_id=native_id,clock_review_sha256=contract['review_receipt']['sha256'])


class PortableNativeImporter(unittest.TestCase):
    def importer(self, f):
        return load_tool().NativeImporter(collector_path=f['collector'],collector_sha256=sha(f['collector']),
            review_path=f['review'],review_sha256=sha(f['review']),evidence_root=f['folder']/'evidence',
            ledger_path=f['ledger'],ledger_sha256=sha(f['ledger']))

    def test_fresh_declared_binding_emits_counter_proof_and_retains_physical_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            f=portable_capture(pathlib.Path(temp),load_tool());importer=self.importer(f)
            importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
            row=importer.emit_job(f['native_id'],output_root=f['folder'])
            self.assertTrue(row['timing_qualified_for_declared_scope'],row.get('eligibility_reasons'))
            self.assertFalse(row['performance_acceptance_eligible'])
            self.assertIsNone(row['durability_verified']);self.assertNotIn('upper_worker_hops',row['counters'])
            comp=comparator_fixtures.load_tool()
            raw=json.loads((f['folder']/row['counter_provenance']['path']).read_text())
            self.assertEqual(raw['meta']['frequency'],'733444576')
            intervals,problem=comp.validate_counter_capture(f['schedule'],f['job'],row,f['folder'],{})
            self.assertIsNone(problem);self.assertNotEqual(float(intervals['latency'].center),row['elapsed_ms'])

    def test_context_boolean_coherent_counter_or_lifetime_changes_never_qualify(self):
        for fault in ('seccomp','namespace','libc','preload','monotonic','lifetime','EOF','host_policy','cache'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=portable_capture(pathlib.Path(temp),load_tool());path=f['evidence']/'native-storage-post-context.json';post=json.loads(path.read_text());c=post['clock_context']
                if fault=='seccomp':c['target_seccomp']=2
                if fault=='namespace':c['target_time_namespace']='time:[2]'
                if fault=='libc':c['libc_file']['sha256']='d'*64
                if fault=='preload':c['interposition_variables_present']['LD_PRELOAD']=True
                if fault=='monotonic':c['monotonic_reads_ns']=[11,10]
                if fault=='lifetime':post['start_time_at_end']='124'
                if fault=='EOF':post['serial_end']['bytes']+=1
                if fault=='host_policy':(f['evidence']/'native-host-controls.txt').write_text('pid=42\nuid=1000\npolicy=other\n')
                if fault=='cache':write(f['evidence'],'diagnostics/run-state/report.json',dict(Status='complete',ComparisonReady=False,DriverNamespaceVerified=False,CacheMode='cold',Issues=[]))
                write(f['evidence'],path.name,post)
                importer=self.importer(f);importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
                row=importer.emit_job(f['native_id'],output_root=f['folder'])
                self.assertFalse(row['timing_qualified_for_declared_scope']);self.assertNotIn('clock_provenance',row)
                self.assertTrue(row['eligibility_reasons']);self.assertEqual(row['runner_status'],'completed')

    def test_general_trust_and_changed_artifact_reject_before_collector_execution(self):
        with tempfile.TemporaryDirectory() as temp:
            f=portable_capture(pathlib.Path(temp),load_tool());pin=sha(f['collector']);review_pin=sha(f['review'])
            marker=f['folder']/'executed';f['collector'].write_text('from pathlib import Path\nPath('+repr(str(marker))+').touch()\n')
            with self.assertRaises(ValueError):load_tool().NativeImporter(collector_path=f['collector'],collector_sha256=pin,
                review_path=f['review'],review_sha256=review_pin,evidence_root=f['folder']/'evidence',ledger_path=f['ledger'],ledger_sha256=sha(f['ledger']))
            self.assertFalse(marker.exists())

    def test_wrong_precapture_bindings_native_workload_and_cohort_cannot_be_resealed_away(self):
        for fault in ('binding','declared_input','request','runner','cohort','case','source_role','clock_review'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory() as temp:
                f=portable_capture(pathlib.Path(temp),load_tool());importer=self.importer(f)
                if fault=='runner':importer.plan['schedule_sha256']='0'*64
                if fault=='cohort':importer.plan['timing_calibration_eligible']=False
                if fault in ('runner','cohort','clock_review'):
                    pin='0'*64 if fault=='clock_review' else f['clock_review_sha256']
                    with self.assertRaises(ValueError):importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=pin)
                    continue
                importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
                attempt=importer.declared[f['native_id']]
                if fault=='binding':
                    binding=json.loads((f['folder']/'inputs/aa-binding.json').read_text());binding['manifest_sha256']='0'*64
                    write(f['folder'],'inputs/aa-binding.json',binding)
                if fault=='declared_input':attempt['expected_inputs']['aa-binding.json']='0'*64
                if fault=='request':attempt['request_sha256']='0'*64
                if fault=='case':attempt['expected_case']['expected_operation_bytes'][-1]=1024
                if fault=='source_role':attempt['recorder_xbe_sha256']='0'*64
                row=importer.emit_job(f['native_id'],output_root=f['folder'])
                self.assertFalse(row['timing_qualified_for_declared_scope']);self.assertNotIn('clock_provenance',row)
                self.assertTrue(row['eligibility_reasons'])

    def test_public_write_raw_provenance_qualifies_timing_only_and_not_physical_flushes(self):
        with tempfile.TemporaryDirectory() as temp:
            f=portable_capture(pathlib.Path(temp),load_tool(),kind='write-flush');importer=self.importer(f)
            importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
            row=importer.emit_job(f['native_id'],output_root=f['folder'])
            self.assertTrue(row['timing_qualified_for_declared_scope'],row.get('eligibility_reasons'))
            self.assertEqual(row['flush_api_calls_completed'],1024);self.assertIsNone(row['flushes_completed']);self.assertIsNone(row['durability_verified'])
            comp=comparator_fixtures.load_tool()
            self.assertIsNone(comp.validate_public_write(f['schedule'],f['job'],row,f['folder'],{}))

    def test_guest_warmup_and_actual_host_cache_mode_are_independent(self):
        for changed in (False,True):
            with self.subTest(actual_host_changed=changed),tempfile.TemporaryDirectory() as temp:
                f=portable_capture(pathlib.Path(temp),load_tool(),kind='boundary-sg',cache_policy='warm');importer=self.importer(f)
                if changed:
                    report=json.loads((f['evidence']/'diagnostics/run-state/report.json').read_text())
                    report['CacheMode']='warm';write(f['evidence'],'diagnostics/run-state/report.json',report)
                importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
                row=importer.emit_job(f['native_id'],output_root=f['folder'])
                self.assertEqual(row['native']['cache_label'],'warm')
                self.assertEqual(row['timing_qualified_for_declared_scope'],not changed,row['eligibility_reasons'])
                if changed:self.assertNotIn('clock_provenance',row)

    def test_coherent_failed_native_outcome_and_duplicate_ledger_preserve_errors(self):
        with tempfile.TemporaryDirectory() as temp:
            f=portable_capture(pathlib.Path(temp),load_tool());row=json.loads(f['ledger'].read_text())
            result=json.loads((f['evidence']/'result.json').read_text());result.update(status='crashed',exitCode=17)
            write(f['evidence'],'result.json',result)
            row.update(result_sha256=sha(f['evidence']/'result.json'),runner_status='crashed',raw_exit_code=17)
            f['ledger'].write_text(json.dumps(row)+'\n')
            observed=self.importer(f).verify_attempt(f['native_id'])
            self.assertEqual(observed['verification_status'],'failed_verification');self.assertEqual(observed['runner_status'],'crashed');self.assertEqual(observed['raw_exit_code'],17)
            f['ledger'].write_text('{"attempt_id":"lost","attempt_id":"forged"}\n')
            with self.assertRaisesRegex(ValueError,'line 1.*duplicate'):self.importer(f)

    def test_native_pressure_zero_means_absent_target_and_positive_is_exact_integer(self):
        for pressure in (0,900):
            with self.subTest(pressure=pressure),tempfile.TemporaryDirectory() as temp:
                f=portable_capture(pathlib.Path(temp),load_tool(),kind='fatx-read',pressure_pages=pressure)
                importer=self.importer(f);importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
                attempt=importer.declared[f['native_id']];manifest=importer.collector.observe(f['evidence'],{})[2]
                job,_=importer._scheduled_job(attempt,manifest)
                self.assertEqual(job['case']['pressure_pages'],pressure)
                # An explicit None also means no clamp. Zero is a conflicting
                # requested target, rather than a spelling of absent evidence.
                if pressure==0:
                    attempt['expected_case']['pressure_target_pages']=None
                    importer._scheduled_job(attempt,manifest)
                invalid=(0,-1,True,1,900.0) if pressure==0 else (None,-1,False,900.0,901)
                for value in invalid:
                    with self.subTest(invalid_target=value):
                        attempt['expected_case']['pressure_target_pages']=value
                        with self.assertRaises(ValueError):importer._scheduled_job(attempt,manifest)


class RetainedWindowsClockContext(unittest.TestCase):
    """Portable actual V4 observations already retained in product documentation."""
    def test_actual_qpf_context_preserves_unknown_provider_and_cache_fields(self):
        tool = load_tool()
        context_path = ROOT / "docs/storage-replacement/native-observations/windows-clock-v4-context.json"
        receipt_path = ROOT / "docs/storage-replacement/windows-clock-context-native-receipt.json"
        observed = tool.verify_windows_context(context_path, receipt_path,
                                               receipt_sha256="feec2b6dedda11edf8d368731c0133526ac0e741ba3610b7e7e09e51f1d13fc2")
        self.assertEqual(observed["qpf_hz"], 10000000)
        self.assertEqual(observed["count_quantum_ns"], 100)
        self.assertFalse(observed["performance_eligible"])
        self.assertFalse(observed["provider_precision_proved"])
        self.assertIsNone(observed["single_step"])
        self.assertFalse(observed["driver_cache_verified"])

    def test_self_declared_review_and_coherent_changed_qpf_or_lifetime_reject(self):
        tool = load_tool()
        context_path = ROOT / "docs/storage-replacement/native-observations/windows-clock-v4-context.json"
        receipt_path = ROOT / "docs/storage-replacement/windows-clock-context-native-receipt.json"
        original = json.loads(context_path.read_text())
        for fault in ("review", "frequency", "lifetime", "paused"):
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as temp:
                folder = pathlib.Path(temp)
                value = copy.deepcopy(original)
                receipt = json.loads(receipt_path.read_text())
                if fault == "review": receipt["status"] = "SELF_DECLARED_REVIEWED"
                if fault == "frequency": value["final_clock"]["qpf_frequency_dec"] = "3000001"
                if fault == "lifetime": value["final_process"]["start_ticks"] += 1
                if fault == "paused": value["initial_managed_status"]["response"]["running"] = False
                target = folder / "context.json";target.write_text(json.dumps(value))
                for entry in receipt["raw_portable_artifacts"]:
                    if entry["path"].endswith("context.json"):
                        entry.update(sha256=sha(target),bytes=target.stat().st_size)
                receipt["actual_clock_samples"] = {"initial":value["initial_clock"],"final":value["final_clock"]}
                reviewed = folder / "receipt.json";reviewed.write_text(json.dumps(receipt))
                # The review forgery keeps the real trusted pin. Other mutations deliberately
                # update checksums to exercise semantic validation, not only hash rejection.
                pin = "feec2b6dedda11edf8d368731c0133526ac0e741ba3610b7e7e09e51f1d13fc2" if fault == "review" else sha(reviewed)
                with self.assertRaises(ValueError): tool.verify_windows_context(target,reviewed,receipt_sha256=pin)


class RetainedDeckArchive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        location = os.environ.get("STORAGE_NATIVE_IMPORT_ARCHIVE")
        if not location:
            raise unittest.SkipTest("set STORAGE_NATIVE_IMPORT_ARCHIVE to the retained native evidence directory")
        cls.archive = pathlib.Path(location)
        cls.tool = load_tool()
        cls.collector = cls.archive / "frozen-fixture-v32-full36/qualification-collector.py"
        cls.review = cls.archive / "v32-root-review-receipt.json"
        cls.ledger = cls.archive / "deck-v32-full36-fixed-wrapper-functional-qualification.jsonl"

    def importer(self, ledger=None):
        return self.tool.NativeImporter(
            collector_path=self.collector, collector_sha256="8463a75f7a9138c49730adbf8d116db407265cf063e3eac4bdeb35ba706c7483",
            review_path=self.review, review_sha256=sha(self.review),
            evidence_root=self.archive / "evidence", ledger_path=ledger or self.ledger,
            ledger_sha256=sha(ledger or self.ledger))

    def test_actual_all36_functional_leaf_replay_retains_seed_and_physical_unknown(self):
        importer = self.importer()
        observations = [importer.verify_attempt(row["attempt_id"]) for row in importer.rows]
        self.assertEqual(len(observations), 36)
        self.assertTrue(all(row["verification_status"] == "verified_native_functional" for row in observations))
        self.assertEqual(sum(row["native"]["operations_completed"] for row in observations), 36864)
        self.assertTrue(all(not row["performance_eligible"] for row in observations))
        self.assertTrue(all(row["prepared_image"]["source_seed_sha256"] ==
                            "78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b" for row in observations))
        self.assertGreater(len({row["prepared_image"]["sha256"] for row in observations}), 1)
        self.assertTrue(all(row["native"]["durability_verified"] is None for row in observations))

    def test_coherent_ledger_claim_cannot_override_actual_plan_or_failed_result(self):
        original = [json.loads(line) for line in self.ledger.read_text().splitlines()]
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            for fault in ("eligible", "duplicate"):
                with self.subTest(fault=fault):
                    rows = copy.deepcopy(original)
                    if fault == "eligible": rows[0]["performance_acceptance_eligible"] = True
                    else: rows[1]["run_id"] = rows[0]["run_id"]
                    ledger = folder / (fault + ".jsonl")
                    ledger.write_text("".join(json.dumps(row) + "\n" for row in rows))
                    if fault == "duplicate":
                        with self.assertRaises(ValueError): self.importer(ledger)
                    else:
                        observed = self.importer(ledger).verify_attempt(rows[0]["attempt_id"])
                        self.assertEqual(observed["verification_status"], "failed_verification")
                        self.assertFalse(observed["performance_eligible"])
                        self.assertEqual(observed["runner_status"], "completed")

    def test_unapproved_collector_or_review_rejects_before_code_can_run(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);fake = folder / "collector.py"
            marker = folder / "executed"
            fake.write_text("from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n")
            with self.assertRaises(ValueError):
                self.tool.NativeImporter(collector_path=fake,
                    collector_sha256="8463a75f7a9138c49730adbf8d116db407265cf063e3eac4bdeb35ba706c7483",
                    review_path=self.review,review_sha256=sha(self.review),evidence_root=self.archive / "evidence",
                    ledger_path=self.ledger,ledger_sha256=sha(self.ledger))
            self.assertFalse(marker.exists())

    def test_actual_post_end_btrfs_context_passes_bounded_checks_without_promoting_pilot(self):
        freeze=self.archive/'frozen-fixture-v343-storage-post'
        ledger=self.archive/'deck-v343-qualification.jsonl';review=self.archive/'v343-root-review-receipt.json'
        importer=self.tool.NativeImporter(collector_path=freeze/'qualification-collector.py',
            collector_sha256='4c64d1f83854941ddfc6af20673f7b32552155c39e86b588bf0acff98f81ed9b',
            review_path=review,review_sha256=sha(review),evidence_root=self.archive/'evidence',
            ledger_path=ledger,ledger_sha256=sha(ledger))
        actual=importer.rows[0];observed=importer.verify_attempt(actual['attempt_id'])
        self.assertEqual(observed['verification_status'],'verified_native_functional',observed.get('error'))
        self.assertFalse(observed['performance_eligible']);self.assertFalse(importer.plan['timing_calibration_eligible'])
        evidence=self.archive/'evidence'/actual['run_id'];post=json.loads((evidence/'native-storage-post-context.json').read_text())
        importer.contract={'runtime_requirements':{'libc_sha256':post['clock_context']['libc_file']['sha256'],
            'host_controls':{'/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor':'powersave'}}}
        raw=importer.collector.observe(evidence,{})
        job={'manifest':{'xemu_sha256':importer.plan['hosts']['deck']['emulator_sha256']}}
        checked=importer._context(evidence,raw,job)
        self.assertEqual(checked['clock_context']['libc_file']['binding_method'],'btrfs-root-subvolume-map-files')
        self.assertNotEqual(checked['clock_context']['libc_file']['device'],checked['clock_context']['libc_file']['mapped_device'])


class PortableDvdMediaImporter(unittest.TestCase):
    importer = PortableNativeImporter.importer
    def test_DVD_emitter_populates_actual_wrapper_and_separate_original_before_comparator(self):
        for variant in ('standard','alternate'):
            with self.subTest(variant=variant),tempfile.TemporaryDirectory() as temp:
                f=portable_capture(pathlib.Path(temp),load_tool(),kind='dvd-xiso',variant=variant)
                importer=self.importer(f);importer.configure_schedule(f['schedule'],artifact_root=f['folder'],clock_review_sha256=f['clock_review_sha256'])
                row=importer.emit_job(f['native_id'],output_root=f['folder'])
                self.assertTrue(row['timing_qualified_for_declared_scope'],row.get('eligibility_reasons'))
                self.assertEqual(row.get('media_sha256'),f['job']['case']['iso_sha256'])
                entry=f['schedule']['spec']['artifact_policy']['cases'][row['case_id']]
                self.assertEqual(row['original_released_iso_sha256'],entry['original_released_iso']['sha256'])
                self.assertNotEqual(row['media_sha256'],row['original_released_iso_sha256'])
                self.assertFalse(row['exact_original_media_parity']);self.assertEqual(row['media_method'],'fixed-wrapper')
                comp=comparator_fixtures.load_tool();metrics,issues,failures,_=comp.inspect_records(f['schedule'],[row],evidence_root=f['folder'])
                self.assertIn(row['attempt_id'],metrics);self.assertEqual([x for x in issues if not x.endswith('missing attempt')],[]);self.assertEqual(failures,[])

class RetainedDvdMediaImporter(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        location=os.environ.get('STORAGE_NATIVE_IMPORT_CYCLE72')
        if not location:raise unittest.SkipTest('set immutable actual first72 archive; no live ledger reads')
        cls.archive=pathlib.Path(location);cls.freeze=cls.archive/'deck-aa-v352-preparation'
        path=cls.archive/'v352-first-cycle-import.jsonl'
        assert sha(path)=='70738c086e853b459bf3c941fc3a8d9992ea4867f6ca79fe85a90e32493896db'
        cls.rows=[json.loads(x) for x in path.read_text().splitlines()];cls.schedule=json.loads((cls.freeze/'schedule.json').read_text());cls.plan=json.loads((cls.freeze/'qualification-plan.json').read_text())
        cls.comp=comparator_fixtures.load_tool();cls.tool=load_tool();cls.importer=cls.tool.NativeImporter.__new__(cls.tool.NativeImporter)
        cls.importer.comp=cls.comp;cls.importer.artifact_root=cls.freeze
    def data(self,row):
        job=next(j for j in self.schedule['jobs'] if j['attempt_id']==row['attempt_id']);attempt=next(a for a in self.plan['attempts'] if a['id']==row['native_attempt_id']);entry=self.schedule['spec']['artifact_policy']['cases'][row['case_id']]
        manifest=json.loads((self.archive/'evidence'/row['native_run_id']/'input-manifest.json').read_text())
        return copy.deepcopy(attempt),copy.deepcopy(manifest),copy.deepcopy(job['case']),copy.deepcopy(entry),copy.deepcopy(row['dvd_media']['post'])
    def test_actual72_red_shape_then_diagnostic_corrected_fields_cover_both_DVD_variants(self):
        metrics,issues,failures,_=self.comp.inspect_records(self.schedule,self.rows,evidence_root=self.freeze)
        self.assertEqual(len(metrics),64);self.assertEqual(sum('optical variant media hash mismatch' in x for x in issues),8)
        repaired=copy.deepcopy(self.rows);observed=set()
        for row in repaired:
            if row['case_id'].startswith('dvd-'):
                values=self.data(row);fields=self.importer._dvd_media_fields(*values);row.update(fields)
                self.assertEqual(row['media_sha256'],values[2]['iso_sha256']);self.assertFalse(row['exact_original_media_parity'])
                self.assertEqual(row['dvd_media'],next(r['dvd_media'] for r in self.rows if r['attempt_id']==row['attempt_id']))
                observed.add((row['media_sha256'],row['original_released_iso_sha256']))
        self.assertEqual(observed,{('6b8c26ab5201eef7d213d6329b5cddc225a8c2f60c403df7ae48491ecd5d0bd7','8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475'),('9c3e20d49cad3886f0b341b4bfe4c4f24c5afa9c13632f09e246d0ac67d4d180','099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33')})
        metrics,issues,failures,_=self.comp.inspect_records(self.schedule,repaired,evidence_root=self.freeze)
        self.assertEqual(len(metrics),72);self.assertEqual(sum(x.endswith('missing attempt') for x in issues),288)
        self.assertEqual([x for x in issues if not x.endswith('missing attempt')],[]);self.assertEqual(failures,[])
        # This is diagnostic dictionary repair, not a new clock verifier/schedule
        # qualification. Original rows, proofs, context and immutable plan remain unchanged.
    def test_actual_original_input_and_wrapper_route_faults_reject(self):
        row=next(r for r in self.rows if r['case_id'].startswith('dvd-'))
        for fault in ('missing_original','wrong_original','wrong_expected_original','unverified_original','duplicate_original','coherent_foreign_original','missing_frozen_original','wrong_wrapper','wrong_route','writable_route','parity_claim'):
            with self.subTest(fault=fault):
                a,m,c,e,p=self.data(row);original=next(x for x in m['Inputs'] if x['Path']=='target.iso')
                if fault=='missing_original':m['Inputs'].remove(original)
                if fault=='wrong_original':original['Sha256']='f'*64
                if fault=='wrong_expected_original':original['ExpectedSha256']='f'*64
                if fault=='unverified_original':original['Verified']=False
                if fault=='duplicate_original':m['Inputs'].append(copy.deepcopy(original))
                if fault=='coherent_foreign_original':original.update(Sha256='f'*64,ExpectedSha256='f'*64);a['expected_inputs']['target.iso']='f'*64;a['dvd_binding']['original_released_iso_sha256']='f'*64
                if fault=='missing_frozen_original':del a['expected_inputs']['target.iso']
                if fault=='wrong_wrapper':p['recorder']['sha256']='f'*64
                if fault=='wrong_route':p['actual_route']['raw_block']['inserted']['file']='/foreign/target.iso'
                if fault=='writable_route':p['actual_route']['raw_block']['inserted']['ro']=False
                if fault=='parity_claim':a['dvd_binding']['exact_original_media_parity']=True
                with self.assertRaises(ValueError):self.importer._dvd_media_fields(a,m,c,e,p)
    def test_changed_verifier_cannot_reuse_original_V352_clock_contract(self):
        probe=self.tool.NativeImporter.__new__(self.tool.NativeImporter)
        probe.plan=copy.deepcopy(self.plan);probe.collector_path=self.freeze/'qualification-collector.py'
        with self.assertRaisesRegex(ValueError,'clock contract does not identify the executed importer/helper'):
            probe.configure_schedule(self.schedule,artifact_root=self.freeze,
                clock_review_sha256='c99659264ca9b338af0d254d6ab43479e2fb52b6e2a0437ce79a65faecd6d6f6')
