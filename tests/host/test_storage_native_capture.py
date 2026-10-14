"""Generic caller identity/ledger controls; all dispatch is mocked."""
import hashlib,importlib.util,json,pathlib,sys,tempfile,unittest
from unittest import mock
SOURCE=pathlib.Path(__file__).parents[2]/'tools/storage_native_capture.py'
PARSER=SOURCE.with_name('storage_native_runner.py')
def subject():
 spec=importlib.util.spec_from_file_location('storage_native_capture',SOURCE);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def frozen(root):
 (root/'tool-source').mkdir();data=PARSER.read_bytes();(root/'tool-source/storage_native_runner.py').write_bytes(data);pin=hashlib.sha256(data).hexdigest()
 plan={'schema_version':1,'purpose':'native_fixture_qualification','revision':'3.4','parser_sha256':pin,'method_source_pins':{'storage_native_runner.py':pin},'attempts':[{'id':'owned-attempt','host':'deck','phase':'post-method','expected_case':{'id':'small-hdd-read.cold-ish'}}]}
 path=root/'qualification-plan.json';path.write_text(json.dumps(plan));return path,hashlib.sha256(path.read_bytes()).hexdigest()
class NativeCaptureTests(unittest.TestCase):
 def test_observe_retains_raw_assessment_and_context_hashes_before_grading(self):
  m=subject()
  with tempfile.TemporaryDirectory(prefix='pr248-capture-raw-') as work:
   root=pathlib.Path(work);(root/'diagnostics/run-state').mkdir(parents=True)
   assessment={'Execution':'failed','Intervened':True,'Uncontrolled':['os-page-cache']};result={'status':'failed','assessment':assessment,'exitCode':7,'startedUtc':'start','endedUtc':'end','processId':123}
   for name,value in [('result.json',result),('input-manifest.json',{}),('runtime-cleanup.json',{}),('job.json',{'Id':'own'}),('launch.json',{'runId':'own'}),('diagnostics/run-state/report.json',{'unknown':None})]:(root/name).write_text(json.dumps(value))
   (root/'native-serial.log').write_text('retained failure\n');(root/'native-host-controls.txt').write_text('actual\n');row={};m.observe(root,row)
   self.assertEqual(row['raw_runner_assessment'],assessment);self.assertEqual(row['job_sha256'],m.sha(root/'job.json'));self.assertEqual(row['launch_sha256'],m.sha(root/'launch.json'));self.assertEqual(row['context_artifact_sha256']['diagnostics/run-state/report.json'],m.sha(root/'diagnostics/run-state/report.json'))
 def test_import_and_configure_are_pure_and_use_external_plan_digest(self):
  self.assertTrue(SOURCE.exists(),'generic native caller missing');m=subject();self.assertIsNone(m.PLAN);self.assertIsNone(m.ROOT)
  with tempfile.TemporaryDirectory(prefix='pr248-capture-configure-') as work:
   root=pathlib.Path(work);path,pin=frozen(root)
   with mock.patch('urllib.request.urlopen',side_effect=AssertionError('configuration dispatched HTTP')):m.configure(root,pin)
   self.assertEqual(m.ROOT,root);self.assertEqual(m.PLAN_SHA,pin)
   with self.assertRaises(ValueError):m.configure(root,'f'*64)
   self.assertNotIn("PLAN_SHA='",SOURCE.read_text())
 def test_actual_main_never_dispatches_after_prior_failure_or_recursive_duplicate(self):
  self.assertTrue(SOURCE.exists(),'generic native caller missing')
  for prior in ['plain','duplicate','nested']:
   with self.subTest(prior=prior),tempfile.TemporaryDirectory(prefix='pr248-capture-ledger-') as work:
    root=pathlib.Path(work)/'freeze';root.mkdir();_,pin=frozen(root);m=subject();review=root/'review.json';review.write_text('{}');review_pin=hashlib.sha256(review.read_bytes()).hexdigest();ledger=root.parent/'deck-v34-qualification.jsonl'
    row={'plan_sha256':pin,'status':'failed_qualification','attempt_id':'owned-attempt'}
    text=json.dumps(row)
    if prior=='duplicate':text='{"status":"failed_qualification","status":"qualified_for_declared_scope","plan_sha256":'+json.dumps(pin)+'}'
    if prior=='nested':text=json.dumps(row)[:-1]+',"nested":{"failure":true,"\\u0066ailure":false}}'
    ledger.write_text(text+'\n')
    args=['capture','deck','--plan-root',str(root),'--plan-sha256',pin,'--phase','post-method','--execute','--review-receipt',str(review),'--review-sha256',review_pin]
    with mock.patch.object(sys,'argv',args),mock.patch.object(m,'validate_review'),mock.patch.object(m,'execute',side_effect=AssertionError('native dispatch')) as dispatch:
     if prior=='plain':self.assertEqual(m.main(),2)
     else:
      with self.assertRaisesRegex(ValueError,'line 1.*duplicate'):m.main()
     dispatch.assert_not_called()
 def test_empty_ledger_reaches_exactly_one_owned_dispatch_and_retains_failure(self):
  self.assertTrue(SOURCE.exists(),'generic native caller missing')
  with tempfile.TemporaryDirectory(prefix='pr248-capture-empty-') as work:
   root=pathlib.Path(work)/'freeze';root.mkdir();_,pin=frozen(root);m=subject();review=root/'review.json';review.write_text('{}');review_pin=hashlib.sha256(review.read_bytes()).hexdigest()
   args=['capture','deck','--plan-root',str(root),'--plan-sha256',pin,'--phase','post-method','--execute','--review-receipt',str(review),'--review-sha256',review_pin]
   with mock.patch.object(sys,'argv',args),mock.patch.object(m,'validate_review'),mock.patch.object(m,'execute',side_effect=RuntimeError('retained actual failure')) as dispatch:self.assertEqual(m.main(),2);dispatch.assert_called_once()
   row=json.loads((root.parent/'deck-v34-qualification.jsonl').read_text());self.assertEqual(row['error'],'retained actual failure');self.assertEqual(row['status'],'failed_qualification')
if __name__=='__main__':unittest.main()
