# SPDX-License-Identifier: GPL-2.0-only
import unittest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/storage_allocation_diagnostic'))

from operation_boundaries import Boundaries


def begin(index=0, **values):
    return dict(kind="issue",index=index,thread=0x80003000,esp=0x80008000,
                length=4096,offset=index*4096,**values)


def end(index=0, **values):
    return dict(kind="consumer",index=index,thread=0x80003000,esp=0x80008000,
                status=0,io_status=0,information=4096,verification_mask=0,**values)


class BoundaryTests(unittest.TestCase):
    def test_complete_only_after_all_actual_paired_boundaries(self):
        tracker=Boundaries(2)
        tracker.observe(begin(0));tracker.observe(end(0))
        self.assertFalse(tracker.complete)
        tracker.observe(begin(1));tracker.observe(end(1))
        self.assertTrue(tracker.complete)

    def test_missing_duplicate_and_out_of_order_boundaries_reject(self):
        for events in ([end()], [begin(),begin()], [begin(1)]):
            tracker=Boundaries(2)
            with self.assertRaises(ValueError):
                for event in events:tracker.observe(event)

    def test_wrong_thread_or_stack_cannot_be_consumer(self):
        for field in ("thread","esp"):
            tracker=Boundaries(1);tracker.observe(begin());event=end();event[field]+=4
            with self.assertRaises(ValueError):tracker.observe(event)
            self.assertFalse(tracker.complete)

    def test_missing_bad_or_boolean_verification_is_not_success(self):
        for field in ("status","io_status","information","verification_mask"):
            for value in (None,True,1):
                tracker=Boundaries(1);tracker.observe(begin());event=end();event[field]=value
                with self.assertRaises(ValueError):tracker.observe(event)
                self.assertFalse(tracker.complete)

    def test_wrong_length_offset_or_boolean_index_reject(self):
        for field,value in (("length",2048),("offset",4096),("index",False)):
            tracker=Boundaries(1);event=begin();event[field]=value
            with self.assertRaises(ValueError):tracker.observe(event)


if __name__=="__main__":unittest.main()
