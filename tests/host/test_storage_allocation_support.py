# SPDX-License-Identifier: GPL-2.0-only
"""Host-only transport, import and numeric binding controls."""
import hashlib
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2] / 'tools/storage_allocation_diagnostic'
sys.path.insert(0, str(TOOLS))
from support import load_transport, caller_frames
from rsp_transport import Rsp
from prepare_kernel_binding import prepare
from prepare_fixture_binding import bind


class SupportTests(unittest.TestCase):
    def test_transport_loads_exact_hash_and_rejects_wrong_hash_before_import(self):
        path = TOOLS / 'rsp_transport.py'
        loaded = load_transport(path, hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(loaded.__name__, 'Rsp')
        with self.assertRaisesRegex(ValueError, 'transport source hash mismatch'):
            load_transport(path, '0' * 64)

    def test_step_preserves_raw_trap_reply_and_rejects_nonstop(self):
        rsp = object.__new__(Rsp)
        commands = []
        rsp.send = commands.append
        rsp.reply = lambda: 'T05thread:01;'
        self.assertEqual(rsp.run('s'), 'T05thread:01;')
        self.assertTrue(rsp.stopped)
        self.assertEqual(commands, ['s'])
        rsp.reply = lambda: 'E01'
        with self.assertRaisesRegex(ValueError, 'unexpected stop'):
            rsp.run('s')
        rsp.reply = lambda: 'W00'
        with self.assertRaises(EOFError):
            rsp.run('s')

    def test_memory_read_rejects_partial_reply_and_invalid_pointer(self):
        rsp = object.__new__(Rsp)
        commands = []
        rsp.packet = lambda command: commands.append(command) or 'aabb'
        self.assertEqual(rsp.read(0x2000, 2), b'\xaa\xbb')
        with self.assertRaisesRegex(ValueError, 'unreadable pointer'):
            rsp.read(0x2000, 4)
        with self.assertRaisesRegex(ValueError, 'bounded valid pointer'):
            rsp.read(0, 4)
        self.assertEqual(commands, ['m2000,2', 'm2000,4'])

    def test_breakpoint_bookkeeping_requires_actual_ok(self):
        rsp = object.__new__(Rsp)
        rsp.breakpoints = set()
        commands = []
        rsp.packet = lambda command: commands.append(command) or 'OK'
        rsp.bp(0x1234)
        rsp.bp(0x1234, False)
        self.assertEqual(commands, ['Z0,1234,1', 'z0,1234,1'])
        self.assertEqual(rsp.breakpoints, set())
        rsp.packet = lambda command: 'E01'
        with self.assertRaises(ValueError):
            rsp.bp(0x5678)
        self.assertEqual(rsp.breakpoints, set())

    def test_incomplete_caller_frames_remain_explicit(self):
        class Memory:
            def read(self, address, size):
                return struct.pack('<II', 0, 0x84001000)
        result = caller_frames(Memory(), 0x80008020, 0x80008000)
        self.assertFalse(result['complete'])
        self.assertEqual(result['termination'], 'zero-frame-link')
        self.assertEqual(result['frames'][0]['caller_pc'], 0x84001000)

    def test_binding_generators_reject_unselected_images(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / 'wrong.bin'
            p.write_bytes(b'Invented host fixture')
            with self.assertRaisesRegex(ValueError, 'selected reference kernel hash mismatch'):
                prepare(p, p, TOOLS / 'rsp_transport.py')
            with self.assertRaisesRegex(ValueError, 'exact owned selected XBE required'):
                bind(p, p)


if __name__ == '__main__':
    unittest.main()
