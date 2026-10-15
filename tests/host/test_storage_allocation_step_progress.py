# SPDX-License-Identifier: GPL-2.0-only
"""Invented stop streams reproduce collector control, with no native endpoint."""
import json
import struct
import unittest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/storage_allocation_diagnostic'))

import test_storage_allocation_capture as base

InventedRsp = base.InventedRsp
KERNEL = base.KERNEL


class PoolStops(InventedRsp):
    repeated_steps = 1
    reply = 'T05'
    changed_register = False

    def __init__(self, *args):
        super().__init__(*args)
        self.repeats = 0

    def run(self, command):
        if self.phase == 'stepped' and self.after_step == 'issue' and self.index == 0:
            assert command == 'c'
            self.phase = 'allocate'
        elif self.phase == 'free' and command == 's' and self.repeats < self.repeated_steps:
            assert KERNEL['sites'][1]['address'] not in self.breakpoints
            self.repeats += 1
            return self.reply
        elif self.phase in ('allocate', 'allocate-return', 'free', 'free-return'):
            assert command == 's'
            self.phase += '-stepped'
        elif self.phase.endswith('-stepped'):
            assert command == 'c'
            self.phase = {'allocate-stepped': 'allocate-return',
                          'allocate-return-stepped': 'free',
                          'free-stepped': 'free-return',
                          'free-return-stepped': 'consumer'}[self.phase]
        else:
            return super().run(command)
        return 'S05'

    def regs(self):
        pcs = {'allocate': KERNEL['sites'][0]['address'],
               'allocate-stepped': KERNEL['sites'][0]['address'] + 1,
               'allocate-return': 0x84001004, 'allocate-return-stepped': 0x84001005,
               'free': KERNEL['sites'][1]['address'],
               'free-stepped': KERNEL['sites'][1]['address'] + 1,
               'free-return': 0x84001008, 'free-return-stepped': 0x84001009}
        if self.phase not in pcs:
            return super().regs()
        esp = 0x80007000 + (16 if self.phase.startswith('allocate-return') else
                            12 if self.phase.startswith('free-return') else 0)
        return [0x90008000 if self.phase.startswith('allocate-return') else
                int(self.changed_register and self.phase == 'free' and self.repeats > 0),
                0, 0, 0, esp, 0x80007100, 0, 0, pcs[self.phase]]

    def read(self, address, size):
        if address == 0x80007000:
            values = [0x84001004, 0, 872, 7] if self.phase == 'allocate' else [0x84001008, 0x90008000, 7]
            return struct.pack('<' + 'I' * len(values), *values)
        if address == 0x80007100:
            return struct.pack('<II', 0, 0x84001000)
        return super().read(address, size)


class StepProgressTests(unittest.TestCase):
    run_case = base.CaptureTests.run_case
    def test_unchanged_step_at_free_entry_is_not_a_second_call(self):
        for reply in ('T05', 'S02'):
            cls = type('Repeated', (PoolStops,), {'reply': reply})
            code, report, _ = self.run_case(cls)
            self.assertEqual(code, 0, report)
            self.assertEqual(report['observed']['successful_allocations'], 1)
            self.assertEqual(report['observed']['completed_frees'], 1)
            self.assertEqual(report['owned_boundaries']['operations'], 1024)
            self.assertEqual(report['integrity'], 'complete')
            self.assertFalse(report['native_qualified'])
            self.assertIsNone(report['physical_storage_peak_bytes'])
            entries = [x for x in self.last_events if x['kind'] == 'entry']
            self.assertEqual([x['call'] for x in entries], ['allocate', 'free'])
            repeats = [x for x in self.last_control if x['same_stop_identity']]
            self.assertEqual(len(repeats), 1)
            self.assertEqual(repeats[0]['reply'], reply)
            self.assertEqual(repeats[0]['before_registers'], repeats[0]['after_registers'])
            self.assertTrue(repeats[0]['observed_register_context_unchanged'])

    def test_bounded_nonprogress_retains_partial_unknown_without_duplicate_call(self):
        class Stalled(PoolStops):
            repeated_steps = 100
        code, report, _ = self.run_case(Stalled)
        self.assertEqual(code, 1)
        self.assertEqual(report['integrity'], 'unknown')
        self.assertIn('single-step made no progress', report['owned_boundaries']['error'])
        self.assertNotIn('ambiguous-return-identity', [x['code'] for x in report['issues']])
        self.assertEqual(report['observed']['completed_frees'], 0)
        self.assertIsNone(report['physical_storage_peak_bytes'])
        self.assertEqual(len([x for x in self.last_control if x['same_stop_identity']]), 8)
        self.assertEqual(len([x for x in self.last_events if x['kind'] == 'entry']), 2)

    def test_same_entry_pc_thread_and_esp_with_changed_eax_is_not_replayed(self):
        class Changed(PoolStops):
            changed_register = True
        code, report, _ = self.run_case(Changed)
        self.assertEqual(code, 0, report)
        self.assertEqual(report['observed']['completed_frees'], 1)
        repeats = [x for x in self.last_control if x['same_stop_identity']]
        self.assertEqual(len(repeats), 1)
        self.assertFalse(repeats[0]['observed_register_context_unchanged'])

    def test_real_second_free_after_a_normal_return_is_retained_as_unknown(self):
        class SecondFree(PoolStops):
            repeated_steps = 0
            visits = 0

            def run(self, command):
                if self.phase == 'free-return-stepped' and self.visits == 0:
                    assert command == 'c'
                    self.visits += 1
                    self.phase = 'free'
                    return 'S05'
                return super().run(command)

        code, report, _ = self.run_case(SecondFree)
        self.assertEqual(code, 0)
        self.assertEqual(report['owned_boundaries']['operations'], 1024)
        self.assertEqual(report['integrity'], 'unknown')
        self.assertEqual(len([x for x in self.last_events if x['kind'] == 'entry' and x['call'] == 'free']), 2)
        self.assertIn('free-without-live-allocation', [x['code'] for x in report['issues']])


if __name__ == '__main__':
    unittest.main()
