# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('burst_analyze', Path(__file__).with_name('analyze.py'))
MODULE = None
if Path(SPEC.origin).exists():
    MODULE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(MODULE)


def log():
    lines = ['# FORZA-BURST-META version=1 frequency=1000000 seconds=10 cases=8 depth=8 frame_ms=33']
    for index, length in enumerate((0, 1, 35, 36, 37, 0xc1008c48, 0xffffffff)):
        fields = {name: 0xa5a5a5a5 for name in ('length', 'total', 'available', 'committed', 'reserved', 'cache', 'pool', 'stack', 'image')}
        fields['length'] = length
        fields.update({f'{side}{n}': 0xa5a5a5a5 for side in ('pre', 'post') for n in range(4)})
        lines.append(f'# FORZA-BURST-MM index={index} input={length:08x} status=c000000d ' + ' '.join(f'{k}={v:08x}' for k,v in fields.items()))
    for case in range(8):
        target = 783 if case < 4 else 900
        budget = (250, 500, 1000, 0)[case % 4]
        lines += [f'# FORZA-BURST-CASE id={case} target={target} before={target} after={target} budget_us={budget} operations=64 verified=64 callbacks=64 bytes=2113536 elapsed=10000000 frames=32 high_water=2 failures=0',
                  f'# FORZA-BURST-TIMING id={case} pending=64 budget_stops=0 empty_immediate=64 pair_same=32 pair_split=0 pair_gap_sum=640 pair_gap_max=20 burst_sum=1600 burst_max=50 poll_sum=320']
        for size in (65536, 512):
            lines.append(f'# FORZA-BURST-SIZE id={case} bytes={size} count=32 submit_sum=320 submit_max=10 callback_sum=1056000 callback_max=33000')
        for seq in range(64):
            frame=seq//2
            at=1+frame*33000
            issue=at+(seq%2)*20
            size=65536 if seq%2==0 else 512
            offset=((frame*197)%127)*65536+(65536 if seq%2 else 0)
            lines.append(f'# FORZA-BURST-OP id={case} seq={seq} slot={seq%2} bytes={size} offset={offset} frame={frame} issue={issue} returned={issue+10} callback={at+32000} burst={at} status=00000103 calls=1')
        for frame in range(32):
            at=1+frame*33000
            lines.append(f'# FORZA-BURST-FRAME id={case} frame={frame} begin={at} end={at+50} issued=2 before=0 after=2 budget_hit=0 submit_ticks=20 poll_ticks=10')
    lines += ['# FORZA-BURST-END failures=0']
    return '\n'.join(lines)


class AnalyzerTests(unittest.TestCase):
    def analyze(self, text):
        self.assertIsNotNone(MODULE, 'burst analyzer must exist')
        return MODULE.analyze(text)

    def test_complete_run_splits_size_cost_and_pair_metrics(self):
        result = self.analyze(log())
        self.assertEqual(len(result['cases']), 8)
        self.assertEqual(result['cases'][0]['sizes'][0]['submit_mean_us'], 10)
        self.assertEqual(result['cases'][0]['pair_gap_mean_ms'], .020)
        self.assertEqual(len(result['statistics_queries']), 7)

    def test_query_failure_field_mutation_is_an_observation(self):
        result = self.analyze(log().replace('available=a5a5a5a5', 'available=00000000', 1))
        self.assertEqual(result['statistics_queries'][0]['available'], 0)

    def test_missing_final_marker_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'END'):
            self.analyze(log().rsplit('\n',1)[0])

    def test_duplicate_callback_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'callback'):
            self.analyze(log().replace('callbacks=64', 'callbacks=65', 1))

    def test_reused_slot_before_callback_is_rejected(self):
        text=log().replace('seq=1 slot=1', 'seq=1 slot=0', 1)
        with self.assertRaisesRegex(ValueError, 'reuse'):
            self.analyze(text)

    def test_missing_operation_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'OP'):
            self.analyze('\n'.join(row for row in log().splitlines() if 'OP id=0 seq=5 ' not in row))

    def test_missing_frame_sample_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'FRAME'):
            self.analyze('\n'.join(row for row in log().splitlines() if 'FRAME id=0 frame=5 ' not in row))

    def test_short_case_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duration'):
            self.analyze(log().replace('elapsed=10000000', 'elapsed=9999999', 1))

    def test_concurrency_over_depth_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'depth'):
            self.analyze(log().replace('high_water=2', 'high_water=9', 1))

    def test_invalid_length_canary_overwrite_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'canary'):
            self.analyze(log().replace('post0=a5a5a5a5', 'post0=00000000', 1))

    def test_missing_statistics_query_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'MM'):
            self.analyze('\n'.join(row for row in log().splitlines() if 'MM index=5 ' not in row))

    def test_pair_accounting_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'pair'):
            self.analyze(log().replace('pair_same=32', 'pair_same=31', 1))

    def test_no_new_issue_after_previous_return_exhausted_budget(self):
        text=log().replace('issue=1 returned=11 callback=', 'issue=1 returned=301 callback=',1)
        text=text.replace('issue=21 returned=31 callback=', 'issue=321 returned=331 callback=',1)
        text=text.replace('begin=1 end=51 issued=', 'begin=1 end=351 issued=',1)
        text=text.replace('submit_ticks=20 poll_ticks=', 'submit_ticks=320 poll_ticks=',1)
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.analyze(text)

    def test_uncapped_case_cannot_claim_budget_stop(self):
        text=log().replace('TIMING id=3 pending=64 budget_stops=0', 'TIMING id=3 pending=64 budget_stops=1')
        with self.assertRaisesRegex(ValueError, 'uncapped'):
            self.analyze(text)

    def test_out_of_range_sample_case_is_rejected(self):
        row=next(row for row in log().splitlines() if 'FORZA-BURST-SIZE id=0' in row)
        with self.assertRaisesRegex(ValueError, 'case'):
            self.analyze(log()+'\n'+row.replace('id=0','id=99'))

if __name__ == '__main__':
    unittest.main()
