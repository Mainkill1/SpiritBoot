# SPDX-License-Identifier: MIT
import unittest
from analyze_prefix import parse, counts_by_api
from test_prefix import CAPTURE

V2 = CAPTURE.replace('version=1', 'version=2').replace('prefix_meta version=2 ', 'prefix_meta version=2 excluded_rows=1 ').replace('prefix_end rows=2', '''prefix_limits handle=0000042c max_api=64 admitted=1 returned=1 admission_closed=0 range_count=1
prefix_range id=1 start=84001000 end=84002000
prefix_health allocated_descriptors=1 allocated_instructions=3 descriptor_overflow=0 instruction_overflow=0 row_overflow=0 excluded_overflow=0 max_probe=1 max_excluded_probe=1
prefix_excluded api=1 identity_seq=2 pc=00100000 first=2 last=4 executions=2 begun=6 rep_iterations=0
prefix_end rows=2 excluded_rows=1''')

class VersionTwoTests(unittest.TestCase):
    def test_explicit_excluded_counts_are_not_owned_symbols(self):
        parsed = parse(V2)
        counted = counts_by_api(parsed, {'instruction_owners': {'84001000':'function'}})[1]
        self.assertEqual(counted['begun'], 11)
        self.assertEqual(counted['excluded_begun'], 6)
        self.assertEqual(counted['symbols']['<excluded>'], 6)
        self.assertEqual(counted['symbols']['function'], 2)

    def test_all_exhaustion_and_invalid_records_reject(self):
        for field in ['descriptor_overflow','instruction_overflow','row_overflow','excluded_overflow']:
            with self.subTest(field=field), self.assertRaises(ValueError):
                parse(V2.replace(field+'=0',field+'=1'))
        with self.assertRaises(ValueError): parse(V2.replace('prefix_end','prefix_invalid reason=1 count=1\nprefix_end'))

    def test_excluded_pc_in_owned_range_is_invalid(self):
        with self.assertRaises(ValueError): parse(V2.replace('pc=00100000','pc=84001000'))

    def test_limit_drain_and_bounds_reject(self):
        for old,new in [('returned=1','returned=0'),('max_api=64','max_api=0'),
                        ('admission_closed=0','admission_closed=1'),('range_count=1','range_count=2')]:
            with self.subTest(new=new), self.assertRaises(ValueError): parse(V2.replace(old,new))

    def test_excluded_count_and_duplicates_reject(self):
        with self.assertRaises(ValueError): parse(V2.replace('begun=6','begun=7'))
        row='prefix_excluded api=1 identity_seq=2 pc=00100000 first=2 last=4 executions=2 begun=6 rep_iterations=0\n'
        with self.assertRaises(ValueError): parse(V2.replace(row,row+row))

    def test_required_v2_health_cannot_be_silently_missing(self):
        with self.assertRaises(ValueError): parse('\n'.join(l for l in V2.splitlines() if not l.startswith('prefix_health')))

if __name__=='__main__': unittest.main()
