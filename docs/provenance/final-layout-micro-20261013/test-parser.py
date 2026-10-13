import unittest,zipfile
from pathlib import Path
from micro_parser import parse_micro
with zipfile.ZipFile(Path(__file__).parent/'receipts.zip') as z:
    sample=z.read(next(n for n in z.namelist() if n.endswith('/serial.log'))).decode()
class ParserTests(unittest.TestCase):
    def test_valid_complete_fixture(self):self.assertEqual(len(parse_micro(sample)),40)
    def test_reject_corrupt_truncated_duplicate_or_extra_records(self):
        for log in [sample.replace('correct=1','correct=0',1),sample.replace('iterations=1000','iterations=999',1),sample.replace('checksum=811c9dc5','checksum=00000000',1),sample.replace('sample=0','sample=1',1),sample.replace('ticks=','bad_ticks=',1),sample.replace('ok 2 -','not ok 2 -',1),sample.rsplit('\n',2)[0],sample+sample,sample.replace('# PERF-SUMMARY','# PERF surplus\n# PERF-SUMMARY',1)]:
            with self.subTest(log=log[:30]),self.assertRaises(ValueError):parse_micro(log)
if __name__=='__main__':unittest.main()
