# SPDX-License-Identifier: MIT
import unittest
from analyze_prefix import parse

CAPTURE = '''prefix_meta version=1 descriptors=1 rows=2 translations=1 overflow=0 reentry=0 thread_mismatch=0 invalid_prefix=0 open_api=0
prefix_tb id=1 pc=84001000 count=3 generation=1 born_api=1 born_identity_seq=1
prefix_insn tb=1 ordinal=1 pc=84001000 rep=0
prefix_insn tb=1 ordinal=2 pc=84001002 rep=0
prefix_insn tb=1 ordinal=3 pc=84001004 rep=1
prefix_row api=1 identity_seq=1 tb=1 first=1 last=2 executions=2 begun=4 rep_iterations=0
prefix_row api=1 identity_seq=2 tb=1 first=3 last=3 executions=1 begun=1 rep_iterations=7
prefix_translation api=1 identity_seq=1 tb=1
prefix_end rows=2
'''

class PrefixTests(unittest.TestCase):
    def test_partial_prefix_and_rep_have_distinct_counts(self):
        result = parse(CAPTURE)
        self.assertEqual(len(result['rows']), 2)
        self.assertEqual(sum(r['begun'] for r in result['rows']), 5)
        self.assertEqual(sum(r['rep_iterations'] for r in result['rows']), 7)

    def test_dropped_footer(self):
        with self.assertRaises(ValueError): parse(CAPTURE.rsplit('prefix_end', 1)[0])

    def test_fault_counters_reject(self):
        for name in ('overflow', 'reentry', 'thread_mismatch', 'invalid_prefix', 'open_api'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                parse(CAPTURE.replace(name+'=0', name+'=1'))

    def test_count_formula_is_checked(self):
        with self.assertRaises(ValueError): parse(CAPTURE.replace('begun=4', 'begun=5'))

    def test_descriptor_ordinals_must_be_complete(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('prefix_insn tb=1 ordinal=2 pc=84001002 rep=0\n', ''))

    def test_row_cannot_escape_descriptor(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('first=3 last=3', 'first=4 last=4'))

    def test_unknown_and_duplicate_fields_reject(self):
        for change in ('odd=1 ', 'api=2 '):
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse(CAPTURE.replace('prefix_row api=1', 'prefix_row '+change+'api=1', 1))

    def test_duplicate_histogram_keys_reject(self):
        row = 'prefix_row api=1 identity_seq=1 tb=1 first=1 last=2 executions=2 begun=4 rep_iterations=0\n'
        with self.assertRaises(ValueError): parse(CAPTURE.replace(row, row+row))

    def test_optional_rep_is_unknown_not_zero(self):
        result = parse(CAPTURE.replace(' rep_iterations=7', ''))
        self.assertEqual(len(result['rows']), 2)
        self.assertNotIn('rep_iterations', result['rows'][1])

    def test_translation_reference_must_exist(self):
        with self.assertRaises(ValueError):
            parse(CAPTURE.replace('prefix_translation api=1 identity_seq=1 tb=1',
                                  'prefix_translation api=1 identity_seq=1 tb=2'))

    def test_counters_cannot_be_negative_or_zero_executions(self):
        for old, new in [('executions=2', 'executions=0'), ('rep_iterations=7', 'rep_iterations=-1')]:
            with self.subTest(new=new), self.assertRaises(ValueError): parse(CAPTURE.replace(old, new))

if __name__ == '__main__': unittest.main()
