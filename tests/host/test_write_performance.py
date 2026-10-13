import unittest
from tools.write_performance import CASES, parse


def valid():
    lines = ['== write-performance begin ==', 'TAP version 14', '1..81',
             '# WRITE-META version=1 frequency=3579545 repeats=9 cases=9']
    n = 0
    for case, size in CASES.items():
        for i in range(9):
            n += 1
            lines += [f'# WRITE case={case} sample={i} ticks=123 bytes={size} correct=1',
                      f'ok {n} - {case}/{i}']
    return '\n'.join(lines + ['# WRITE-SUMMARY samples=81 failures=0', '== write-performance end PASS =='])


class TestWritePerformance(unittest.TestCase):
    def test_complete_valid_log(self):
        self.assertEqual(len(parse(valid())['samples']), 81)

    def test_reject_corruption(self):
        for old, new in [('correct=1', 'correct=0'), ('bytes=65536', 'bytes=65535'),
                         ('ticks=123', 'ticks=0'), ('sample=0', 'sample=1'),
                         ('ok 1 -', 'not ok 1 -'), ('frequency=3579545', 'frequency=0'),
                         ('failures=0', 'failures=1'), ('end PASS', 'end FAIL')]:
            with self.subTest(old=old), self.assertRaises(ValueError):
                parse(valid().replace(old, new, 1))

    def test_reject_truncated_duplicate_and_junk_records(self):
        for text in [valid().rsplit('\n', 1)[0], valid() + '\n' + valid(),
                     valid() + '\n# WRITE case=bad', valid().replace('ok 2 -', 'ok 1 -', 1)]:
            with self.assertRaises(ValueError):
                parse(text)
