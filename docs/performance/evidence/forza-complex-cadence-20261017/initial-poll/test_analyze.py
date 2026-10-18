# SPDX-License-Identifier: GPL-2.0-or-later
import importlib.util
from pathlib import Path
import unittest

SPEC = importlib.util.spec_from_file_location('pump_analyze', Path(__file__).with_name('analyze.py'))
MODULE = None
if Path(SPEC.origin).exists():
    MODULE = importlib.util.module_from_spec(SPEC)
    SPEC.loader.exec_module(MODULE)


def log():
    lines = ['# FORZA-PUMP-META version=1 frequency=1000000 seconds=10 cases=8 depth=8 buffers=16 frame_ms=33']
    for index, length in enumerate((0, 1, 35, 36, 37, 0xc1008c48, 0xffffffff)):
        fields = {name: 0xa5a5a5a5 for name in ('length', 'total', 'available', 'committed', 'reserved', 'cache', 'pool', 'stack', 'image')}
        fields['length'] = length
        fields.update({f'{side}{n}': 0xa5a5a5a5 for side in ('pre', 'post') for n in range(4)})
        lines.append(f'# FORZA-PUMP-MM index={index} input={length:08x} status=c000000d ' + ' '.join(f'{k}={v:08x}' for k,v in fields.items()))
    for case in range(8):
        target = 783 if case < 4 else 900
        budget = (250, 450, 1000, 0)[case % 4]
        lines += [f'# FORZA-PUMP-CASE id={case} target={target} before={target} after={target} budget_us={budget} operations=64 verified=64 callbacks=64 bytes=2113536 elapsed=10000000 frames=32 high_water=2 failures=0',
                  f'# FORZA-PUMP-TIMING id={case} pending=64 budget_stops=0 empty_immediate=64 pair_same=32 pair_split=0 pair_gap_sum=640 pair_gap_max=20 burst_sum=1760 burst_max=55 poll_sum=320 initial_sum=160 initial_max=5 initial_callbacks=62 zero_issue_frames=0']
        for size in (65536, 512):
            lines.append(f'# FORZA-PUMP-SIZE id={case} bytes={size} count=32 submit_sum=320 submit_max=10 callback_sum=1056000 callback_max=33000')
        for seq in range(64):
            frame=seq//2
            at=1+frame*33000
            issue=at+5+(seq%2)*20
            size=65536 if seq%2==0 else 512
            offset=((frame*197)%127)*65536+(65536 if seq%2 else 0)
            lines.append(f'# FORZA-PUMP-OP id={case} seq={seq} slot={seq%4} bytes={size} offset={offset} frame={frame} issue={issue} returned={issue+10} callback={at+33002} burst={at} checked={issue} status=00000103 calls=1')
        for frame in range(32):
            at=1+frame*33000
            lines.append(f'# FORZA-PUMP-FRAME id={case} frame={frame} begin={at} end={at+55} issued=2 before={0 if frame==0 else 2} after_initial=0 after=2 budget_hit=0 submit_ticks=20 poll_ticks=10 initial_return={at+5} initial_ticks=5 initial_callbacks={0 if frame==0 else 2}')
    lines += ['# FORZA-PUMP-END failures=0']
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
        text=log().replace('issue=6 returned=16 callback=', 'issue=6 returned=306 callback=',1)
        text=text.replace('issue=26 returned=36 callback=', 'issue=326 returned=336 callback=',1)
        text=text.replace('begin=1 end=56 issued=', 'begin=1 end=356 issued=',1)
        text=text.replace('submit_ticks=20 poll_ticks=', 'submit_ticks=320 poll_ticks=',1)
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.analyze(text)

    def test_uncapped_case_cannot_claim_budget_stop(self):
        text=log().replace('TIMING id=3 pending=64 budget_stops=0', 'TIMING id=3 pending=64 budget_stops=1')
        with self.assertRaisesRegex(ValueError, 'uncapped'):
            self.analyze(text)

    def test_out_of_range_sample_case_is_rejected(self):
        row=next(row for row in log().splitlines() if 'FORZA-PUMP-SIZE id=0' in row)
        with self.assertRaisesRegex(ValueError, 'case'):
            self.analyze(log()+'\n'+row.replace('id=0','id=99'))

    def test_initial_poll_cost_is_inside_pump(self):
        result=self.analyze(log())
        self.assertEqual(result['cases'][0]['initial_poll_mean_us'], 5)

    def test_no_issue_when_initial_poll_exhausts_budget(self):
        text=log().replace('initial_return=6 initial_ticks=5', 'initial_return=301 initial_ticks=300', 1)
        with self.assertRaisesRegex(ValueError, 'initial|budget|cost'):
            self.analyze(text)

    def test_sample_deadline_check_must_precede_issue(self):
        with self.assertRaisesRegex(ValueError, 'check'):
            self.analyze(log().replace('checked=6', 'checked=7',1))

    def test_rejects_deadline_check_at_budget(self):
        text=log().replace('issue=6 returned=16', 'issue=251 returned=261',1).replace('checked=6', 'checked=251',1)
        with self.assertRaises(ValueError):self.analyze(text)

    def test_valid_zero_issue_initial_timeout_then_later_progress(self):
        import re
        rows=[]
        for row in log().splitlines():
            if 'CASE id=0 ' in row:
                row=row.replace('frames=32','frames=33')
            if 'TIMING id=0 ' in row:
                row=row.replace('budget_stops=0','budget_stops=1').replace('burst_sum=1760 burst_max=55','burst_sum=2060 burst_max=300')
                row=row.replace('initial_sum=160 initial_max=5','initial_sum=460 initial_max=300').replace('zero_issue_frames=0','zero_issue_frames=1')
            if 'OP id=0 ' in row or 'FRAME id=0 ' in row:
                if 'FRAME id=0 frame=31 ' in row:continue
                for key in ('issue','returned','callback','burst','checked','begin','end','initial_return'):
                    row=re.sub(r'(?<!\w)'+key+r'=(\d+)',lambda m:key+'='+str(int(m[1])+33000),row)
                row=re.sub(r'(?<!\w)frame=(\d+)',lambda m:'frame='+str(int(m[1])+1),row)
            rows.append(row)
        rows.append('# FORZA-PUMP-FRAME id=0 frame=0 begin=1 end=301 issued=0 before=0 after_initial=0 after=0 budget_hit=1 submit_ticks=0 poll_ticks=0 initial_return=301 initial_ticks=300 initial_callbacks=0')
        result=self.analyze('\n'.join(rows))
        self.assertEqual(result['cases'][0]['zero_issue_frames'],1)
        self.assertAlmostEqual(result['cases'][0]['initial_poll_mean_us'],460/33)

    def test_initial_poll_completion_cannot_be_reused_in_same_pump(self):
        with self.assertRaisesRegex(ValueError,'reuse'):
            self.analyze(log().replace('seq=2 slot=2','seq=2 slot=0',1))

    def test_no_callbacks_between_frame_end_and_next_initial_poll(self):
        text=log().replace('frame=1 begin=33001 end=33056 issued=2 before=2', 'frame=1 begin=33001 end=33056 issued=2 before=1',1)
        text=text.replace('initial_return=33006 initial_ticks=5 initial_callbacks=2','initial_return=33006 initial_ticks=5 initial_callbacks=1',1).replace('initial_callbacks=62','initial_callbacks=61',1)
        with self.assertRaisesRegex(ValueError,'continuity'):
            self.analyze(text)

    def test_frame_cannot_create_unexplained_outstanding_requests(self):
        text=log().replace('after_initial=0 after=2','after_initial=0 after=3',1)
        with self.assertRaisesRegex(ValueError,'outstanding'):
            self.analyze(text)

    def test_buffer_count_is_separate_from_queue_depth(self):
        with self.assertRaisesRegex(ValueError, 'META'):
            self.analyze(log().replace('buffers=16','buffers=8',1))

if __name__ == '__main__':
    unittest.main()
