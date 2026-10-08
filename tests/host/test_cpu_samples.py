"""Period-weighted CPU samples must not become call counts or kernel time."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2] / 'tools' / 'kernel_cpu_samples.py'


class CommandTests(unittest.TestCase):
    def test_malformed_samples_are_rejected_without_publishing_a_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'samples').write_text('not a perf leaf sample\n')
            (root / 'kernel').write_bytes(b'')
            result = subprocess.run([sys.executable, str(PATH), '--samples', str(root / 'samples'),
                                     '--kernel', str(root / 'kernel'), '--pid', '7',
                                     '--output', str(root / 'report')], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('malformed sample', result.stderr)
            self.assertFalse((root / 'report').exists())


class AttributionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('tools.kernel_cpu_samples', PATH)
        cls.cpu = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.cpu)

    def rows(self, lines):
        return self.cpu.parse_samples(lines.splitlines(), 7)

    def sample(self, period=100, symbol='guest-0x84001001', dso='/tmp/perf-7.map',
               timestamp='1.000000001', pid=7):
        return f'xemu {pid}/9 {timestamp}: {period} 7f0000 {symbol} ({dso})'

    def symbols(self):
        return [dict(start=0x84001000, end=0x84001010, section='.text', symbols=['First', 'Alias']),
                dict(start=0x84001010, end=0x84001020, section='.text', symbols=['Second'])]

    def test_period_weights_not_equal_sample_counts_determine_shares(self):
        rows = self.rows(self.sample(period=900) + '\n' +
                         self.sample(period=100, symbol='helper', dso='/bin/xemu'))
        result = self.cpu.rank_samples(rows, self.symbols())
        self.assertEqual(result['weighted_period'], 1000)
        self.assertEqual(result['categories']['kernel_jit']['share_pct'], 90)
        self.assertEqual(result['kernel'][0]['period'], 900)

    def test_unknown_library_symbols_still_belong_to_the_library(self):
        result = self.cpu.rank_samples(self.rows(self.sample(symbol='[unknown]',
                                       dso='/usr/lib/libsamplerate.so')), self.symbols())
        self.assertEqual(result['categories']['host_library']['share_pct'], 100)
        self.assertEqual(result['modules'][0]['name'], '/usr/lib/libsamplerate.so')

    def test_recorded_executable_path_supports_renames_without_matching_another_dso(self):
        rows = self.rows(self.sample(symbol='helper', dso='/build/qemu-system-i386') + '\n' +
                         self.sample(symbol='helper', dso='/other/qemu-system-i386'))
        result = self.cpu.rank_samples(rows, self.symbols(),
                                       host_executable='/build/qemu-system-i386')
        self.assertEqual(result['categories']['xemu_host']['share_pct'], 50)
        self.assertEqual(result['categories']['host_library']['share_pct'], 50)
        self.assertEqual(result['host_executable'], '/build/qemu-system-i386')

    def test_demangled_symbol_parentheses_do_not_consume_the_module_field(self):
        symbol = 'helper(int) (anonymous namespace)::foo()'
        rows = self.rows(self.sample(symbol=symbol, dso='/build/xemu'))
        self.assertEqual(rows[0]['symbol'], symbol)
        self.assertEqual(rows[0]['dso'], '/build/xemu')
        result = self.cpu.rank_samples(rows, self.symbols(), host_executable='/build/xemu')
        self.assertEqual(result['categories']['xemu_host']['share_pct'], 100)

    def test_host_symbol_offset_cannot_change_guest_instruction_identity(self):
        rows = self.rows(self.sample() + '\n' + self.sample(symbol='guest-0x84001000+0x11'))
        result = self.cpu.rank_samples(rows, self.symbols())
        self.assertEqual([tuple(x['symbols']) for x in result['kernel']],
                         [('First', 'Alias')])
        self.assertEqual(result['kernel'][0]['period'], 200)

    def test_outside_image_and_unresolved_guest_map_are_not_kernel(self):
        rows = self.rows(self.sample(symbol='guest-0x84001020') + '\n' +
                         self.sample(symbol='[unknown]'))
        result = self.cpu.rank_samples(rows, self.symbols())
        self.assertEqual(result['kernel'], [])
        self.assertEqual(result['categories']['other_guest_jit']['share_pct'], 50)
        self.assertEqual(result['categories']['unresolved_guest_jit']['share_pct'], 50)

    def test_phase_window_retains_exact_nanoseconds_and_excluded_counts(self):
        rows = self.rows(self.sample(timestamp='1.000000001', period=900) + '\n' +
                         self.sample(timestamp='1.000000002', period=100))
        result = self.cpu.rank_samples(rows, self.symbols(), 1000000002, 1000000003)
        self.assertEqual(result['samples'], 1)
        self.assertEqual(result['excluded_samples'], 1)
        self.assertEqual(result['weighted_period'], 100)
        self.assertEqual(rows[0]['time_ns'], 1000000001)

    def test_equal_inclusive_bounds_can_select_one_timestamp(self):
        rows = self.rows(self.sample())
        result = self.cpu.rank_samples(rows, self.symbols(), 1000000001, 1000000001)
        self.assertEqual(result['samples'], 1)
        self.assertEqual(result['weighted_period'], 100)

    def test_mixed_process_stale_map_and_guest_overflow_are_rejected(self):
        for line in (self.sample(pid=8), self.sample(dso='/tmp/perf-8.map'),
                     self.sample(symbol='guest-0x100000000')):
            with self.subTest(line=line), self.assertRaises(ValueError):
                self.rows(line)

    def test_malformed_zero_period_and_sample_budget_are_rejected(self):
        for line in ('bad', self.sample(period=0), self.sample(timestamp='nan'),
                     self.sample(timestamp='1.0000000001'), self.sample(symbol=''),
                     self.sample(dso=''), self.sample(symbol='  '), self.sample(dso='  ')):
            with self.subTest(line=line), self.assertRaises(ValueError):
                self.rows(line)
        with self.assertRaises(ValueError):
            self.cpu.parse_samples([self.sample(), self.sample()], 7, max_samples=1)

    def test_empty_or_reversed_windows_cannot_publish_zero_cost(self):
        rows = self.rows(self.sample())
        for start, end in ((2, 1), (2000000000, 3000000000)):
            with self.subTest(start=start), self.assertRaises(ValueError):
                self.cpu.rank_samples(rows, self.symbols(), start, end)
        with self.assertRaises(ValueError):
            self.cpu.parse_samples([], 7)

    def test_large_periods_remain_exact_and_unknown_ips_stay_visible(self):
        result = self.cpu.rank_samples(self.rows(self.sample(period=2**54 + 1,
                                       symbol='[unknown]', dso='[unknown]')), self.symbols())
        self.assertEqual(result['weighted_period'], 2**54 + 1)
        self.assertEqual(result['categories']['unresolved']['samples'], 1)


if __name__ == '__main__':
    unittest.main()
