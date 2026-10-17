"""Native evidence integrity checks; literals are invented protocol test data."""
import importlib.util
from pathlib import Path
import unittest
import shutil
import subprocess
import tempfile
import re
import hashlib
import json
import struct
import sys

PATH = Path(__file__).parents[2] / 'tools/storage_native_runner.py'

class NativeRecorderTests(unittest.TestCase):
    def dvd_generator(self):
        path = PATH.parent.parent / 'tests/xbe/storage-perf/make-dvd-references.py'
        spec = importlib.util.spec_from_file_location('owned_dvd_generator', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_dvd_reference_generation_ignores_stale_extracted_headers(self):
        module = self.dvd_generator()
        with tempfile.TemporaryDirectory(prefix='pr248-dvd-lineage-') as work:
            directory = Path(work)
            expected = bytearray(4096)
            expected[:4] = b'XBEH'
            for offset, value in ((0x104,0x10000),(0x108,4096),(0x11c,1),(0x120,0x10180),(0x18c,4096)):
                struct.pack_into('<I', expected, offset, value)
            expected[0x200] = 23
            (directory/'fresh-header').write_bytes(expected + b'body')
            extractor = directory/'owned-extractor'
            extractor.write_text('#!'+sys.executable+'\nimport pathlib,sys\n'
                'args=sys.argv; destination=pathlib.Path(args[args.index("-d")+1]); destination.mkdir()\n'
                'destination.joinpath("default.xbe").write_bytes(pathlib.Path(__file__).with_name("fresh-header").read_bytes())\n'
                'pathlib.Path(__file__).with_name("invocations").open("a").write("fresh\\n")\n')
            extractor.chmod(0o755)
            iso = directory/'invented.iso'; iso.write_bytes(b'invented public test ISO input')
            stale = directory/'clean'; stale.mkdir()
            stale_header = bytearray(expected); stale_header[0x200] = 99
            (stale/'default.xbe').write_bytes(stale_header + b'old!')
            references = [('clean',iso,hashlib.sha256(iso.read_bytes()).hexdigest())]
            output = directory/'reference.h'; manifest = directory/'manifest.json'
            rows = module.generate_references(references,extractor,hashlib.sha256(extractor.read_bytes()).hexdigest(),output,manifest)
            self.assertEqual(rows[0]['header_sha256'],hashlib.sha256(expected).hexdigest())
            self.assertEqual(rows[0]['extraction_mode'],'fresh_temporary_directory')
            self.assertEqual((directory/'invocations').read_text(),'fresh\n')
            self.assertEqual((stale/'default.xbe').read_bytes(),stale_header+b'old!')
            self.assertEqual(json.loads(manifest.read_text()),rows)
            for position in ('iso','extractor'):
                with self.subTest(position=position):
                    bad_refs = [('clean',iso,'0'*64)] if position=='iso' else references
                    bad_tool = '0'*64 if position=='extractor' else hashlib.sha256(extractor.read_bytes()).hexdigest()
                    with self.assertRaisesRegex(ValueError,'pin mismatch'):
                        module.generate_references(bad_refs,extractor,bad_tool,output,manifest)
                    self.assertEqual((directory/'invocations').read_text(),'fresh\n')

    @unittest.skipUnless(shutil.which('make'), 'clean DVD dependency check requires make')
    def test_clean_dvd_build_generates_header_from_declared_inputs(self):
        fixture = PATH.parent.parent / 'tests/xbe/storage-perf'
        with tempfile.TemporaryDirectory(prefix='pr248-dvd-build-') as work:
            directory = Path(work); sdk = directory/'sdk'; sdk.mkdir()
            # Small SDK rule exercises the actual owned Makefile dependency,
            # without a local SDK build or generated headers from the checkout.
            (sdk/'Makefile').write_text('OBJS = owned.o\nall: $(OBJS)\n$(OBJS):\n\t@test -s dvd-metadata-reference.h\n\t@touch $@\n')
            shutil.copyfile(fixture/'Makefile',directory/'Makefile')
            (directory/'make-dvd-references.py').write_text('import pathlib,sys\n'
                'a=sys.argv; pathlib.Path(a[a.index("--output")+1]).write_text("generated from declared inputs\\n")\n'
                'pathlib.Path("generator-argv").write_text("\\n".join(a))\n')
            for name in ('clean.iso','performance.iso','extractor'):(directory/name).write_text(name)
            args=['make','MODE=dvd','NXDK_DIR='+str(sdk),'DVD_CLEAN_ISO='+str(directory/'clean.iso'),
                  'DVD_PERFORMANCE_ISO='+str(directory/'performance.iso'),'DVD_EXTRACTOR='+str(directory/'extractor'),
                  'DVD_EXTRACTOR_SHA256='+'a'*64]
            completed=subprocess.run(args,cwd=directory,capture_output=True,text=True)
            self.assertEqual(completed.returncode,0,completed.stdout+completed.stderr)
            self.assertTrue((directory/'owned.o').exists())
            argv=(directory/'generator-argv').read_text()
            self.assertIn('--clean-iso\n'+str(directory/'clean.iso'),argv)
            self.assertIn('--performance-iso\n'+str(directory/'performance.iso'),argv)
            self.assertIn('--extractor-sha256\n'+'a'*64,argv)

    def module(self):
        self.assertTrue(PATH.exists(), 'native recorder has not been implemented')
        spec = importlib.util.spec_from_file_location('native_recorder', PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def serial(self, suffix=''):
        return ('# STORAGE-PERF-META version=1 fixture_generation=2 counter=rdtsc frequency=1000000 overhead_ticks=8\n'
                '# STORAGE-PERF-OP id=small-warm index=0 ticks=10 status=00000000 io_status=00000000 information=512 apcs=0\n'
                '# STORAGE-PERF-OP id=small-warm index=1 ticks=20 status=00000000 io_status=00000000 information=512 apcs=0\n'
                '# STORAGE-PERF-CASE id=small-warm operations=2 bytes=1024 ticks=35 assertions=6 failures=0 flush_calls=0 persistence=0 qd_actual=1 available_pages=12000 cache=warm\n'
                '# STORAGE-PERF-END cases=1 failures=0\n' + suffix)

    def test_valid_serial_converts_actual_ticks_and_preserves_missing_internal_counters(self):
        result = self.module().parse_serial(self.serial())['cases']['small-warm']
        self.assertEqual(result['latencies_ms'], [.01, .02])
        self.assertEqual(result['elapsed_ms'], .035)
        self.assertEqual(result['operations_completed'], 2)
        self.assertEqual(result['bytes_completed'], 1024)
        self.assertNotIn('upper_worker_hops', result['counters'])
        self.assertEqual(result['counters']['file_read_calls'], 2)

    def test_missing_end_is_incomplete_not_pass(self):
        result = self.module().parse_serial(self.serial().replace('# STORAGE-PERF-END cases=1 failures=0\n', ''))
        self.assertFalse(result['complete'])

    def test_duplicate_operation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.module().parse_serial(self.serial().replace('# STORAGE-PERF-CASE', '# STORAGE-PERF-OP id=small-warm index=0 ticks=10 status=00000000 io_status=00000000 information=512 apcs=0\n# STORAGE-PERF-CASE', 1))

    def test_bad_iosb_is_a_failed_attempt(self):
        result = self.module().parse_serial(self.serial().replace('io_status=00000000', 'io_status=c0000001', 1))
        self.assertEqual(result['cases']['small-warm']['status'], 'error')

    def test_duplicate_fields_cannot_override_a_failure(self):
        module = self.module()
        for before, after in (
            ('status=00000000', 'status=c0000001 status=00000000'),
            ('failures=0', 'failures=1 failures=0'),
            ('fixture_generation=2', 'fixture_generation=1 fixture_generation=2'),
        ):
            with self.subTest(field=before), self.assertRaisesRegex(ValueError, 'duplicate.*field'):
                module.parse_serial(self.serial().replace(before, after, 1))

    def test_count_mismatch_is_a_failed_attempt(self):
        result = self.module().parse_serial(self.serial().replace('operations=2 bytes=1024', 'operations=3 bytes=1536'))
        self.assertEqual(result['cases']['small-warm']['status'], 'error')

    def test_truncated_cache_policy_is_rejected(self):
        result = self.module().parse_serial(self.serial().replace('cache=warm', 'cache=war'))
        self.assertEqual(result['cases']['small-warm']['status'], 'error')

    def test_write_fixture_counters_do_not_become_read_only_counts(self):
        serial = self.serial().replace('cache=warm', 'cache=warm read_calls=2 write_calls=2')
        counters = self.module().parse_serial(serial)['cases']['small-warm']['counters']
        self.assertEqual(counters['file_write_calls'], 2)
        self.assertEqual(counters['file_read_calls'], 2)

    def test_pipe_proof_accepts_only_matching_live_codex_desktop(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'parse_pipe_proof'), 'desktop pipe proof reader missing')
        server = ('identity=DESKTOP\\Codex\nsession=1\nserver_pid=22\npipe_name=pr248-owned-test\n'
                  'window_station=WinSta0\ndesktop=Default\noperation=PROVE\nlaunch_transport=named-pipe\n')
        client = ('identity=DESKTOP\\Codex\nsession=1\nserver_pid=22\npipe_name=pr248-owned-test\n'
                  'window_station=WinSta0\ndesktop=Default\noperation=PROVE\nhandshake_verified=True\n')
        result = module.parse_pipe_proof(server, client)
        self.assertTrue(result['bridge_verified'])
        self.assertFalse(result['graphical_guest_launched'])
        with self.assertRaisesRegex(ValueError, 'desktop'):
            module.parse_pipe_proof(server.replace('session=1', 'session=0'), client)

    def test_stage_guard_rejects_foreign_job_and_unisolated_guest(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_stage_request'), 'owned stage guard missing')
        with self.assertRaisesRegex(ValueError, 'owned'):
            module.validate_stage_request({'id':'foreign-job','job':{'id':'foreign-job'},'files':[]})
        with self.assertRaisesRegex(ValueError, 'private'):
            module.validate_stage_request({'id':'pr248-native-test','job':{'id':'pr248-native-test'},'files':[]})

    def test_flush_calls_do_not_claim_device_cache_sync(self):
        result = self.module().parse_serial(self.serial().replace('flush_calls=0 persistence=0', 'flush_calls=2 persistence=1'))['cases']['small-warm']
        self.assertEqual(result['flush_api_calls_completed'], 2)
        self.assertIsNone(result['flushes_completed'])
        self.assertTrue(result['reopen_readback_verified'])
        self.assertIsNone(result['durability_verified'])

    def test_legacy_persistence_flag_cannot_be_verified_readback(self):
        raw = self.serial().replace('fixture_generation=2 ', '').replace('persistence=0', 'persistence=1')
        result = self.module().parse_serial(raw)['cases']['small-warm']
        self.assertTrue(result['reopen_readback_reported'])
        self.assertIsNone(result['reopen_readback_verified'])
        self.assertIsNone(result['durability_verified'])

    def test_error_query_preserves_caller_poison_without_claiming_internal_information(self):
        raw = ('# STORAGE-QUERY path=hdd control=device-number code=002d1080 length=11 status=c0000023 iosb=5a5a5a5a information=1515870810\n'
               '# STORAGE-QUERY-DATA path=hdd control=device-number length=11 offset=0 hex=a5a5a5a5a5a5a5a5a5a5a5\n'
               '# STORAGE-QUERY-END controls=1 no_disc_observed=0\n')
        result = self.module().parse_queries(raw)
        self.assertTrue(result['complete'])
        row = result['observations'][0]
        self.assertTrue(row['caller_iosb_poison_preserved'])
        self.assertIsNone(row['internal_driver_information'])
        self.assertEqual(row['caller_information'], 1515870810)

    def test_query_missing_trailing_bytes_is_rejected(self):
        raw = ('# STORAGE-QUERY path=hdd control=device-number code=002d1080 length=16 status=00000000 iosb=00000000 information=12\n'
               '# STORAGE-QUERY-DATA path=hdd control=device-number length=16 offset=0 hex=070000000000000000000000\n')
        with self.assertRaisesRegex(ValueError, 'output bytes'):
            self.module().parse_queries(raw)

    def test_run_pipe_handshake_requires_actual_child_receipt_for_gui_claim(self):
        server = ('identity=DESKTOP\\Codex\nsession=1\nserver_pid=22\npipe_name=pr248-owned-test\n'
                  'window_station=WinSta0\ndesktop=Default\noperation=RUN\nlaunch_transport=named-pipe\n')
        client = server.replace('launch_transport=named-pipe', 'handshake_verified=True')
        module = self.module()
        self.assertFalse(module.parse_pipe_proof(server, client)['graphical_guest_launched'])
        launch = server.replace('operation=RUN\n', '') + 'xemu_pid=33\nxemu_session=1\nuserInteractive=True\n'
        self.assertTrue(module.parse_pipe_proof(server, client, launch)['graphical_guest_launched'])
        with self.assertRaisesRegex(ValueError, 'child'):
            module.parse_pipe_proof(server, client, launch.replace('xemu_session=1', 'xemu_session=0'))

    def inference_inputs(self):
        case = {'id': 'small-warm', 'operations': 2, 'bytes_completed_expected': 1024,
                'assertions_expected': 6, 'expected_sha256': 'a' * 64}
        manifest = {'Inputs': [{'Path': 'storage-perf.iso', 'Sha256': 'b' * 64,
                               'ExpectedSha256': 'b' * 64, 'Verified': True}],
                    'RuntimeFiles': [{'Destination': 'hdd.qcow2', 'SeedSha256': 'c' * 64,
                                      'DiskAssetId': 'owned-invented-seed'}]}
        return case, manifest

    def test_digest_inference_records_its_origin_from_complete_exact_comparisons(self):
        case, manifest = self.inference_inputs()
        value = self.module().infer_integrity(self.serial(), case, manifest,
                                             fixture_sha256='b'*64, seed_sha256='c'*64)
        self.assertEqual(value['integrity_sha256'], 'a'*64)
        self.assertEqual(value['integrity_sha256_origin'], 'host_inferred_from_verified_equality')
        self.assertEqual(value['integrity_comparisons_completed'], 2)

    def test_native_inference_is_bound_to_frozen_plan_parser_fixture_seed_and_schedule(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'infer_integrity_for_attempt'), 'frozen native caller missing')
        import json
        with tempfile.TemporaryDirectory(prefix='pr248-bound-inference-') as work:
            root = Path(work)
            fixture = root/'fixture.iso'; fixture.write_bytes(b'invented complete native fixture')
            fixture_hash = module.sha256(fixture)
            source = root/'source-manifest.json'
            source.write_text(json.dumps({'files':[{'path':'fixture.iso','bytes':fixture.stat().st_size,
                                                    'sha256':fixture_hash}]}))
            case, manifest = self.inference_inputs()
            manifest['JobId'] = 'pr248-native-invented-bound'
            manifest['Inputs'][0].update(Sha256=fixture_hash, ExpectedSha256=fixture_hash)
            manifest['RuntimeFiles'][0]['Source'] = 'disk-asset:owned-invented-seed'
            request = root/'request.json'
            request.write_text(json.dumps({'id':manifest['JobId'],'files':[{'Path':'storage-perf.iso','Sha256':fixture_hash}], 'job':{'id':manifest['JobId'],
                'runtimeState':{'xiso':{'image':'hdd.qcow2'}, 'diskAssets':[{
                    'assetId':'owned-invented-seed','destination':'hdd.qcow2','expectedSha256':'c'*64}]}}}))
            plan = {'schema_version':1,'purpose':'native_fixture_qualification',
                    'parser_sha256':module.sha256(PATH),
                    'source_manifest':{'path':'source-manifest.json','sha256':module.sha256(source)},
                    'hosts':{'invented':{'hdd_seed_id':'owned-invented-seed','hdd_seed_sha256':'c'*64}},
                    'attempts':[{'id':manifest['JobId'],'host':'invented','kind':'native_integrity',
                      'fixture_sha256':fixture_hash,'expected_inputs':{'storage-perf.iso':fixture_hash},
                      'seed_request_mode':'prepared_xiso','request_path':'request.json',
                      'request_sha256':module.sha256(request),
                      'expected_metadata':{'version':'1','fixture_generation':'2','counter':'rdtsc'},
                      'expected_case':case,'expected_operation_bytes':[512,512],
                      'expected_apcs_per_operation':0,'expected_qd':1,'expected_cache':'warm'}]}
            path=root/'plan.json';path.write_text(json.dumps(plan));plan_hash=module.sha256(path)
            value=module.infer_integrity_for_attempt(self.serial(),manifest,plan_path=path,
                                                    plan_sha256=plan_hash,attempt_id=manifest['JobId'])
            self.assertEqual(value['integrity_plan_sha256'],plan_hash)
            self.assertEqual(value['integrity_parser_sha256'],module.sha256(PATH))
            self.assertEqual(value['integrity_sha256'],'a'*64)
            module.infer_integrity_for_attempt(self.serial().replace('STORAGE-PERF-OP ', 'STORAGE-PERF-OP\t'),
                manifest,plan_path=path,plan_sha256=plan_hash,attempt_id=manifest['JobId'])
            with self.assertRaisesRegex(ValueError,'plan'):
                module.infer_integrity_for_attempt(self.serial(),manifest,plan_path=path,
                    plan_sha256='d'*64,attempt_id=manifest['JobId'])
            changed=dict(manifest,JobId='another-attempt')
            with self.assertRaisesRegex(ValueError,'attempt'):
                module.infer_integrity_for_attempt(self.serial(),changed,plan_path=path,
                    plan_sha256=plan_hash,attempt_id=manifest['JobId'])
            altered=self.serial().replace('information=512','information=256',1).replace('information=512','information=768',1)
            with self.assertRaisesRegex(ValueError,'operation'):
                module.infer_integrity_for_attempt(altered,manifest,plan_path=path,
                    plan_sha256=plan_hash,attempt_id=manifest['JobId'])
            for altered in (altered.replace('STORAGE-PERF-OP ', 'STORAGE-PERF-OP\t'),
                            self.serial().replace('STORAGE-PERF-OP ', 'STORAGE-PERF-OP\t').replace('apcs=0', 'apcs=1')):
                with self.subTest(serial=altered), self.assertRaisesRegex(ValueError, 'operation'):
                    module.infer_integrity_for_attempt(altered,manifest,plan_path=path,
                        plan_sha256=plan_hash,attempt_id=manifest['JobId'])
            plan['attempts'][0]['seed_request_mode']='direct_copy';path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'mode'):
                module.infer_integrity_for_attempt(self.serial(),manifest,plan_path=path,
                    plan_sha256=module.sha256(path),attempt_id=manifest['JobId'])
            plan['attempts'][0]['seed_request_mode']='prepared_xiso'
            request.write_text('{}');path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError, 'request'):
                module.infer_integrity_for_attempt(self.serial(),manifest,plan_path=path,
                    plan_sha256=module.sha256(path),attempt_id=manifest['JobId'])
            plan['parser_sha256']='d'*64;path.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'parser'):
                module.infer_integrity_for_attempt(self.serial(),manifest,plan_path=path,
                    plan_sha256=module.sha256(path),attempt_id=manifest['JobId'])

    def test_digest_inference_rejects_partial_failed_or_unmatched_evidence(self):
        case, manifest = self.inference_inputs()
        module = self.module()
        for raw in (self.serial().replace('# STORAGE-PERF-END cases=1 failures=0\n', ''),
                    self.serial().replace('failures=0', 'failures=1', 1),
                    self.serial().replace('operations=2 bytes=1024', 'operations=3 bytes=1536'),
                    self.serial('# STORAGE-PERF-OP id=unexpected index=0 ticks=10 status=00000000 io_status=00000000 information=512 apcs=0\n')):
            with self.assertRaises(ValueError):
                module.infer_integrity(raw, case, manifest, fixture_sha256='b'*64, seed_sha256='c'*64)
        with self.assertRaisesRegex(ValueError, 'fixture'):
            module.infer_integrity(self.serial(), case, manifest,
                                   fixture_sha256='d'*64, seed_sha256='c'*64)
        with self.assertRaisesRegex(ValueError, 'seed'):
            module.infer_integrity(self.serial(), case, manifest,
                                   fixture_sha256='b'*64, seed_sha256='d'*64)

    def test_v1_buffer_reuse_revokes_inferred_integrity(self):
        case, manifest = self.inference_inputs()
        v1 = '02c8b038eab6e216cc5957203b3aa485d14e59128e0b005d8091a46fe55a2515'
        manifest['Inputs'][0].update(Sha256=v1, ExpectedSha256=v1)
        with self.assertRaisesRegex(ValueError, 'V1'):
            self.module().infer_integrity(self.serial(), case, manifest,
                                         fixture_sha256=v1, seed_sha256='c'*64)

    def test_inference_requires_corrected_fixture_generation_even_for_other_legacy_hashes(self):
        case, manifest = self.inference_inputs()
        with self.assertRaisesRegex(ValueError, 'generation'):
            self.module().infer_integrity(self.serial().replace('fixture_generation=2 ', ''), case, manifest,
                                         fixture_sha256='b'*64, seed_sha256='c'*64)

    def test_fatal_and_tap_failures_cannot_become_complete_or_inferred(self):
        case, manifest = self.inference_inputs()
        module = self.module()
        for failure in ('# STORAGE-PERF-ERROR stage=read-batch-timeout\n',
                        'not ok 1 - native fixture failed\n'):
            raw = self.serial(failure)
            parsed = module.parse_serial(raw)
            self.assertFalse(parsed['complete'])
            self.assertTrue(parsed['global_issues'])
            self.assertEqual(parsed['cases']['small-warm']['status'], 'error')
            with self.assertRaises(ValueError):
                module.infer_integrity(raw, case, manifest, fixture_sha256='b'*64, seed_sha256='c'*64)

    def test_protocol_records_after_end_cannot_be_concatenated_into_clean_attempt(self):
        with self.assertRaisesRegex(ValueError, 'after END'):
            self.module().parse_serial(self.serial('# STORAGE-PERF-CLOCK min=900000 median=1000000 max=1100000\n'))

    def test_query_end_is_terminal_and_duplicate_style_is_rejected(self):
        module = self.module()
        row = '# STORAGE-QUERY path=hdd control=geometry-ex code=000700a0 length=40 status=00000000 iosb=00000000 information=40\n'
        data = '# STORAGE-QUERY-DATA path=hdd control=geometry-ex length=40 offset=0 hex=' + 'a5'*40 + '\n'
        style = '# STORAGE-PARTITION-STYLE path=hdd length=40 record_size=0 style=0\n'
        end = '# STORAGE-QUERY-END controls=1 no_disc_observed=0\n'
        for raw in (end+row+data, row+data+end+style, row+style+style+data+end):
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, 'after END|duplicate'):
                module.parse_queries(raw)
        self.assertTrue(module.parse_queries(row+style+data+end+'ok 1 - observation complete\n')['complete'])

    def test_query_fatal_and_tap_failure_remain_incomplete(self):
        raw = '# STORAGE-QUERY-END controls=0 no_disc_observed=0\n'
        for failure in ('not ok 1 - query failed\n', '# STORAGE-PERF-ERROR stage=query\n'):
            with self.subTest(failure=failure):
                result = self.module().parse_queries(raw+failure)
                self.assertFalse(result['complete'])
                self.assertTrue(result['global_issues'])

    def test_seed_lineage_uses_only_the_declared_request_mode(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_seed_lineage'), 'explicit seed lineage missing')
        host = {'hdd_seed_id': 'owned-seed', 'hdd_seed_sha256': 'c'*64}
        direct = {'Destination':'hdd.qcow2','DiskAssetId':'owned-seed',
                  'Source':'disk-asset:owned-seed','Sha256':'c'*64}
        prepared = dict(direct, Sha256='d'*64, SeedSha256='c'*64)
        for mode, disk in (('direct_copy', direct), ('prepared_xiso', prepared)):
            module.validate_seed_lineage({'RuntimeFiles':[disk]}, host, mode)
        for mode, disk in (('prepared_xiso', direct), ('direct_copy', prepared),
                           ('direct_copy', dict(direct, Sha256='e'*64)),
                           ('direct_copy', dict(direct, Source='foreign'))):
            with self.subTest(mode=mode,disk=disk), self.assertRaisesRegex(ValueError, 'seed'):
                module.validate_seed_lineage({'RuntimeFiles':[disk]}, host, mode)
        with self.assertRaisesRegex(ValueError, 'mode'):
            module.validate_seed_lineage({'RuntimeFiles':[direct]}, host, 'guess')

    def test_query_qualification_requires_exact_frozen_matrix_and_style_bytes(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_query_matrix'), 'frozen query matrix missing')
        matrix = [{'path':'hdd-whole','control':'device-number','code':0x2d1080,'output_length':12},
                  {'path':'hdd-whole','control':'geometry-ex','code':0x700a0,'output_length':40}]
        raw = ('# STORAGE-QUERY path=hdd-whole control=device-number code=002d1080 length=12 status=00000000 iosb=00000000 information=12\n'
               '# STORAGE-QUERY-DATA path=hdd-whole control=device-number length=12 offset=0 hex=070000000000000000000000\n'
               '# STORAGE-QUERY path=hdd-whole control=geometry-ex code=000700a0 length=40 status=00000000 iosb=00000000 information=40\n'
               '# STORAGE-PARTITION-STYLE path=hdd-whole length=40 record_size=0 style=0\n'
               '# STORAGE-QUERY-DATA path=hdd-whole control=geometry-ex length=40 offset=0 hex='+'00'*40+'\n'
               '# STORAGE-QUERY-END controls=2 no_disc_observed=0\n')
        module.validate_query_matrix(module.parse_queries(raw), matrix)
        for altered in (raw.replace('path=hdd-whole', 'path=invented'),
                        raw.replace('code=002d1080', 'code=00000000'),
                        raw.replace('style=0', 'style=128'),
                        raw.replace('# STORAGE-PARTITION-STYLE path=hdd-whole length=40 record_size=0 style=0\n', '')):
            with self.subTest(raw=altered), self.assertRaisesRegex(ValueError, 'matrix|style'):
                module.validate_query_matrix(module.parse_queries(altered), matrix)

    def test_deck_lifetime_requires_actual_timeout_and_finalized_owned_exit(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_lifetime_timeout'), 'exact timeout qualification missing')
        attempt = {'expected_lifetime_outcome':{'kind':'runner_timeout','status':'timeout',
                   'execution':'timedOut','timeout_seconds':20}}
        raw = '# STORAGE-LIFETIME-HOLD fixture_generation=2 data_writes=0 expected_completion=owned_timeout\n'
        result = {'status':'timeout','assessment':{'Execution':'timedOut'},
                  'detail':'Exceeded 20 unpaused seconds.'}
        cleanup = {'state':'complete','targetStopped':True,'evidenceFinalized':True}
        module.validate_lifetime_timeout(raw, result, cleanup, attempt)
        for status, execution in (('crashed','crashed'), ('failed','failed'),
                                  ('cancelled','cancelled'), ('completed','completed'), ('timeout','failed')):
            with self.subTest(execution=execution), self.assertRaisesRegex(ValueError, 'timeout'):
                module.validate_lifetime_timeout(raw, dict(result,status=status,assessment={'Execution':execution}), cleanup, attempt)
        for broken in (dict(cleanup,targetStopped=False), dict(cleanup,evidenceFinalized=False)):
            with self.assertRaisesRegex(ValueError, 'exit'):
                module.validate_lifetime_timeout(raw,result,broken,attempt)
        with self.assertRaisesRegex(ValueError, 'HOLD'):
            module.validate_lifetime_timeout(raw+raw,result,cleanup,attempt)

    def test_normal_and_clock_observations_cannot_qualify_a_failed_runner(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_successful_execution'), 'shared successful result check missing')
        module.validate_successful_execution({'status':'completed','assessment':{'Execution':'completed'},'exitCode':0})
        for result in ({'status':'crashed','assessment':{'Execution':'crashed'},'exitCode':1},
                       {'status':'completed','assessment':{'Execution':'completed'},'exitCode':1},
                       {'status':'failed','assessment':{'Execution':'completed'},'exitCode':0}):
            with self.subTest(result=result), self.assertRaisesRegex(ValueError, 'runner'):
                module.validate_successful_execution(result)

    def windows_exit_receipts(self):
        server = ('identity=DESKTOP\\Codex\nsession=1\nserver_pid=22\npipe_name=pr248-owned-test\n'
                  'window_station=WinSta0\ndesktop=Default\noperation=RUN\nlaunch_transport=named-pipe\n')
        return {'server':server, 'client':server.replace('launch_transport=named-pipe','handshake_verified=True')+'client_pid=11\n',
                'launch':server.replace('operation=RUN\n', '')+'xemu_pid=33\nxemu_session=1\nuserInteractive=True\n',
                'server_lifetime':'version=2\nserver_pid=22\nchild_started=True\nchild_pid=33\nowned_child_kill_requested=True\nowned_child_exit_confirmed=True\n',
                'client_lifetime':'version=2\nclient_pid=11\nserver_started=True\nserver_pid=22\nowned_server_exit_confirmed=True\n',
                'job_lifetime':'version=2\nclient_pid=11\nclient_suspended_before_assignment=1\nassigned_to_owned_job=1\nclient_resumed=1\nclient_wait_result=0\nclient_deadline_ms=170000\nkill_on_job_close=1\njob_terminate_succeeded=1\njob_query_succeeded=1\nactive_processes_after_cleanup=0\nowned_descendants_cleared=1\nclient_exit_status=1\n',
                'server_stderr':'Owned graphical child deadline exceeded\n'}

    def test_windows_internal_deadline_requires_live_pipe_and_zero_owned_descendants(self):
        module = self.module()
        self.assertTrue(hasattr(module, 'validate_windows_exit'), 'desktop lifetime receipt validation missing')
        receipts = self.windows_exit_receipts()
        raw = '# STORAGE-LIFETIME-HOLD fixture_generation=2 data_writes=0 expected_completion=owned_timeout\n'
        result = {'status':'failed','assessment':{'Execution':'failed'},'exitCode':1}
        cleanup = {'state':'complete','targetStopped':True,'evidenceFinalized':True}
        attempt = {'expected_lifetime_outcome':{'kind':'owned_server_deadline','status':'failed',
                   'execution':'failed','exit_code':1,'server_error':'Owned graphical child deadline exceeded'}}
        module.validate_lifetime_timeout(raw,result,cleanup,attempt,windows_receipts=receipts)
        for key, before, after in (('server_stderr','Owned graphical child deadline exceeded','unrelated crash'),
                                  ('job_lifetime','active_processes_after_cleanup=0','active_processes_after_cleanup=1'),
                                  ('server_lifetime','child_pid=33','child_pid=44'),
                                  ('client_lifetime','owned_server_exit_confirmed=True','owned_server_exit_confirmed=False')):
            with self.subTest(key=key), self.assertRaises(ValueError):
                changed = dict(receipts);changed[key]=changed[key].replace(before,after)
                module.validate_lifetime_timeout(raw,result,cleanup,attempt,windows_receipts=changed)

    def test_clock_guard_requires_exact_owned_runtime_executable_config_and_lifetime(self):
        path=PATH.parent.parent/'tests/xbe/storage-perf/clock-observer.py'
        spec=importlib.util.spec_from_file_location('owned_clock_observer',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        self.assertTrue(hasattr(module,'validate_target_binding'),'exact runtime target guard missing')
        expected={'job_id':'pr248-native-invented-clock','emulator_sha256':'e'*64,'config_sha256':'c'*64}
        observation={'package':'/owned/job','result':'/owned/results/run1','pid':123,'uid':1000,
          'target_uids':[1000]*4,'exe_path':'/owned/job/xemu','exe_sha256':'e'*64,
          'cwd':'/owned/job','start_time_before':456,'start_time_after':456,'launcher_pid':123,
          'command':['./xemu','-m','64','-config_path','/owned/results/run1/diagnostics/run-state/effective-live.toml'],
          'launch':{'job':'pr248-native-invented-clock','runId':'run1','arguments':['-config_path','/owned/job/xemu.toml','-m','64']},
          'manifest':{'JobId':'pr248-native-invented-clock','Inputs':[{'Path':'xemu','Sha256':'e'*64,'ExpectedSha256':'e'*64,'Verified':True},
                      {'Path':'xemu.toml','Sha256':'c'*64,'ExpectedSha256':'c'*64,'Verified':True}]},
          'report':{'Status':'prepared','ConfigSourcePath':'/owned/job/xemu.toml','ConfigSha256':'c'*64,
                    'EffectiveConfigPath':'/owned/results/run1/diagnostics/run-state/effective-live.toml',
                    'EffectiveConfigSha256':'f'*64},'effective_config_sha256':'f'*64}
        module.validate_target_binding(observation,expected)
        import copy
        for key,value in [('exe_path','/unrelated/xemu'),('exe_sha256','a'*64),
                          ('target_uids',[0]*4),('start_time_after',457),('launcher_pid',999),
                          ('effective_config_sha256','a'*64),('command',['./xemu','-m','64','-config_path','/owned/job/xemu.toml'])]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                changed=copy.deepcopy(observation);changed[key]=value;module.validate_target_binding(changed,expected)

    @unittest.skipUnless(shutil.which('cc'), 'actual C metrology requires host C compiler')
    def test_actual_metrology_busy_deadline_uses_its_qpc_counter_frequency(self):
        fixture=PATH.parent.parent/'tests/xbe/storage-perf'
        with tempfile.TemporaryDirectory(prefix='pr248-metrology-counter-domain-') as work:
            executable=Path(work)/'metrology-mock'
            subprocess.run(['cc','-std=gnu11','-O0','-I'+str(fixture/'host-mock'),'-I'+str(fixture),
                            str(fixture/'metrology.c'),str(fixture/'host-mock/metrology-mock.c'),
                            '-o',str(executable)],check=True,capture_output=True,text=True)
            raw=subprocess.run([str(executable)],check=True,capture_output=True,text=True).stdout
            samples=[]
            for line in raw.splitlines():
                marker=line.find('STORAGE-CLOCK-SAMPLE ')
                if marker>=0:samples.append(dict(word.split('=',1) for word in line[marker:].split()[1:]))
            self.assertEqual(len(samples),50)
            for sample in samples:
                self.assertEqual(int(sample['qpc_hz']),1000000)
                expected=int(sample['requested_us'])
                elapsed=int(sample['qpc_ticks'])
                with self.subTest(index=sample['index'],busy=sample['busy']):
                    self.assertGreaterEqual(elapsed,expected)
                    self.assertLessEqual(elapsed,expected+2)

    def test_clock_derivation_keeps_qpc_and_rdtsc_counter_domains_separate(self):
        module=self.module()
        self.assertTrue(hasattr(module,'derive_clock_observation'),'counter-domain derivation missing')
        guest={'qpc_ticks':'3374488','qpc_hz':'3374488','rdtsc_ticks':'733333333'}
        wall={'host_wall_ns_estimate':1000000000}
        observed=module.derive_clock_observation(guest,wall)
        self.assertEqual(observed['qpc_elapsed_seconds'],1)
        self.assertEqual(observed['qpc_over_host_ratio'],1)
        self.assertEqual(observed['rdtsc_ticks_per_host_second_estimate'],733333333)
        self.assertNotIn('rdtsc_elapsed_seconds',observed)
        zero=module.derive_clock_observation(guest,{'host_wall_ns_estimate':0})
        self.assertIsNone(zero['qpc_over_host_ratio'])
        self.assertIsNone(zero['rdtsc_ticks_per_host_second_estimate'])
        for key in ('qpc_hz','qpc_ticks','rdtsc_ticks'):
            changed=dict(guest);changed[key]='0'
            with self.subTest(key=key),self.assertRaises(ValueError):module.derive_clock_observation(changed,wall)

    @unittest.skipUnless(shutil.which('cc'), 'actual owned C fixture fault test requires host C compiler')
    def test_actual_write_fixture_rejects_success_without_readback_fill(self):
        fixture = PATH.parent.parent / 'tests/xbe/storage-perf'
        with tempfile.TemporaryDirectory(prefix='pr248-native-fault-') as work:
            executable = Path(work) / 'families-mock'
            subprocess.run(['cc', '-std=gnu11', '-O0', '-DSTORAGE_SUITE',
                            '-I'+str(fixture/'host-mock'), '-I'+str(fixture),
                            str(fixture/'families.c'), str(fixture/'host-mock/families-mock.c'),
                            '-o', str(executable)], check=True, capture_output=True, text=True)
            results = {}
            for mode in ('fill', 'no-fill', 'partial', 'iosb-untouched', 'error-untouched'):
                raw = subprocess.run([str(executable), mode], check=True, capture_output=True, text=True).stdout
                line = next(line for line in raw.splitlines() if line.startswith('STORAGE-PERF-CASE '))
                results[mode] = dict(item.split('=',1) for item in line.split() if '=' in item)
            self.assertEqual(results['fill']['failures'], '0')
            self.assertEqual(results['fill']['persistence'], '1')
            for mode in ('no-fill', 'partial', 'iosb-untouched', 'error-untouched'):
                self.assertEqual(results[mode]['failures'], '1024', mode)
                self.assertEqual(results[mode]['persistence'], '0', mode)

    @unittest.skipUnless(shutil.which('cc'), 'actual owned query fault test requires host C compiler')
    def test_actual_query_poisons_each_iosb_and_every_expected_readback_byte(self):
        fixture = PATH.parent.parent / 'tests/xbe/storage-perf'
        with tempfile.TemporaryDirectory(prefix='pr248-native-query-fault-') as work:
            executable = Path(work)/'query-mock'
            subprocess.run(['cc', '-std=gnu11', '-O0', '-I'+str(fixture/'host-mock'),
                            '-I'+str(fixture), str(fixture/'host-mock/query-mock.c'), '-o', str(executable)],
                           check=True, capture_output=True, text=True)
            results = {}
            for mode in ('fill', 'no-fill', 'partial', 'iosb-untouched', 'error-untouched', 'flush-error-untouched'):
                raw = subprocess.run([str(executable), mode], check=True, capture_output=True, text=True).stdout
                results[mode] = {line.split()[0]: dict(item.split('=',1) for item in line.split() if '=' in item)
                                 for line in raw.splitlines()}
            self.assertEqual(results['fill']['STORAGE-PERSIST']['verified'], '1')
            for mode in ('no-fill', 'partial', 'iosb-untouched', 'error-untouched'):
                self.assertEqual(results[mode]['STORAGE-PERSIST']['verified'], '0', mode)
            flush = results['flush-error-untouched']['STORAGE-FLUSH']
            self.assertEqual(flush['iosb'], '5a5a5a5a')
            self.assertEqual(flush['information'], '1515870810')

    @unittest.skipUnless(shutil.which('cc'), 'actual owned Win32 wrapper fault test requires host C compiler')
    def test_actual_windows_wrapper_assigns_before_resume_and_bounds_owned_descendants(self):
        fixture = PATH.parent.parent / 'tests/xbe/storage-perf'
        with tempfile.TemporaryDirectory(prefix='pr248-native-lifetime-') as work:
            directory = Path(work); (directory/'host-mock').mkdir()
            for name in ('windows-launch.c','make-pipe-header.py','desktop-pipe-server.ps1','desktop-pipe-client.ps1'):
                shutil.copyfile(fixture/name,directory/name)
            shutil.copyfile(fixture/'host-mock/windows-lifetime-mock.c',directory/'host-mock/windows-lifetime-mock.c')
            subprocess.run([sys.executable,str(directory/'make-pipe-header.py')],
                           check=True,capture_output=True,text=True)
            executable = directory / 'windows-lifetime-mock'
            compiled = subprocess.run(['cc', '-std=gnu11', '-O0', '-fshort-wchar',
                            str(directory/'host-mock/windows-lifetime-mock.c'), '-o', str(executable)],
                           capture_output=True, text=True)
            self.assertEqual(compiled.returncode,0,compiled.stderr)
            results = {}
            for mode in ('normal', 'timeout', 'assign-failure', 'rundown-unconfirmed', 'query-failure'):
                raw = subprocess.run([str(executable), mode], check=True, capture_output=True, text=True).stdout
                results[mode] = {k:int(v) for k,v in (item.split('=',1) for item in raw.split())}
            for mode in ('normal', 'timeout'):
                self.assertEqual(results[mode]['flags'] & 4, 4, 'client must start suspended')
                self.assertGreater(results[mode]['assign_order'], 0)
                self.assertGreater(results[mode]['resume_order'], results[mode]['assign_order'])
                self.assertEqual(results[mode]['job_kills'], 1, 'clear all owned descendants even after client exit')
            self.assertEqual(results['normal']['exit'], 0)
            self.assertNotEqual(results['timeout']['exit'], 0)
            self.assertEqual(results['assign-failure']['resume_order'], 0)
            self.assertEqual(results['assign-failure']['process_kills'], 1)
            self.assertNotEqual(results['assign-failure']['exit'], 0)
            self.assertNotEqual(results['rundown-unconfirmed']['exit'], 0)
            self.assertNotEqual(results['query-failure']['exit'], 0)

    @unittest.skipUnless(shutil.which('cc'), 'actual owned DVD fixture fault test requires host C compiler')
    def test_actual_dvd_fixture_requires_a_fresh_fill_on_every_repeated_read(self):
        fixture = PATH.parent.parent / 'tests/xbe/storage-perf'
        with tempfile.TemporaryDirectory(prefix='pr248-native-dvd-fault-') as work:
            directory = Path(work)
            # Compile the exact recorder source with invented public-header
            # bytes; no external ISO or executable body is needed by this test.
            shutil.copyfile(fixture/'dvd.c', directory/'owned-dvd.c')
            (directory/'dvd-metadata-reference.h').write_text(
                'static const UCHAR dvd_clean_header[4096]={0};\n'
                'static const UCHAR dvd_performance_header[4096]={0};\n'
                '#define DVD_CLEAN_FILE_BYTES 565248\n#define DVD_PERFORMANCE_FILE_BYTES 573440\n')
            executable = directory/'dvd-mock'
            subprocess.run(['cc', '-std=gnu11', '-O0', '-I'+str(directory),
                            '-I'+str(fixture/'host-mock'), '-I'+str(fixture),
                            str(fixture/'host-mock/dvd-mock.c'), '-o', str(executable)],
                           check=True, capture_output=True, text=True)
            results = {}
            for mode in ('fill', 'fill-once', 'no-fill', 'partial', 'iosb-untouched', 'error-untouched'):
                raw = subprocess.run([str(executable), mode], check=True, capture_output=True, text=True).stdout
                line = next(line for line in raw.splitlines() if line.startswith('STORAGE-PERF-CASE '))
                results[mode] = dict(item.split('=',1) for item in line.split() if '=' in item)
            self.assertEqual(results['fill']['failures'], '0')
            self.assertEqual(results['fill-once']['failures'], '1023')
            for mode in ('no-fill', 'partial', 'iosb-untouched', 'error-untouched'):
                self.assertEqual(results[mode]['failures'], '1024', mode)

if __name__ == '__main__': unittest.main()
