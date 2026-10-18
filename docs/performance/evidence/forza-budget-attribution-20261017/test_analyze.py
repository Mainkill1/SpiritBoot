# SPDX-License-Identifier: MIT
# Independently authored observation-parser tests; no title implementation.
import unittest
import analyze


def sample(**changes):
    row = dict(host_ns=1000, virtual_ns=900, thread=1, queue=2, budget=335000,
               limit=512, outstanding_start=0, outstanding_end=1, reads=1,
               bytes=512, callbacks=0, checks=2, deadline_pc=0x110d9f,
               empty=0, first_elapsed_ticks=100, elapsed_ticks=335001,
               total_ns=100, initial_ns=20, read_ns=30, wait_ns=10,
               callback_ns=0, read_open=0, wait_open=0, callback_open=0)
    row.update(changes)
    return row


def log(rows, **meta_changes):
    meta = dict(rows=len(rows), overflow=0, reentry=0)
    meta.update(meta_changes)
    lines = ['forza_budget_meta ' + ' '.join(f'{k}={v}' for k,v in meta.items())]
    for row in rows:
        lines.append('forza_budget ' + ' '.join(
            f'{k}={v:08x}' if k in analyze.HEX_FIELDS else f'{k}={v}'
            for k,v in row.items()))
    return '\n'.join(lines)


class ObservationTests(unittest.TestCase):
    def test_exact_timestamp_precision(self):
        self.assertEqual(analyze.utc_ns('1970-01-01T00:00:00.1234567+00:00'), 123456700)
        self.assertEqual(analyze.utc_ns('1970-01-01T00:00:00.000000001Z'), 1)

    def test_inclusive_endpoint_filter(self):
        rows = [sample(host_ns=x) for x in [99,100,200,201]]
        self.assertEqual([r['host_ns'] for r in analyze.select(rows,100,200)], [100,200])

    def test_boundary_span_is_reported_not_silently_whole(self):
        row = sample(host_ns=100, total_ns=100)
        _, rows = analyze.parse_log(log([row]))
        self.assertEqual(analyze.validate_rows(rows, 50)['potential_start_boundary_overlap'], 1)

    def test_exact_budget_is_exhausted(self):
        self.assertEqual(analyze.reason(sample(first_elapsed_ticks=335000, elapsed_ticks=335000)), 'initial_budget')
        self.assertEqual(analyze.reason(sample()), 'loop_budget')

    def test_empty_and_saturation_are_distinct(self):
        self.assertEqual(analyze.reason(sample(empty=1,deadline_pc=0,elapsed_ticks=100)), 'empty_work')
        self.assertEqual(analyze.reason(sample(deadline_pc=0,elapsed_ticks=100,outstanding_end=512)), 'outstanding_limit')
        self.assertEqual(analyze.reason(sample(deadline_pc=0,elapsed_ticks=100)), 'unclassified')

    def test_nested_time_not_added(self):
        row = sample(total_ns=100, initial_ns=50, wait_ns=40,callback_ns=30,read_ns=20)
        _, rows = analyze.parse_log(log([row]))
        self.assertEqual(analyze.validate_rows(rows,0)['open_spans'],0)
        summary = analyze.summarize(rows)
        self.assertEqual(summary['total_ns']['sum'],100)
        self.assertEqual(summary['callback_ns']['sum'],30)
        self.assertNotIn('cpu_ns',summary)

    def test_missing_or_duplicate_field_rejected(self):
        row=sample();del row['host_ns']
        with self.assertRaises(ValueError):analyze.parse_log(log([row]))
        with self.assertRaises(ValueError):analyze.parse_log(log([sample()])+' host_ns=1000')

    def test_malformed_or_truncated_rejected(self):
        for text in ['garbage', log([sample()]).replace('reads=1','reads=oops'), log([sample()]).replace('rows=1','rows=2')]:
            with self.subTest(text=text),self.assertRaises(ValueError):analyze.parse_log(text)

    def test_incomplete_or_lost_capture_rejected(self):
        for text in [log([sample()],overflow=1),log([sample()],reentry=1),log([sample(read_open=1)])]:
            with self.subTest(text=text),self.assertRaises(ValueError):analyze.parse_log(text)

    def test_inconsistent_values_rejected(self):
        for row in [sample(total_ns=-1),sample(initial_ns=101),sample(deadline_pc=0x110d9f,elapsed_ticks=100),sample(empty=1)]:
            with self.subTest(row=row),self.assertRaises(ValueError):analyze.parse_log(log([row]))

    def test_receipt_pair_required(self):
        with self.assertRaises(ValueError):analyze.replay_bounds('[]')
        with self.assertRaises(ValueError):analyze.replay_bounds('{"Id":"x-resume","Status":"failed"}')


if __name__=='__main__':unittest.main()
