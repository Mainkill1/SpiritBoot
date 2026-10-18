# SPDX-License-Identifier: MIT
import unittest
import json
import tempfile
from pathlib import Path
import analyze_completion_order as order


def row(**kw):
    r=dict(iosb='00001000',begin=10,thread='00002000',bytes=512,offset='00000000',caller='0026741a',done=20,status='00000000',info=512,complete_count=1,returned=30,result='00000103',dispatch=40,callback=50,error='00000000',callback_bytes=512)
    r.update(kw);return r


class CompletionOrderTests(unittest.TestCase):
    def test_pending_does_not_determine_order(self):
        self.assertEqual(order.classify(row()),'before_return')
        self.assertEqual(order.classify(row(done=35)),'after_return')
        self.assertEqual(order.classify(row(done=30)),'same_timestamp')

    def test_reject_ambiguous_lifecycle(self):
        for r in [row(complete_count=2),row(callback_bytes=1),row(done=5),row(returned=60),row(caller='00000000')]:
            with self.subTest(row=r),self.assertRaises(ValueError):order.validate([r])

    def test_validate_successful_join(self):order.validate([row()])

    def test_warmup_is_excluded_before_lifecycle_validation(self):
        with tempfile.TemporaryDirectory()as directory:
            p=Path(directory)
            (p/'rows.json').write_text(json.dumps([row(callback_bytes=763),row(begin=110,done=120,returned=130,dispatch=140,callback=150)]))
            receipts=[{'Id':'test-resume','Status':'completed','EndedUtc':'1970-01-01T00:00:00.000000100Z'},
                      {'Id':'test-pause','Status':'completed','StartedUtc':'1970-01-01T00:00:00.000000200Z'}]
            (p/'receipts.jsonl').write_text('\n'.join(json.dumps(r)for r in receipts))
            result=order.run(p/'rows.json',p/'receipts.jsonl')
            self.assertEqual(result['selected']['calls'],1)
            self.assertEqual(result['excluded_rows'],1)



if __name__=='__main__':unittest.main()
