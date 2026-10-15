import os,pathlib,subprocess,tempfile,unittest
ROOT=pathlib.Path(__file__).resolve().parent
class ActualRecorderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.exe=pathlib.Path(cls.temp.name)/'actual-recorder'
        optimization=os.environ.get('RECORDER_TEST_OPT','-O2');assert optimization in ('-O0','-O2')
        subprocess.run(['cc','-std=gnu11',optimization,'-Wall','-Wextra','-I'+str(ROOT/'host-mock'),'-I'+str(ROOT),str(ROOT/'host-mock/recorder-mock.c'),'-o',str(cls.exe)],check=True,capture_output=True,text=True)
        cls.selection=pathlib.Path(cls.temp.name)/'actual-selection'
        subprocess.run(['cc','-std=gnu11',optimization,'-Wall','-Wextra','-I'+str(ROOT/'host-mock'),'-I'+str(ROOT),str(ROOT/'host-mock/selection-mock.c'),'-o',str(cls.selection)],check=True,capture_output=True,text=True)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def run_mode(self,mode,dataset=1,depth=4,pressure=0,warm=0):
        value=subprocess.run([str(self.exe),mode,str(dataset),str(depth),str(pressure),str(warm)],capture_output=True,text=True,timeout=30)
        self.assertEqual(value.returncode,0,value.stdout+value.stderr);return value.stdout
    def test_valid_all_vectors_resident_and_caller_depths(self):
        for dataset in (0,1):
            for depth in (1,4,12):
                with self.subTest(dataset=dataset,depth=depth):
                    out=self.run_mode('valid',dataset,depth);self.assertIn('VERDICT passed',out);self.assertIn('failures=0',out);self.assertIn('operations_completed=1024',out);self.assertIn('oracle=post_batch_full_bytes',out);self.assertIn('cleanup_live_allocations=0',out)
    def test_no_fill_partial_fill_alias_and_late_mutation_are_rejected(self):
        for mode in ('no-fill','partial-fill','alias','late-mutation','prefix-corruption'):
            with self.subTest(mode=mode):
                out=self.run_mode(mode);self.assertIn('VERDICT failed',out);self.assertIn('STORAGE-IO-V3-CASE',out);self.assertNotIn('STORAGE-IO-V3-ERROR',out);self.assertRegex(out,r'operations_expected=1024 operations_completed=(?!1024\b)\d+')
    def test_wrong_callback_status_pointer_count_and_submit_are_rejected(self):
        for mode in ('wrong-status','wrong-info','wrong-pointer','duplicate-apc','submit-error','clock-rollback'):
            with self.subTest(mode=mode):
                out=self.run_mode(mode);self.assertIn('VERDICT failed',out);self.assertIn('STORAGE-IO-V3-CASE',out);self.assertNotIn('STORAGE-IO-V3-ERROR',out);self.assertRegex(out,r'operations_expected=1024 operations_completed=(?!1024\b)\d+')
    def test_warmup_repoisones_every_buffer_before_measured_batch(self):
        out=self.run_mode('no-fill-measured',1,12,900,1);self.assertIn('VERDICT failed',out);self.assertIn('warmup_oracle_failures=0',out);self.assertIn('measured_pages_before=900',out)
    def test_callbacks_cannot_touch_protected_buffers_and_issuer_cannot_repoison(self):
        out=self.run_mode('protect',0,12,0,1);self.assertIn('VERDICT passed',out);self.assertIn('callback_protection_checks=2048',out)
    def test_allocation_failure_is_explicit_and_cleans_owned_memory(self):
        out=self.run_mode('allocation-failure');self.assertIn('VERDICT failed',out);self.assertIn('cleanup_live_allocations=0',out)
    def test_timeout_keeps_inflight_buffers_alive_until_guest_teardown(self):
        out=self.run_mode('no-apc');self.assertIn('VERDICT failed',out);self.assertIn('buffers_retained_until_poweroff=1',out);self.assertIn('cleanup_complete=0',out)
    def test_actual_selection_accepts_exact24_leaves(self):
        for d in (0,1):
            for q in (1,4,12):
                for p in (0,900):
                    for cache in ('warm','cold-ish'):
                        case=f'fatx-d{d}-q{q}-p{p}-synthetic.{cache}'
                        value=subprocess.run([str(self.selection),case],capture_output=True,text=True)
                        self.assertEqual(value.returncode,0,value.stdout+value.stderr)
    def test_actual_selection_rejects_unknown_multiple_or_noncanonical_case(self):
        for case in ('small-hdd-read.warm','fatx-d01-q4-p0-synthetic.warm','fatx-d1-q2-p0-synthetic.warm','fatx-d1-q4-p1-synthetic.warm','fatx-d1-q4-p0-synthetic.hot','multiple'):
            value=subprocess.run([str(self.selection),case],capture_output=True,text=True);self.assertEqual(value.returncode,2,value.stdout+value.stderr)
if __name__=='__main__':unittest.main(verbosity=2)
