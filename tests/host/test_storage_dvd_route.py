"""Invented managed QMP media faults; no runner or VM execution."""
import copy,hashlib,importlib.util,json,pathlib,shutil,subprocess,sys,tempfile,unittest
SOURCE=pathlib.Path(__file__).parents[2]/'tests/xbe/storage-perf/dvd-route-observer.py'
def subject():
 spec=importlib.util.spec_from_file_location('dvd_route_subject',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class DvdRouteTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('cc'),'actual DVD control test requires host compiler')
 def test_actual_dvd_method_grace_is_outside_unchanged_verification_loop(self):
  fixture=SOURCE.parent
  with tempfile.TemporaryDirectory(prefix='pr248-dvd-grace-') as work:
   directory=pathlib.Path(work);shutil.copy2(fixture/'dvd.c',directory/'owned-dvd.c')
   (directory/'dvd-metadata-reference.h').write_text('static const UCHAR dvd_clean_header[4096]={0};\nstatic const UCHAR dvd_performance_header[4096]={0};\n#define DVD_CLEAN_FILE_BYTES 565248\n#define DVD_PERFORMANCE_FILE_BYTES 573440\n')
   for name,ticks,flags in [('default',5000000,[]),('method',200000000,['-DSTORAGE_DVD_POST_END_GRACE_100NS=200000000'])]:
    executable=directory/name
    subprocess.run(['cc','-std=gnu11','-O0',*flags,'-I'+str(directory),'-I'+str(fixture/'host-mock'),'-I'+str(fixture),str(fixture/'host-mock/dvd-mock.c'),'-o',str(executable)],check=True,capture_output=True)
    raw=subprocess.run([str(executable),'fill'],check=True,capture_output=True,text=True).stdout
    self.assertIn('STORAGE-PERF-END cases=1 failures=0',raw)
    self.assertIn('MOCK-DVD-POWEROFF last_delay_100ns=-'+str(ticks),raw)
    self.assertLess(raw.index('STORAGE-PERF-END'),raw.index('MOCK-DVD-POWEROFF'))
    self.assertIn('operations=1024 bytes=4194304',raw)
    fixed=subprocess.run([str(executable),'fixed-route'],check=True,capture_output=True,text=True).stdout
    self.assertIn('MOCK-FIXED-ROUTE target_opens=1 dismount_calls=0',fixed)
    self.assertIn('operations=1024 bytes=4194304',fixed)

 @unittest.skipUnless(shutil.which('cc'),'actual query count test requires host compiler')
 def test_short_preflight_query_count_refuses_to_start_measurement(self):
  fixture=SOURCE.parent
  with tempfile.TemporaryDirectory(prefix='pr248-dvd-query-count-') as work:
   directory=pathlib.Path(work);shutil.copy2(fixture/'dvd.c',directory/'owned-dvd.c')
   (directory/'dvd-metadata-reference.h').write_text('static const UCHAR dvd_clean_header[4096]={0};\nstatic const UCHAR dvd_performance_header[4096]={0};\n#define DVD_CLEAN_FILE_BYTES 565248\n#define DVD_PERFORMANCE_FILE_BYTES 573440\n')
   executable=directory/'query-count'
   subprocess.run(['cc','-std=gnu11','-O0','-I'+str(directory),'-I'+str(fixture/'host-mock'),'-I'+str(fixture),str(fixture/'host-mock/dvd-mock.c'),'-o',str(executable)],check=True,capture_output=True)
   raw=subprocess.run([str(executable),'query-short'],check=True,capture_output=True,text=True).stdout
   self.assertIn('STORAGE-PERF-ERROR stage=wrapper-target-length',raw)
   self.assertNotIn('STORAGE-PERF-CASE',raw)
   self.assertNotIn('STORAGE-PERF-END',raw)

 def test_unique_actual_removable_route_and_exact_owned_source(self):
  self.assertTrue(SOURCE.exists(),'owned managed DVD receipt guard missing');m=subject()
  package=pathlib.Path('/owned/job');source=package/'storage-perf.iso'
  dvd={'device':'ide0-cd1','removable':True,'locked':False,'inserted':{'file':str(source),'ro':True,'drv':'raw'}}
  hdd={'device':'ide0-hd0','removable':False,'locked':True,'inserted':{'file':'/owned/runtime/hdd.qcow2','ro':False,'drv':'qcow2'}}
  observed=m.validate_media_route([hdd,dvd],package,source,'ide0-cd1')
  self.assertEqual(observed['device'],dvd['device']);self.assertEqual(observed['actual_inserted_path'],str(source));self.assertEqual(observed['raw_block'],dvd)
  for key,value in [('device','foreign'),('removable',False),('locked',True)]:
   changed=copy.deepcopy(dvd);changed[key]=value
   with self.subTest(key=key),self.assertRaises(ValueError):m.validate_media_route([hdd,changed],package,source,'ide0-cd1')
  for key,value in [('file','/foreign/target.iso'),('ro',False),('ro','true'),('drv','qcow2')]:
   changed=copy.deepcopy(dvd);changed['inserted'][key]=value
   with self.subTest(inserted=key),self.assertRaises(ValueError):m.validate_media_route([hdd,changed],package,source,'ide0-cd1')
  for blocks in ([hdd],[hdd,dvd,dvd],{'device':'ide0-cd1'},[hdd,{**dvd,'inserted':{}}]):
   with self.subTest(blocks=blocks),self.assertRaises(ValueError):m.validate_media_route(blocks,package,source,'ide0-cd1')
  relative=copy.deepcopy(dvd);relative['inserted']['file']='storage-perf.iso'
  self.assertEqual(m.validate_media_route([hdd,relative],package,source,'ide0-cd1')['actual_inserted_path'],str(source))
 def test_typed_recipe_actual_binding_and_recursive_failure_retention(self):
  self.assertTrue(SOURCE.exists(),'owned managed DVD receipt guard missing');m=subject()
  with tempfile.TemporaryDirectory(prefix='pr248-dvd-recipe-') as work:
   result=pathlib.Path(work);directory=result/'diagnostics/20261014-0000-dvd-qmp-initial';directory.mkdir(parents=True)
   request={'Id':'dvd-qmp-initial','Type':'qmp','QmpCommand':'query-block','QmpArguments':{},'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}
   outcome={'Id':'dvd-qmp-initial','Type':'qmp','Status':'completed','Directory':str(directory),'Artifacts':['qmp-result.json'],'Detail':None,'StartedUtc':'2026-10-14T00:00:00+00:00','EndedUtc':'2026-10-14T00:00:01+00:00'}
   for name,data in [('request.json',request),('result.json',outcome),('qmp-result.json',[])]: (directory/name).write_text(json.dumps(data))
   value=m.read_recipe(result,'dvd-qmp-initial','query-block',{},str(result));self.assertEqual(value['response'],[]);self.assertEqual(len(value['artifact_sha256']),3)
   for file,key,data in [('request.json','QmpCommand','query-status'),('request.json','PauseBefore',True),('result.json','Status','failed'),('result.json','Directory','/foreign/result'),('result.json','Artifacts',[]),('result.json','EndedUtc','2025-10-14T00:00:01+00:00')]:
    path=directory/file;original=path.read_bytes();mutated=json.loads(original);mutated[key]=data;path.write_text(json.dumps(mutated))
    with self.subTest(file=file,key=key),self.assertRaises(ValueError):m.read_recipe(result,'dvd-qmp-initial','query-block',{},str(result))
    path.write_bytes(original)
   (directory/'qmp-result.json').write_text('[{"removable":false,"removable":true}]')
   with self.assertRaisesRegex(ValueError,'duplicate'):m.read_recipe(result,'dvd-qmp-initial','query-block',{},str(result))
 def test_source_and_target_hashes_are_actually_measured_before_control(self):
  self.assertTrue(SOURCE.exists(),'owned managed DVD receipt guard missing');m=subject()
  with tempfile.TemporaryDirectory(prefix='pr248-dvd-input-') as work:
   package=pathlib.Path(work);data=b'known own public ISO bytes';(package/'target.iso').write_bytes(data);expected=hashlib.sha256(data).hexdigest()
   value=m.input_receipt(package,'target.iso',expected);self.assertEqual(value['sha256'],expected);self.assertEqual(value['path'],str(package/'target.iso'))
   observed={}
   with self.assertRaises(ValueError):m.input_receipt(package,'target.iso','f'*64,observation=observed)
   self.assertEqual(observed['sha256'],expected)
   self.assertEqual(observed['bytes'],len(data))
   with self.assertRaises(ValueError):m.input_receipt(package,'../foreign.iso',expected)
   (package/'alias.iso').symlink_to(package/'target.iso')
   with self.assertRaises(ValueError):m.input_receipt(package,'alias.iso',expected)

 @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('cc'),'actual owned process guard requires Linux host compiler')
 def test_actual_guard_main_retains_failed_input_and_observes_owned_process(self):
  with tempfile.TemporaryDirectory(prefix='pr248-dvd-main-') as work:
   root=pathlib.Path(work);package=root/'package';result=root/'run';package.mkdir();result.mkdir()
   c=root/'mock.c';c.write_text('#include <unistd.h>\nint main(void){for(;;)pause();}\n')
   subprocess.run(['cc',str(c),'-o',str(package/'xemu')],check=True,capture_output=True)
   guard=SOURCE.with_name('clock-observer.py');shutil.copy2(guard,package/'clock-observer.py')
   (package/'xemu.toml').write_text('owned host config\n');effective=result/'diagnostics/run-state/effective-live.toml';effective.parent.mkdir(parents=True);effective.write_text('owned isolated host config\n')
   for name,data in [('storage-perf.iso',b'owned recorder'),('target.iso',b'known target')]: (package/name).write_bytes(data)
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   process=subprocess.Popen(['./xemu','-m','64','-config_path',str(effective)],cwd=package)
   try:
    identity='pr248-native-host-dvd-main'
    (result/'launch.json').write_text(json.dumps({'job':identity,'runId':result.name,'arguments':['-config_path',str(package/'xemu.toml'),'-m','64']}))
    inputs=[{'Path':name,'Verified':True,'Sha256':sha(package/name),'ExpectedSha256':sha(package/name)} for name in ['xemu','xemu.toml','storage-perf.iso','target.iso']]
    (result/'input-manifest.json').write_text(json.dumps({'JobId':identity,'Inputs':inputs}))
    (result/'native-host-controls.txt').write_text(f'pid={process.pid}\n')
    (effective.parent/'report.json').write_text(json.dumps({'Status':'prepared','ConfigSourcePath':str(package/'xemu.toml'),'ConfigSha256':sha(package/'xemu.toml'),'EffectiveConfigPath':str(effective),'EffectiveConfigSha256':sha(effective)}))
    directory=result/'diagnostics/20261014-0000-dvd-qmp-initial';directory.mkdir()
    (directory/'request.json').write_text(json.dumps({'Id':'dvd-qmp-initial','Type':'qmp','QmpCommand':'query-block','QmpArguments':{},'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}))
    (directory/'result.json').write_text(json.dumps({'Id':'dvd-qmp-initial','Type':'qmp','Status':'completed','Directory':str(directory),'Artifacts':['qmp-result.json'],'Detail':None,'StartedUtc':'2026-10-14T00:00:00+00:00','EndedUtc':'2026-10-14T00:00:01+00:00'}))
    blocks=[{'device':'ide0-cd1','removable':True,'locked':False,'inserted':{'file':str(package/'storage-perf.iso'),'ro':True,'drv':'raw'}}]
    (directory/'qmp-result.json').write_text(json.dumps(blocks))
    command=[sys.executable,'-B',str(SOURCE),'--stage','initial','--pid',str(process.pid),'--package',str(package),'--result',str(result),'--expected-job',identity,'--expected-device','ide0-cd1','--expected-xemu-sha256',sha(package/'xemu'),'--expected-config-sha256',sha(package/'xemu.toml'),'--expected-guard-sha256',sha(package/'clock-observer.py'),'--expected-recorder-sha256',sha(package/'storage-perf.iso'),'--expected-target-sha256',sha(package/'target.iso')]
    completed=subprocess.run(command,capture_output=True,text=True,timeout=10)
    self.assertEqual(completed.returncode,0,completed.stderr)
    actual=json.loads((result/'native-dvd-initial-guard.json').read_text());self.assertTrue(actual['guard_complete']);self.assertEqual(actual['binding']['pid'],process.pid);self.assertEqual(actual['actual_route']['raw_block'],blocks[0])
    initial_bytes=(result/'native-dvd-initial-guard.json').read_bytes()
    for marker,operation,arguments,start,end,response in [
     ('change','blockdev-change-medium',subject().change_arguments('ide0-cd1'),2,3,{}),
     ('final','query-block',{},4,5,[{**blocks[0],'inserted':{'file':'target.iso','ro':True,'drv':'raw'}}])]:
     part=result/('diagnostics/20261014-0000-dvd-qmp-'+marker);part.mkdir()
     (part/'request.json').write_text(json.dumps({'Id':'dvd-qmp-'+marker,'Type':'qmp','QmpCommand':operation,'QmpArguments':arguments,'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}))
     (part/'result.json').write_text(json.dumps({'Id':'dvd-qmp-'+marker,'Type':'qmp','Status':'completed','Directory':str(part),'Artifacts':['qmp-result.json'],'Detail':None,'StartedUtc':f'2026-10-14T00:00:0{start}+00:00','EndedUtc':f'2026-10-14T00:00:0{end}+00:00'}))
     (part/'qmp-result.json').write_text(json.dumps(response))
    final=command.copy();final[final.index('--stage')+1]='final'
    completed=subprocess.run(final,capture_output=True,text=True,timeout=10)
    self.assertEqual(completed.returncode,0,completed.stderr)
    actual=json.loads((result/'native-dvd-final-guard.json').read_text());self.assertTrue(actual['guard_complete']);self.assertEqual(actual['initial_guard_sha256'],hashlib.sha256(initial_bytes).hexdigest());self.assertEqual(actual['managed_change']['response'],{})
    change=result/'diagnostics/20261014-0000-dvd-qmp-change/qmp-result.json';change.write_text('{"error":"retained failed medium change"}')
    failed=subprocess.run(final,capture_output=True,text=True,timeout=10);self.assertNotEqual(failed.returncode,0)
    actual=json.loads((result/'native-dvd-final-guard.json').read_text());self.assertFalse(actual['guard_complete']);self.assertIn('managed change',actual['error']);self.assertEqual(actual['managed_change']['response']['error'],'retained failed medium change');self.assertEqual(actual['binding']['pid'],process.pid)
    change.write_text('{}')
    old=json.loads(initial_bytes);old['binding']['start_time_before']+=1;(result/'native-dvd-initial-guard.json').write_text(json.dumps(old))
    failed=subprocess.run(final,capture_output=True,text=True,timeout=10);self.assertNotEqual(failed.returncode,0)
    actual=json.loads((result/'native-dvd-final-guard.json').read_text());self.assertFalse(actual['guard_complete']);self.assertIn('lifetime',actual['error']);self.assertEqual(actual['actual_route']['actual_inserted_path'],str(package/'target.iso'))
    (result/'native-dvd-initial-guard.json').write_bytes(initial_bytes)
    command[-1]='f'*64;failed=subprocess.run(command,capture_output=True,text=True,timeout=10);self.assertNotEqual(failed.returncode,0)
    actual=json.loads((result/'native-dvd-initial-guard.json').read_text());self.assertFalse(actual['guard_complete']);self.assertIn('input hash',actual['error']);self.assertEqual(actual['target']['sha256'],sha(package/'target.iso'));self.assertEqual(actual['binding']['pid'],process.pid)
   finally:
    process.terminate()
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
if __name__=='__main__':unittest.main()
