# SPDX-License-Identifier: MIT
import unittest
from join_prefix import classify

class JoinTests(unittest.TestCase):
    def test_boundary_instruction_belongs_to_new_phase(self):
        expected = {1:'entry_to_ready', 2:'entry_to_ready', 3:'ready_to_bind',
                    4:'ready_to_bind', 5:'bind_to_start', 6:'bind_to_start',
                    7:'start_to_return', 8:'start_to_return'}
        for seq, phase in expected.items():
            self.assertEqual(classify(seq, 1, 3, 5, 7, 9), phase)

    def test_queued_start_after_return_not_in_current_call(self):
        self.assertEqual(classify(8, 1, 3, 5, 11, 9), 'bind_to_return')

    def test_invalid_or_outside_interval_rejected(self):
        for args in [(0,1,3,5,7,9),(9,1,3,5,7,9),(4,1,5,3,7,9),(6,1,3,5,4,9)]:
            with self.subTest(args=args), self.assertRaises(ValueError): classify(*args)

if __name__ == '__main__': unittest.main()
