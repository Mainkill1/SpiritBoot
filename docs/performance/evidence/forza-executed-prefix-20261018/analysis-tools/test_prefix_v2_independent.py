# SPDX-License-Identifier: MIT
"""Independent v2 accounting and CLI-binding tests; synthetic data only."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from analyze_prefix import parse, counts_by_api
from join_prefix import join
from test_join_independent import identity_text, prefix_text, identity, timeline, prebind, IDENTITY_TOOLS, SYMBOLS

HANDLE = 0x42c
EXCLUDED = [
    'prefix_excluded api=1 identity_seq=2 pc=00100000 first=2 last=3 executions=3 begun=6 rep_iterations=9',
    'prefix_excluded api=2 identity_seq=8 pc=00102000 first=1 last=1 executions=4 begun=4 rep_iterations=0',
    'prefix_excluded api=3 identity_seq=18 pc=00103000 first=1 last=1 executions=2 begun=2 rep_iterations=0',
]


def v2():
    lines = prefix_text().splitlines()
    lines[0] = lines[0].replace('version=1', 'version=2') + ' excluded_rows=3'
    footer = lines.pop() + ' excluded_rows=3'
    return '\n'.join(lines + [
        'prefix_limits handle=0000042c max_api=64 admitted=3 returned=3 admission_closed=0 range_count=1',
        'prefix_range id=1 start=84001000 end=84002000',
        'prefix_health allocated_descriptors=1 allocated_instructions=1 descriptor_overflow=0 instruction_overflow=0 row_overflow=0 excluded_overflow=0 max_probe=1 max_excluded_probe=1',
    ] + EXCLUDED + [footer]) + '\n'


def matching_identity():
    lines = identity_text().splitlines()
    return '\n'.join(line.replace('value0=00000000', f'value0={HANDLE:08x}')
        if ' kind=1 ' in line else line for line in lines) + '\n'


class IndependentV2Tests(unittest.TestCase):
    def joined(self, text=None):
        _, events = identity.parse(matching_identity())
        return join(parse(v2() if text is None else text), SYMBOLS, events,
                    timeline.timeline(events, 0, 17000), prebind.analyze(events, 0, 17000))

    def test_owned_excluded_and_unknown_counts_preserved_separately(self):
        capture = parse(v2())
        result = counts_by_api(capture, SYMBOLS)
        self.assertEqual(sum(row['begun'] for row in result.values()), 103)
        self.assertEqual(sum(row['excluded_begun'] for row in result.values()), 12)
        self.assertEqual(result[1]['symbols'], {'owned_helper': 10, '<excluded>': 6})
        self.assertEqual(result[1]['rep_iterations_known'], 9)
        self.assertEqual(result[1]['begun'], 16)  # REP body count is not added.
        self.assertEqual(result[1]['unknown_pcs'], {})
        unknown = counts_by_api(capture, {'instruction_owners': {}})[1]
        self.assertEqual(unknown['symbols'], {'<unknown>': 10, '<excluded>': 6})
        self.assertEqual(unknown['unknown_pcs'], {'84001000': 10})
        for row in result.values():
            self.assertEqual(sum(row['symbols'].values()), row['begun'])
            self.assertEqual(sum(sum(phase.values()) for phase in row['phases_by_identity_seq'].values()), row['begun'])

    def test_excluded_pc_is_never_promoted_by_static_symbol_map(self):
        symbols = {'instruction_owners': {'84001000': 'owned_helper', '00100000': 'must_not_attribute'}}
        result = counts_by_api(parse(v2()), symbols)[1]
        self.assertNotIn('must_not_attribute', result['symbols'])
        self.assertEqual(result['symbols']['<excluded>'], 6)

    def test_admitted_count_cannot_understate_observed_apis(self):
        for count in (0, 1, 2):
            with self.subTest(count=count), self.assertRaises(ValueError):
                parse(v2().replace('admitted=3 returned=3', f'admitted={count} returned={count}'))

    def test_every_owned_instruction_pc_is_range_checked(self):
        text = v2().replace('count=1 generation=1', 'count=2 generation=1')
        text = text.replace('prefix_insn tb=1 ordinal=1 pc=84001000 rep=0',
                            'prefix_insn tb=1 ordinal=1 pc=84001000 rep=0\nprefix_insn tb=1 ordinal=2 pc=84002000 rep=0')
        text = text.replace('allocated_instructions=1', 'allocated_instructions=2')
        with self.assertRaises(ValueError):
            parse(text)

    def test_excluded_phase_counts_and_off_receipt_call_are_retained(self):
        result = self.joined()
        self.assertEqual(result['excluded_prefix_apis_outside_selected_identity_cohort'], [3])
        self.assertEqual(sum(row['begun'] for row in result['reads']), 96)
        self.assertEqual(result['reads'][0]['excluded_begun'], 6)
        self.assertEqual(result['reads'][0]['phase_symbols']['ready_to_bind']['<excluded>'], 6)
        self.assertEqual(result['reads'][1]['phase_symbols']['ready_to_bind']['<excluded>'], 4)

    def test_each_v2_singleton_and_range_duplicate_rejects(self):
        for prefix in ('prefix_limits ', 'prefix_health ', 'prefix_range '):
            line = next(line for line in v2().splitlines(keepends=True) if line.startswith(prefix))
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                parse(v2().replace(line, line + line))

    def test_excluded_duplicate_rejects_even_with_adjusted_totals(self):
        with self.assertRaises(ValueError):
            parse(v2().replace('excluded_rows=3', 'excluded_rows=4').replace(EXCLUDED[0], EXCLUDED[0]+'\n'+EXCLUDED[0]))

    def test_version_one_cannot_smuggle_v2_metadata_or_records(self):
        with self.assertRaises(ValueError):
            parse(v2().replace('version=2', 'version=1'))
        for record in [line for line in v2().splitlines() if line.startswith(('prefix_limits ', 'prefix_health ', 'prefix_range ', 'prefix_excluded '))]:
            with self.subTest(record=record.split()[0]), self.assertRaises(ValueError):
                parse(prefix_text().replace('prefix_end ', record+'\nprefix_end '))
        for fragment in ('excluded_rows=0 ',):
            with self.assertRaises(ValueError):
                parse(prefix_text().replace('prefix_meta ', 'prefix_meta '+fragment))

    def test_required_v2_records_and_header_footer_counts_are_binding(self):
        for prefix in ('prefix_limits ', 'prefix_health ', 'prefix_range '):
            with self.subTest(prefix=prefix), self.assertRaises(ValueError):
                parse('\n'.join(line for line in v2().splitlines() if not line.startswith(prefix)))
        for text in (v2().replace(' excluded_rows=3', '', 1),
                     v2().replace('prefix_end rows=13 excluded_rows=3', 'prefix_end rows=13'),
                     v2().replace('excluded_rows=3', 'excluded_rows=2', 1)):
            with self.subTest(text=text[-90:]), self.assertRaises(ValueError):
                parse(text)

    def test_all_health_overflow_and_allocation_underclaims_reject(self):
        for old, new in [('descriptor_overflow=0', 'descriptor_overflow=1'),
                         ('instruction_overflow=0', 'instruction_overflow=1'),
                         ('row_overflow=0', 'row_overflow=1'),
                         ('excluded_overflow=0', 'excluded_overflow=1'),
                         ('allocated_descriptors=1', 'allocated_descriptors=0'),
                         ('allocated_instructions=1', 'allocated_instructions=0'),
                         ('max_probe=1', 'max_probe=129'),
                         ('max_excluded_probe=1', 'max_excluded_probe=129')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse(v2().replace(old, new))

    def test_health_probe_cap_boundary_and_unemitted_allocations(self):
        parse(v2().replace('max_probe=1 ', 'max_probe=128 ').replace('max_excluded_probe=1', 'max_excluded_probe=128')
              .replace('allocated_descriptors=1', 'allocated_descriptors=2').replace('allocated_instructions=1', 'allocated_instructions=3'))

    def test_invalid_and_bad_records_fail_closed_even_if_count_zero(self):
        bad = 'prefix_bad index=0 reason=1 api=1 identity_seq=1 tb=1 segment_tb=1 first=1 last=1 rep=0 rep_base=0 actual_pc=84001000 expected_pc=84001000 type=0 segment_type=0'
        for record in ('prefix_invalid reason=1 count=0', 'prefix_invalid reason=1 count=1', bad):
            with self.subTest(record=record.split()[0]), self.assertRaises(ValueError):
                parse(v2().replace('prefix_end ', record+'\nprefix_end '))

    def test_admission_bounds_drain_and_closed_flag(self):
        for old, new in [('max_api=64', 'max_api=0'), ('admitted=3', 'admitted=65'),
                         ('returned=3', 'returned=2'), ('admission_closed=0', 'admission_closed=1'),
                         ('admission_closed=0', 'admission_closed=2')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                parse(v2().replace(old, new))
        parse(v2().replace('max_api=64', 'max_api=3').replace('admission_closed=0', 'admission_closed=1'))

    def test_owned_and_excluded_range_boundaries_are_half_open(self):
        for pc in ('84001000', '84001fff'):
            with self.subTest(pc=pc), self.assertRaises(ValueError):
                parse(v2().replace('pc=00100000', 'pc='+pc))
        for pc in ('84000fff', '84002000'):
            parse(v2().replace('pc=00100000', 'pc='+pc))
        with self.assertRaises(ValueError):
            parse(v2().replace('pc=84001000', 'pc=84002000'))

    def test_overlapping_reversed_and_duplicate_owned_ranges_reject(self):
        for record in ('prefix_range id=2 start=84001fff end=84003000',
                       'prefix_range id=1 start=84003000 end=84004000',
                       'prefix_range id=2 start=84004000 end=84003000'):
            with self.subTest(record=record), self.assertRaises(ValueError):
                parse(v2().replace('range_count=1', 'range_count=2').replace('prefix_health ', record+'\nprefix_health '))
        parse(v2().replace('range_count=1', 'range_count=2').replace('prefix_health ', 'prefix_range id=2 start=84002000 end=84003000\nprefix_health '))

    def test_excluded_full_capture_identity_references_must_resolve(self):
        for old, new in [('api=3 identity_seq=18 pc=00103000', 'api=999 identity_seq=18 pc=00103000'),
                         ('api=3 identity_seq=18 pc=00103000', 'api=3 identity_seq=99 pc=00103000'),
                         ('api=3 identity_seq=18 pc=00103000', 'api=3 identity_seq=6 pc=00103000')]:
            with self.subTest(new=new), self.assertRaises(ValueError):
                self.joined(v2().replace(old, new))

    def cli(self, capture=None, identity_log=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            files = {'prefix': v2() if capture is None else capture,
                     'identity': matching_identity() if identity_log is None else identity_log,
                     'symbol-map': json.dumps(SYMBOLS),
                     'receipts': '\n'.join(json.dumps(row) for row in [
                         {'Id':'synthetic-resume','Status':'completed','EndedUtc':'1970-01-01T00:00:00.000000000Z'},
                         {'Id':'synthetic-pause','Status':'completed','StartedUtc':'1970-01-01T00:00:00.000017000Z'}])}
            command = [sys.executable, str(Path(__file__).with_name('join_prefix.py')), '--identity-tools', str(IDENTITY_TOOLS), '--output', str(root/'output.json')]
            for name, text in files.items():
                path = root/name
                path.write_text(text)
                command.extend(['--'+name, str(path)])
            result = subprocess.run(command, text=True, capture_output=True)
            output = json.loads((root/'output.json').read_text()) if result.returncode == 0 else None
            return result, output

    def test_cli_admission_count_and_handle_match_identity(self):
        result, output = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output['selected_reads'], 2)
        self.assertEqual(sum(row['excluded_begun'] for row in output['reads']), 10)
        for text in (v2().replace('admitted=3 returned=3', 'admitted=4 returned=4'),
                     v2().replace('handle=0000042c', 'handle=00000430')):
            result, output = self.cli(capture=text)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Identity admission differs from prefix limits', result.stderr)
            self.assertIsNone(output)

    def test_cli_off_receipt_admission_handle_is_not_ignored(self):
        lines = matching_identity().splitlines()
        changed = '\n'.join(line.replace('value0=0000042c', 'value0=00000430')
            if ' kind=1 ' in line and ' api=3 ' in line else line for line in lines)+'\n'
        result, output = self.cli(identity_log=changed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Identity admission differs from prefix limits', result.stderr)
        self.assertIsNone(output)


if __name__ == '__main__':
    unittest.main()
