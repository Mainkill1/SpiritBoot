"""Reject incomplete observations and distinguish clears from overwritten pages."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[2] / 'tools' / 'dashboard_memory.py'
spec = importlib.util.spec_from_file_location('dashboard_memory', PATH)
memory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(memory)


class MemoryObservationTests(unittest.TestCase):
    def test_page_outcomes(self):
        seed = memory.marker_page(0x400000)
        self.assertEqual(memory.classify(seed, seed), 'retained')
        self.assertEqual(memory.classify(bytes(4096), seed), 'zero')
        altered = bytearray(seed)
        altered[8:12] = bytes(4)
        self.assertEqual(memory.classify(bytes(altered), seed), 'mixed')
        self.assertEqual(memory.classify(b'\xff' * 4096, seed), 'replaced')

    def test_distinct_pages_and_no_zero_marker_words(self):
        self.assertNotEqual(memory.marker_page(0), memory.marker_page(0x1000000))
        self.assertNotEqual(memory.marker_page(0x400000), memory.marker_page(0x401000))
        seed = memory.marker_page(0)
        self.assertTrue(all(seed[i:i+4] != bytes(4) for i in range(0,4096,4)))

    def test_invalid_marker_and_page_lengths(self):
        for address in (-4096, 1, 0x10000000):
            with self.subTest(address=address), self.assertRaises(ValueError):
                memory.marker_page(address)
        with self.assertRaises(ValueError):
            memory.classify(bytes(4095), bytes(4096))

    def test_capture_sizes_and_ranges(self):
        with self.assertRaises(ValueError):
            memory.summarize(bytes(4096))
        capture = bytes(64 * 1024 * 1024)
        with self.assertRaises(ValueError):
            memory.summarize(capture, before=bytes(4096))
        for ranges in ([(1,4096)], [(0,0)], [(0,8192),(4096,4096)],
                       [(len(capture),4096)]):
            with self.subTest(ranges=ranges), self.assertRaises(ValueError):
                memory.summarize(capture, ranges=ranges)
        result = memory.summarize(capture, ranges=[(0x400000,8192)])
        self.assertEqual(result['ranges'][0]['page_classes'], {'zero':2})


if __name__ == '__main__':
    unittest.main()
