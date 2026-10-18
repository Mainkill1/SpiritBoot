# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('cadence_analyze', Path(__file__).with_name('analyze.py'))
if SPEC and SPEC.loader and Path(SPEC.origin).exists():
    MODULE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(MODULE)
else:
    MODULE = None


def log():
    lines = ['# FORZA-CADENCE-META version=1 frequency=1000000 seconds=10 cases=8',
             '# FORZA-CADENCE-HANDOFF-END cases=40 failures=0',
             '# FORZA-CADENCE-SEM-END cases=32 failures=0']
    for kind in range(5):
        for n in range(8):
            first = int(kind == 3)
            lines.append(f'# FORZA-CADENCE-HANDOFF kind={kind} index={n} enter=10 producer={18 if kind == 4 else 12} enqueued={5 if kind == 3 else 19 if kind == 4 else 14} returned=16 callback={14 if first else 20} status={"000000c0" if first else "00000000"} enqueue_status=00000000 first_calls={first} calls=1 errors=0')
    for n in range(32):
        lines.append(f'# FORZA-CADENCE-SEM index={n} before=0 after=1 return=000000c0 drain=00000000 errors=0')
    for i in range(8):
        target = 900 if i < 4 else 783
        size = 512 if i % 4 < 2 else 65536
        lines += [f'# FORZA-CADENCE-CASE id={i} target={target} before={target} after={target} bytes={size} frame_ms={33 if i % 2 else 0} operations=100 total_bytes={100*size} elapsed=10000000 failures=0',
                  f'# FORZA-CADENCE-TIMING id={i} pending=100 immediate=0 ready_misses=0 submit_sum=1000 callback_sum=3300000 poll_sum=1000 callback_max=33000',
                  f'# FORZA-CADENCE-HIST id={i} low_ms=33 count=100']
        for n in range(32):
            t = n * 10
            lines.append(f'# FORZA-CADENCE-OP id={i} index={n} issue={t+1} returned={t+2} immediate={t+3} callback={t+4} last_poll={t+3} observed=0 status=00000103 polls=1 calls=1 immediate_status=000000c0')
    lines += ['# FORZA-CADENCE-END failures=0']
    return '\n'.join(lines)


class AnalyzerTests(unittest.TestCase):
    def analyze(self, value):
        self.assertIsNotNone(MODULE, 'serial analyzer must exist')
        return MODULE.analyze(value)

    def test_complete_run_reports_mean_and_histogram_bounds(self):
        result = self.analyze(log())
        self.assertEqual(len(result['cases']), 8)
        self.assertEqual(result['cases'][0]['callback_mean_ms'], 33)
        self.assertEqual(result['cases'][0]['callback_p95_bucket_ms'], [33, 34])

    def test_truncated_run_is_not_a_pass(self):
        with self.assertRaisesRegex(ValueError, 'END'):
            self.analyze(log().rsplit('\n', 1)[0])

    def test_short_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duration'):
            self.analyze(log().replace('elapsed=10000000', 'elapsed=1000000', 1))

    def test_failed_oracle_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'failures'):
            self.analyze(log().replace('failures=0', 'failures=1', 1))

    def test_missing_histogram_observations_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'histogram'):
            self.analyze(log().replace('count=100', 'count=99', 1))

    def test_duplicate_case_is_rejected(self):
        line = next(line for line in log().splitlines() if 'FORZA-CADENCE-CASE id=0' in line)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.analyze(log() + '\n' + line)

    def test_handoff_only_labels_established_enqueue_during_call(self):
        result = self.analyze(log())
        self.assertEqual(result['handoff'][0]['outcome'], 'queued_during_call_delivered_later')
        self.assertEqual(result['handoff'][-1]['outcome'], 'enqueue_during_call_not_established')

    def test_missing_handoff_rows_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'HANDOFF'):
            self.analyze('\n'.join(line for line in log().splitlines() if 'HANDOFF kind=' not in line))

    def test_missing_semantic_rows_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SEM'):
            self.analyze('\n'.join(line for line in log().splitlines() if 'SEM index=' not in line))

    def test_missing_operation_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'OP'):
            self.analyze('\n'.join(line for line in log().splitlines() if 'OP id=3 index=11 ' not in line))

    def test_wrong_semantic_wait_status_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SEM'):
            self.analyze(log().replace('return=000000c0', 'return=00000000', 1))

    def test_duplicate_callback_in_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'OP'):
            self.analyze(log().replace('calls=1 immediate_status=', 'calls=2 immediate_status=', 1))

    def test_handoff_after_return_cannot_claim_first_delivery(self):
        with self.assertRaisesRegex(ValueError, 'HANDOFF'):
            self.analyze(log().replace('first_calls=0 calls=1', 'first_calls=1 calls=1', 1))

if __name__ == '__main__':
    unittest.main()
