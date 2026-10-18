# SPDX-License-Identifier: MIT
"""Synthetic identity -> strict analyzers -> prefix join integration tests."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analyze_prefix import parse as parse_prefix
from join_prefix import join

IDENTITY_TOOLS = Path(__file__).resolve().parents[2] / 'forza-request-identity-20261017'
sys.path.insert(0, str(IDENTITY_TOOLS))
import analyze_identity as identity
import analyze_timeline as timeline
import analyze_prebind as prebind


def event(kind, api=0, iosb=0, child=0, parent=0, **extra):
    row = dict.fromkeys(identity.FIELDS, 0)
    row.update(kind=kind, api=api, iosb=iosb, child=child, parent=parent,
               thread=1, srb=child + 4 if kind in (3, 4, 7) else 0, **extra)
    return row


def identity_text():
    rows = [
        event(1, 1, 100, bytes=512),                 # 1
        event(12, 1, 100, parent=300, value0=1),    # 2 ready
        event(3, 1, 100, child=200, parent=300),    # 3 bind
        event(7, 1, child=200, status=0x103),       # 4 queue
        event(2, 1, 100, status=0x103),             # 5 return
        event(1, 2, 104, bytes=512),                # 6
        event(12, 2, 104, parent=500, value0=1),   # 7 ready
        event(4, 2, child=200),                    # 8 old request starts in API2
        event(5, child=200),                       # 9 old completion
        event(5, iosb=100, child=300),             # 10
        event(6, iosb=100, info=512),              # 11
        event(3, 2, 104, child=400, parent=500),   # 12 own bind
        event(4, 2, child=400),                    # 13 own start
        event(2, 2, 104, status=0x103),            # 14 return
        event(5, child=400),                       # 15
        event(5, iosb=104, child=500),             # 16
        event(6, iosb=104, info=512),              # 17
        event(1, 3, 108, bytes=512),               # 18 valid off-receipt call
        event(12, 3, 108, parent=700, value0=1),   # 19
        event(3, 3, 108, child=600, parent=700),   # 20
        event(4, 3, child=600),                    # 21
        event(2, 3, 108, status=0x103),            # 22
    ]
    output = [f'identity_meta version=1 events={len(rows)} overflow=0 reentry=0 lost=0 read_fail=0 open_api=0 map_open=0 map_reentry=0 map_lost=0']
    for seq, row in enumerate(rows, 1):
        row.update(seq=seq, host_ns=seq*1000, virtual_ns=seq*1000)
        output.append('identity_event ' + ' '.join(f'{key}={row[key]:08x}' if key in identity.HEX else f'{key}={row[key]}' for key in sorted(identity.FIELDS)))
    return '\n'.join(output + [f'identity_end events={len(rows)}']) + '\n'


def prefix_text(rows=None, translation_seq=1):
    if rows is None:
        rows = [(1, seq, seq) for seq in (1, 2, 3, 4)] + [(2, seq, seq) for seq in (6, 7, 8, 9, 10, 11, 12, 13)] + [(3, 18, 5)]
    lines = [f'prefix_meta version=1 descriptors=1 rows={len(rows)} translations=1 overflow=0 reentry=0 thread_mismatch=0 invalid_prefix=0 open_api=0',
             f'prefix_tb id=1 pc=84001000 count=1 generation=1 born_api=1 born_identity_seq={translation_seq}',
             'prefix_insn tb=1 ordinal=1 pc=84001000 rep=0']
    lines += [f'prefix_row api={api} identity_seq={seq} tb=1 first=1 last=1 executions={count} begun={count} rep_iterations=0' for api, seq, count in rows]
    return '\n'.join(lines + [f'prefix_translation api=1 identity_seq={translation_seq} tb=1', f'prefix_end rows={len(rows)}']) + '\n'


SYMBOLS = {'image_sha256': 'a'*64, 'instruction_owners': {'84001000': 'owned_helper'}}


class IndependentJoinTests(unittest.TestCase):
    def inputs(self, text=None, start=0, end=17000):
        _, events = identity.parse(identity_text())
        return (parse_prefix(prefix_text() if text is None else text), SYMBOLS, events,
                timeline.timeline(events, start, end), prebind.analyze(events, start, end))

    def test_full_identity_pipeline_preserves_phase_and_call_counts(self):
        result = join(*self.inputs())
        self.assertEqual(result['selected_reads'], 2)
        self.assertEqual(result['excluded_prefix_apis_outside_selected_identity_cohort'], [3])
        by_api = {row['api']: row for row in result['reads']}
        self.assertEqual(by_api[1]['phase_begun'], {'entry_to_ready': 1, 'ready_to_bind': 2, 'bind_to_return': 7})
        self.assertEqual(by_api[2]['phase_begun'], {'entry_to_ready': 6, 'ready_to_bind': 45, 'bind_to_start': 12, 'start_to_return': 13})
        self.assertEqual(sum(row['begun'] for row in result['reads']), 86)
        for row in result['reads']:
            self.assertEqual(sum(row['phase_begun'].values()), row['begun'])
            self.assertEqual(sum(row['symbols'].values()), row['begun'])
            self.assertEqual(row['prebind_begun'], sum(row['phase_begun'].get(p, 0) for p in ('entry_to_ready', 'ready_to_bind')))

    def test_event_api_label_is_not_request_ownership(self):
        args = self.inputs()
        # API1's actual drive start is event8, whose current-call label is API2.
        first, second = args[3]['reads']
        self.assertEqual(first['lifecycle'][0]['starts'][0]['seq'], 8)
        self.assertEqual(second['lifecycle'][0]['starts'][0]['seq'], 13)
        result = join(*args)
        self.assertEqual(result['reads'][0]['partition'], 'queued_start_after_return')
        self.assertEqual(result['reads'][1]['phase_begun']['ready_to_bind'], 45)
        self.assertEqual(result['reads'][1]['phase_begun']['bind_to_start'], 12)

    def test_empty_cohorts_are_explicit_null_summaries(self):
        result = join(*self.inputs())
        empty = result['cohorts_512_extent_hits']['long_gap_direct']
        self.assertEqual(empty['apis'], [])
        self.assertEqual(empty['calls'], 0)
        self.assertEqual(empty['prebind_begun'], {'n': 0, 'sum': 0, 'median': None, 'min': None, 'max': None})
        self.assertEqual(empty['prebind_symbols'], {})
        self.assertEqual(result['cohorts_512_extent_hits']['nearby_queued_later']['apis'], [])

    def test_nearby_queued_cohort_gap_boundaries(self):
        # Unit-level predicate inputs; these gap mutations are not new traces.
        for gap, expected in [(None, []), (-1, []), (0, [1]), (99, [1]),
                              (100, [1]), (999.999, [1]), (1000, []), (10000, [])]:
            with self.subTest(gap=gap):
                args = self.inputs()
                args[4]['reads'][0]['intercall_gap_us'] = gap
                result = join(*args)
                self.assertEqual(result['cohorts_512_extent_hits']['nearby_queued_later']['apis'], expected)

    def test_selected_call_missing_prefix_never_silently_drops(self):
        rows = [(1, 1, 1), (3, 18, 1)]
        with self.assertRaisesRegex(ValueError, 'lacks prefix'):
            join(*self.inputs(prefix_text(rows)))

    def test_selected_row_outside_its_call_rejects(self):
        for seq in (5, 6, 18):
            with self.subTest(seq=seq), self.assertRaises(ValueError):
                join(*self.inputs(prefix_text([(1, seq, 1), (2, 6, 1)])))

    def test_selected_row_absent_identity_sequence_rejects(self):
        with self.assertRaisesRegex(ValueError, 'absent identity'):
            join(*self.inputs(prefix_text([(1, 99, 1), (2, 6, 1)])))

    def test_selected_translation_outside_call_rejects(self):
        with self.assertRaises(ValueError):
            join(*self.inputs(prefix_text(translation_seq=5)))

    def test_selected_translation_absent_identity_rejects(self):
        with self.assertRaises(ValueError):
            join(*self.inputs(prefix_text(translation_seq=99)))

    def test_nonexistent_api_must_not_be_disguised_as_off_receipt(self):
        rows = [(1, 1, 1), (2, 6, 1), (999, 18, 1)]
        with self.assertRaises(ValueError):
            join(*self.inputs(prefix_text(rows)))

    def test_off_receipt_api_still_requires_valid_identity_sequence(self):
        rows = [(1, 1, 1), (2, 6, 1), (3, 99, 1)]
        with self.assertRaises(ValueError):
            join(*self.inputs(prefix_text(rows)))

    def test_off_receipt_api_still_requires_sequence_inside_its_call(self):
        rows = [(1, 1, 1), (2, 6, 1), (3, 6, 1)]
        with self.assertRaises(ValueError):
            join(*self.inputs(prefix_text(rows)))

    def test_off_receipt_translation_absent_sequence_rejects(self):
        text = prefix_text().replace('born_api=1 born_identity_seq=1', 'born_api=3 born_identity_seq=99')
        text = text.replace('prefix_translation api=1 identity_seq=1', 'prefix_translation api=3 identity_seq=99')
        with self.assertRaises(ValueError):
            join(*self.inputs(text))

    def run_cli(self, start=0, end=17000):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, text in [('prefix.log', prefix_text()), ('identity.log', identity_text()), ('symbols.json', json.dumps(SYMBOLS)),
                ('receipts.jsonl', '\n'.join(json.dumps(row) for row in [
                    {'Id': 'synthetic-resume', 'Status': 'completed', 'EndedUtc': f'1970-01-01T00:00:00.{start:09d}Z'},
                    {'Id': 'synthetic-pause', 'Status': 'completed', 'StartedUtc': f'1970-01-01T00:00:00.{end:09d}Z'}]))]:
                (root / name).write_text(text)
            command = [sys.executable, str(Path(__file__).with_name('join_prefix.py')),
                '--prefix', str(root/'prefix.log'), '--identity', str(root/'identity.log'),
                '--receipts', str(root/'receipts.jsonl'), '--identity-tools', str(IDENTITY_TOOLS),
                '--symbol-map', str(root/'symbols.json'), '--output', str(root/'joined.json')]
            subprocess.run(command, check=True, capture_output=True, text=True)
            return json.loads((root/'joined.json').read_text())

    def test_cli_end_to_end_binds_synthetic_inputs_and_selects_receipts(self):
        result = self.run_cli()
        self.assertEqual(result['selected_reads'], 2)
        self.assertEqual(set(result['hashes']), {'prefix', 'identity', 'receipts', 'symbol_map'})
        self.assertEqual(result['reads'][1]['begun'], 76)

    def test_receipt_wholly_inside_call_cannot_silently_exclude_it(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_cli(start=7000, end=13000)

    def test_receipt_cutting_selected_call_cannot_silently_exclude_it(self):
        with self.assertRaises(subprocess.CalledProcessError):
            self.run_cli(end=13000)



if __name__ == '__main__':
    unittest.main()
