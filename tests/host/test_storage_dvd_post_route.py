"""Invented managed QMP media faults; no runner or VM execution."""
import copy,hashlib,importlib.util,json,pathlib,shutil,subprocess,sys,tempfile,unittest
SOURCE=pathlib.Path(__file__).parents[2]/'tests/xbe/storage-perf/dvd-post-route-observer.py'
def subject():
 spec=importlib.util.spec_from_file_location('dvd_route_subject',SOURCE);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
class DvdPostRouteTests(unittest.TestCase):
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
  with self.assertRaises(ValueError):m.validate_media_route([dvd,{**dvd,'removable':False}],package,source,'ide0-cd1')
  relative=copy.deepcopy(dvd);relative['inserted']['file']='storage-perf.iso'
  self.assertEqual(m.validate_media_route([hdd,relative],package,source,'ide0-cd1')['actual_inserted_path'],str(source))
 def test_typed_recipe_actual_binding_and_recursive_failure_retention(self):
  self.assertTrue(SOURCE.exists(),'owned managed DVD receipt guard missing');m=subject()
  with tempfile.TemporaryDirectory(prefix='pr248-dvd-recipe-') as work:
   result=pathlib.Path(work);directory=result/'diagnostics/20261014-0000-dvd-qmp-post';directory.mkdir(parents=True)
   request={'Id':'dvd-qmp-post','Type':'qmp','QmpCommand':'query-block','QmpArguments':{},'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}
   outcome={'Id':'dvd-qmp-post','Type':'qmp','Status':'completed','Directory':str(directory),'Artifacts':['qmp-result.json'],'Detail':None,'StartedUtc':'2026-10-14T00:00:00+00:00','EndedUtc':'2026-10-14T00:00:01+00:00'}
   for name,data in [('request.json',request),('result.json',outcome),('qmp-result.json',[])]: (directory/name).write_text(json.dumps(data))
   value=m.read_recipe(result,'dvd-qmp-post','query-block',{},str(result));self.assertEqual(value['response'],[]);self.assertEqual(len(value['artifact_sha256']),3)
   for file,key,data in [('request.json','QmpCommand','query-status'),('request.json','PauseBefore',True),('result.json','Status','failed'),('result.json','Directory','/foreign/result'),('result.json','Artifacts',[]),('result.json','EndedUtc','2025-10-14T00:00:01+00:00')]:
    path=directory/file;original=path.read_bytes();mutated=json.loads(original);mutated[key]=data;path.write_text(json.dumps(mutated))
    with self.subTest(file=file,key=key),self.assertRaises(ValueError):m.read_recipe(result,'dvd-qmp-post','query-block',{},str(result))
    path.write_bytes(original)
   (directory/'qmp-result.json').write_text('[{"removable":false,"removable":true}]')
   with self.assertRaisesRegex(ValueError,'duplicate'):m.read_recipe(result,'dvd-qmp-post','query-block',{},str(result))
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
   parser=SOURCE.parents[3]/'tools/storage_native_runner.py';shutil.copy2(parser,package/'storage_native_runner.py')
   (package/'xemu.toml').write_text('owned host config\n');effective=result/'diagnostics/run-state/effective-live.toml';effective.parent.mkdir(parents=True);effective.write_text('owned isolated host config\n')
   for name,data in [('storage-perf.iso',b'owned recorder'),('target.iso',b'known target')]: (package/name).write_bytes(data)
   sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
   process=subprocess.Popen(['./xemu','-m','64','-serial','file:'+str(result/'native-serial.log'),'-config_path',str(effective)],cwd=package)
   try:
    identity='pr248-native-host-dvd-post'
    serial='# STORAGE-PERF-META version=1 fixture_generation=2 counter=rdtsc media=fixed-wrapper frequency=1000000 overhead_ticks=8\n'+''.join(f'# STORAGE-PERF-OP id=dvd-api-leaf-clean.cold-ish index={i} ticks=1 status=00000000 io_status=00000000 information=4096 apcs=0\n' for i in range(1024))+'# STORAGE-PERF-CASE id=dvd-api-leaf-clean.cold-ish operations=1024 bytes=4194304 ticks=2048 assertions=4096 failures=0 flush_calls=0 persistence=0 qd_actual=1 available_pages=15000 cache=cold-ish\n# STORAGE-PERF-END cases=1 failures=0\n'
    (result/'native-serial.log').write_text(serial)
    (result/'launch.json').write_text(json.dumps({'job':identity,'runId':result.name,'arguments':['-config_path',str(package/'xemu.toml'),'-m','64','-serial','file:'+str(result/'native-serial.log')]}))
    inputs=[{'Path':name,'Verified':True,'Sha256':sha(package/name),'ExpectedSha256':sha(package/name)} for name in ['xemu','xemu.toml','storage-perf.iso','target.iso','storage_native_runner.py']]
    (result/'input-manifest.json').write_text(json.dumps({'JobId':identity,'Inputs':inputs}))
    (result/'native-host-controls.txt').write_text(f'pid={process.pid}\n')
    (effective.parent/'report.json').write_text(json.dumps({'Status':'prepared','ConfigSourcePath':str(package/'xemu.toml'),'ConfigSha256':sha(package/'xemu.toml'),'EffectiveConfigPath':str(effective),'EffectiveConfigSha256':sha(effective)}))
    directory=result/'diagnostics/20261014-0000-dvd-qmp-post';directory.mkdir()
    (directory/'request.json').write_text(json.dumps({'Id':'dvd-qmp-post','Type':'qmp','QmpCommand':'query-block','QmpArguments':{},'PauseBefore':False,'PauseAfter':False,'ResumeDuring':False}))
    (directory/'result.json').write_text(json.dumps({'Id':'dvd-qmp-post','Type':'qmp','Status':'completed','Directory':str(directory),'Artifacts':['qmp-result.json'],'Detail':None,'StartedUtc':'2026-10-14T00:00:00+00:00','EndedUtc':'2026-10-14T00:00:01+00:00'}))
    blocks=[{'device':'ide0-cd1','removable':True,'locked':False,'inserted':{'file':str(package/'storage-perf.iso'),'ro':True,'drv':'raw'}}]
    (directory/'qmp-result.json').write_text(json.dumps(blocks))
    command=[sys.executable,'-B',str(SOURCE),'--stage','post','--pid',str(process.pid),'--package',str(package),'--result',str(result),'--expected-job',identity,'--expected-device','ide0-cd1','--expected-xemu-sha256',sha(package/'xemu'),'--expected-config-sha256',sha(package/'xemu.toml'),'--expected-guard-sha256',sha(package/'clock-observer.py'),'--expected-recorder-sha256',sha(package/'storage-perf.iso'),'--expected-target-sha256',sha(package/'target.iso'),'--expected-parser-sha256',sha(package/'storage_native_runner.py'),'--expected-case','dvd-api-leaf-clean.cold-ish']
    completed=subprocess.run(command,capture_output=True,text=True,timeout=10)
    self.assertEqual(completed.returncode,0,completed.stderr)
    actual=json.loads((result/'native-dvd-post-guard.json').read_text());self.assertTrue(actual['guard_complete']);self.assertEqual(actual['binding']['pid'],process.pid);self.assertEqual(actual['actual_route']['raw_block'],blocks[0])
    self.assertEqual(actual['serial_end']['sha256'],hashlib.sha256(serial.encode()).hexdigest())
    self.assertLessEqual(actual['serial_end']['read_ended_monotonic_ns'],actual['heavy_hash_started_monotonic_ns'])
    for fault in ['missing-END','partial-END','duplicate-END','fatal-after-END','wrong-case','failed-op','symlink']:
     target_receipt=result/'native-dvd-post-target.json';target_receipt.unlink()
     path=result/'native-serial.log';changed=serial
     if fault=='missing-END':changed=serial[:serial.index('# STORAGE-PERF-END')]
     elif fault=='partial-END':changed=serial.rstrip('\n')
     elif fault=='duplicate-END':changed=serial+'# STORAGE-PERF-END cases=1 failures=0\n'
     elif fault=='fatal-after-END':changed=serial+'# STORAGE-PERF-ERROR stage=retained\n'
     elif fault=='wrong-case':changed=serial.replace('dvd-api-leaf-clean.cold-ish','foreign.cold-ish')
     elif fault=='failed-op':changed=serial.replace('status=00000000','status=c0000001',1)
     if fault=='symlink':
      path.unlink();(root/'foreign.log').write_text(serial);path.symlink_to(root/'foreign.log')
     else:path.write_text(changed)
     failed=subprocess.run(command,capture_output=True,text=True,timeout=10)
     self.assertNotEqual(failed.returncode,0,fault)
     observed=json.loads((result/'native-dvd-post-guard.json').read_text());self.assertFalse(observed['guard_complete'],fault);self.assertFalse(target_receipt.exists(),fault+' entered heavy target binding before qualified END')
     if fault=='symlink':path.unlink()
     path.write_text(serial)
     completed=subprocess.run(command,capture_output=True,text=True,timeout=10);self.assertEqual(completed.returncode,0,completed.stderr)
   finally:
    process.terminate()
    try:process.wait(timeout=3)
    except subprocess.TimeoutExpired:process.kill();process.wait(timeout=3)
if __name__=='__main__':unittest.main()
