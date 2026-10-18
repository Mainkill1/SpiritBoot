# SPDX-License-Identifier: MIT
import struct
import unittest
from read_spirit_medium import Snapshot, extract

class SnapshotTests(unittest.TestCase):
    def test_unmapped_page_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unmapped'):
            Snapshot(bytes(16384), 0).physical(0)

    def test_small_page_crossing(self):
        data = bytearray(16384)
        struct.pack_into('<I', data, 0, 0x1001)
        struct.pack_into('<II', data, 0x1000, 0x2001, 0x3001)
        data[0x2fff:0x3003] = b'\x78\x56\x34\x12'
        self.assertEqual(Snapshot(data, 0).scalar(0xfff), 0x12345678)

    def test_large_page_out_of_snapshot(self):
        data = bytearray(16384)
        struct.pack_into('<I', data, 0, 0x400081)
        with self.assertRaisesRegex(ValueError, 'outside snapshot'):
            Snapshot(data, 0).physical(0)

    def test_name_bound_and_scalar_size(self):
        data = bytearray(16384)
        struct.pack_into('<I', data, 0, 0x81)
        struct.pack_into('<HHI', data, 0x100, 130, 130, 0x200)
        memory = Snapshot(data, 0)
        with self.assertRaisesRegex(ValueError, 'oversized'):
            memory.name(0x100)
        with self.assertRaisesRegex(ValueError, 'scalar'):
            memory.scalar(0x100, 8)

    def test_unknown_snapshot_rejected(self):
        with self.assertRaisesRegex(ValueError, 'recorded'):
            extract(bytes(1024))

if __name__ == '__main__':
    unittest.main()
