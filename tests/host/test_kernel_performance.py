"""Malformed captures and noisy medians must never become timing claims."""
import copy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from tools.firmware import grade_tap, sha256
from tools.kernel_performance import BASELINE, WORKLOADS, analyze, capture


class AnalyzerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.runtime = {'baseline_release':{'sha256':BASELINE,'bytes':262144}, 'candidate_release':{'sha256':'c'*64,'bytes':262144,'source_tree':'f7adb302a762ed1945cc07d9c2ff428c643ba959'}}
        self.assets = {}
        for name,key in [('xemu','xemu'),('hdd','api_seed'),('dvd','benchmark_dvd')]:
            path = self.root / name; path.write_bytes(name.encode())
            record = {'path':str(path), 'sha256':sha256(path),'size':path.stat().st_size}
            self.assets[name] = record
            self.runtime[key] = record
        self.dataset = {'pairs':[], 'execution_log':[]}
        self.make_dataset()

    def dump(self,path,value):
        path.write_text(json.dumps(value))

    def make_dataset(self, baseline=1000, candidate=700, noise=0):
        self.dataset = {'pairs':[], 'execution_log':[]}
        start = datetime(2026,10,7,1,0,0,250000,tzinfo=timezone.utc)
        for i in range(7):
            pair = {'baseline':f'b{i}', 'candidate':f'c{i}'}
            self.dataset['pairs'].append(pair)
            for variant in (('baseline','candidate') if i%2 == 0 else ('candidate','baseline')):
                p = self.root / pair[variant]; p.mkdir(exist_ok=True)
                ticks = (baseline if variant == 'baseline' else candidate) + i
                lines = ['== kernel-performance begin ==','TAP version 14','1..42','# PERF-META version=1 clock=KeQueryPerformanceCounter frequency=3374488 samples=3','ok 1 - public-known-answers']
                for number,(name,iterations) in enumerate(WORKLOADS.items(),2):
                    for sample in range(1 if name=='object-cold-64' else 3):
                        value = ticks + ((sample-1)*noise if name != 'object-cold-64' else 0)
                        lines.append(f'# PERF workload={name} sample={sample} iterations={iterations} ticks={value*iterations} correct=1 checksum=811c9dc5')
                    lines.append(f'ok {number} - {name}')
                lines.extend(['# PERF-SUMMARY workloads=41 failures=0','== kernel-performance end PASS =='])
                serial = '\n'.join(lines)+'\n'; (p/'serial.log').write_text(serial)
                run = {'schema':1,'status':'passed','returncode':0,'memory_mib':128,'boot_mode':'open-direct','expect_tap':True,'snapshot':True,'started_utc':start.replace(microsecond=0).isoformat().replace('+00:00','Z'),'elapsed_seconds':1,'tap':grade_tap(serial),'assets':copy.deepcopy(self.assets)}
                run['assets']['flash'] = {'path':f'/unavailable/{variant}.bin','sha256':BASELINE if variant=='baseline' else 'c'*64,'size':262144}
                self.dump(p/'run.json',run)
                end = start+timedelta(seconds=1.1)
                self.dataset['execution_log'].append({'pair':i,'variant':variant,'capture':pair[variant],'started_utc':start.isoformat().replace('+00:00','Z'),'completed_utc':end.isoformat().replace('+00:00','Z')})
                start = end+timedelta(seconds=0.1)

    def report(self):
        self.dump(self.root/'pairs.json',self.dataset); self.dump(self.root/'runtime.json',self.runtime)
        return analyze(self.root/'pairs.json',self.root/'runtime.json')

    def mutate_run(self,change):
        p=self.root/'c0/run.json'; run=json.loads(p.read_text()); change(run); self.dump(p,run)

    def mutate_serial(self,change, regrade=True):
        p=self.root/'c0/serial.log'; serial=change(p.read_text()); p.write_text(serial)
        if regrade: self.mutate_run(lambda r:r.update(tap=grade_tap(serial)))

    def test_explicit_64_mib_capture(self):
        self.mutate_run(lambda r: r.update(memory_mib=64))
        result = capture(self.root / 'c0', {}, expected_memory_mib=64)
        self.assertEqual(result['memory_mib'], 64)
        self.assertEqual(len(result['workloads']), 41)

    def test_default_capture_still_requires_128_mib(self):
        self.assertEqual(capture(self.root / 'c0', {})['memory_mib'], 128)
        self.mutate_run(lambda r: r.update(memory_mib=64))
        with self.assertRaisesRegex(ValueError, 'runtime configuration mismatch'):
            capture(self.root / 'c0', {})
        with self.assertRaisesRegex(ValueError, 'runtime configuration mismatch'):
            self.report()

    def test_explicit_capacity_must_match_record(self):
        with self.assertRaisesRegex(ValueError, 'runtime configuration mismatch'):
            capture(self.root / 'c0', {}, expected_memory_mib=64)
        self.mutate_run(lambda r: r.update(memory_mib=64))
        with self.assertRaisesRegex(ValueError, 'runtime configuration mismatch'):
            capture(self.root / 'c0', {}, expected_memory_mib=128)

    def test_capture_rejects_unsupported_capacity(self):
        for capacity in (72, True, '64', 64.0, None):
            with self.subTest(capacity=capacity):
                with self.assertRaisesRegex(ValueError, 'unsupported expected memory capacity'):
                    capture(self.root / 'c0', {}, expected_memory_mib=capacity)

    def test_valid_seven_pairs_and_positive_threshold(self):
        report=self.report(); row=report['workloads']['pin-1']
        self.assertEqual(row['classification'],'timing improvement')
        self.assertEqual(row['paired_differences'],[300]*7)
        self.assertEqual(len(report['captures']),7)
        self.assertEqual(len(report['captures'][0]['baseline']['workloads']['empty']),3)
        self.assertFalse(report['overhead_subtracted'])

    def test_noise_prevents_false_speedup(self):
        self.make_dataset(noise=250)
        self.assertEqual(self.report()['workloads']['pin-1']['classification'],'timing inconclusive')

    def test_consistent_regression(self):
        self.make_dataset(candidate=1400)
        self.assertEqual(self.report()['workloads']['pin-1']['classification'],'timing regression')

    def test_small_inconclusive_change(self):
        self.make_dataset(candidate=999)
        self.assertEqual(self.report()['workloads']['pin-1']['classification'],'timing inconclusive')

    def set_workload_ticks(self, name, baseline, candidate):
        """Replace only permitted PERF tick fields in all fourteen captures."""
        for i in range(7):
            for prefix, ticks in [('b', baseline), ('c', candidate)]:
                path = self.root / f'{prefix}{i}' / 'serial.log'
                pattern = rf'(# PERF workload={re.escape(name)} sample=(\d+) iterations=\d+ ticks=)\d+'
                serial = re.sub(pattern, lambda m:m[1]+str(ticks[int(m[2])]), path.read_text())
                path.write_text(serial)

    def test_uint64_precision_noise_cannot_invent_improvement_or_regression(self):
        baseline = [9223372036854776833]*3
        candidate = [9223372036854775809,9223372036854776832,9223372036854776832]
        for reverse in (False,True):
            with self.subTest(reverse=reverse):
                self.set_workload_ticks('sysva-4096', candidate if reverse else baseline, baseline if reverse else candidate)
                row = self.report()['workloads']['sysva-4096']
                self.assertEqual(row['classification'],'timing inconclusive')
                self.assertEqual(row['median_difference'],-1 if reverse else 1)
                self.assertEqual(row['maximum_observed_variant_range'],1023)
                self.assertEqual(row['exact_decision']['median_difference'],
                                 {'numerator':-1 if reverse else 1,'denominator':1})
                self.assertEqual(row['exact_decision']['maximum_observed_variant_range'],
                                 {'numerator':1023,'denominator':1})

    def test_uint64_definite_improvement_and_regression_remain_supported(self):
        baseline = [9223372036854776833]*3
        candidate = [9223372036854775809]*3
        for reverse in (False,True):
            with self.subTest(reverse=reverse):
                self.set_workload_ticks('sysva-4096', candidate if reverse else baseline, baseline if reverse else candidate)
                row = self.report()['workloads']['sysva-4096']
                self.assertEqual(row['classification'],'timing regression' if reverse else 'timing improvement')
                self.assertEqual(row['median_difference'],-1024 if reverse else 1024)
                self.assertEqual(row['maximum_observed_variant_range'],0)

    def test_uint64_fractional_iteration_noise_remains_inconclusive(self):
        self.set_workload_ticks('pin-1', [9223372036854776833]*3,
                                [9223372036854775809,9223372036854776832,9223372036854776832])
        row = self.report()['workloads']['pin-1']
        self.assertEqual(row['classification'],'timing inconclusive')
        self.assertEqual(row['median_difference'],0.001)
        self.assertEqual(row['maximum_observed_variant_range'],1.023)
        self.assertEqual(row['exact_decision']['median_difference'],
                         {'numerator':1,'denominator':1000})
        self.assertEqual(row['exact_decision']['maximum_observed_variant_range'],
                         {'numerator':1023,'denominator':1000})
        json.dumps(row,allow_nan=False)

    def test_five_improving_pairs_cannot_claim_speedup(self):
        for i in range(7):
            for variant,prefix in [('baseline','b'),('candidate','c')]:
                target = (800 if variant == 'baseline' else 900) if i < 2 else (1100 if variant == 'baseline' else 700)
                path = self.root / f'{prefix}{i}' / 'serial.log'
                import re
                serial = re.sub(r'iterations=(\d+) ticks=\d+', lambda m:f'iterations={m[1]} ticks={int(m[1])*target}', path.read_text())
                path.write_text(serial)
        row = self.report()['workloads']['pin-1']
        self.assertEqual(row['improving_pairs'],5)
        self.assertGreater(row['median_difference'],row['maximum_observed_variant_range'])
        self.assertEqual(row['classification'],'timing inconclusive')

    def test_insufficient_pairs(self):
        self.dataset['pairs'].pop()
        with self.assertRaises(ValueError): self.report()

    def test_same_candidate_image(self):
        self.runtime['candidate_release']['sha256']=BASELINE
        with self.assertRaises(ValueError): self.report()

    def test_mismatched_iso_record(self):
        self.mutate_run(lambda r:r['assets']['dvd'].update(sha256='d'*64))
        with self.assertRaises(ValueError): self.report()

    def test_locally_modified_dvd(self):
        (self.root/'dvd').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.report()

    def test_failed_tap_cannot_be_disguised_by_run_manifest(self):
        self.mutate_serial(lambda s:s.replace('ok 1 -','not ok 1 -'),False)
        with self.assertRaises(ValueError): self.report()

    def test_todo_or_skip_refused(self):
        for directive in ('TODO','SKIP'):
            with self.subTest(directive=directive):
                self.make_dataset(); self.mutate_serial(lambda s:s.replace('ok 1 - public-known-answers','ok 1 - public-known-answers # '+directive))
                with self.assertRaises(ValueError): self.report()

    def test_missing_terminal(self):
        self.mutate_serial(lambda s:s.replace('== kernel-performance end PASS ==',''))
        with self.assertRaises(ValueError): self.report()

    def test_failed_driver(self):
        self.mutate_run(lambda r:r.update(returncode=1))
        with self.assertRaises(ValueError): self.report()

    def test_incorrect_sample_contract(self):
        changes=[('correct=1','correct=0'),('checksum=811c9dc5','checksum=00000000'),('frequency=3374488','frequency=0'),('iterations=1000','iterations=0'),('sample=0','sample=9'),('ticks=700000','ticks=18446744073709551616')]
        for before,after in changes:
            with self.subTest(after=after):
                self.make_dataset();self.mutate_serial(lambda s:s.replace(before,after,1))
                with self.assertRaises(ValueError): self.report()

    def test_missing_or_duplicate_workload(self):
        for duplicate in (False,True):
            self.make_dataset()
            def change(s):
                line=next(l for l in s.splitlines() if l.startswith('# PERF workload=pin-1 sample=0 '))
                return s.replace(line+'\n',line+'\n'+line+'\n' if duplicate else '')
            self.mutate_serial(change)
            with self.assertRaises(ValueError): self.report()

    def test_nonalternating_order(self):
        self.dataset['execution_log'][2:4]=reversed(self.dataset['execution_log'][2:4])
        with self.assertRaises(ValueError): self.report()

    def test_overlapping_timestamps(self):
        self.dataset['execution_log'][1]['started_utc']=self.dataset['execution_log'][0]['started_utc']
        with self.assertRaises(ValueError): self.report()

    def test_coarse_start_outside_interval(self):
        self.mutate_run(lambda r:r.update(started_utc='2026-10-07T01:00:30Z'))
        with self.assertRaises(ValueError): self.report()

    def test_execution_log_required(self):
        del self.dataset['execution_log']
        with self.assertRaises(ValueError): self.report()

    def test_bad_configuration(self):
        for field,value in [('snapshot',False),('memory_mib',64),('expect_tap',False),('boot_mode','http')]:
            self.make_dataset(); self.mutate_run(lambda r:r.update({field:value}))
            with self.assertRaises(ValueError): self.report()

    def test_cli_outputs_and_refusal(self):
        self.report()
        command=[sys.executable,str(Path(__file__).resolve().parents[2]/'scripts/analyze-kernel-performance.py'),str(self.root/'pairs.json'),'--runtime-inputs',str(self.root/'runtime.json'),'--candidate-hash','c'*64,'--output',str(self.root/'report.json'),'--markdown',str(self.root/'report.md')]
        result=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertTrue((self.root/'report.md').read_text().startswith('7 alternating pairs'))
        command[command.index('--candidate-hash')+1]='e'*64
        self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)
