# SPDX-License-Identifier: GPL-2.0-only
"""Static owned runner-recipe checks; no native endpoint or PowerShell run."""
import importlib.util
import unittest
from pathlib import Path

BUILDER = Path(__file__).resolve().parents[1] / 'xbe/storage-perf/make-windows-allocation-guard-command.py'


class WindowsCommandTests(unittest.TestCase):
    def make(self, expected, stage='before-gdb'):
        if not BUILDER.exists():
            self.fail('The reproducible owned guard recipe builder is missing.')
        spec = importlib.util.spec_from_file_location('allocation_recipe', BUILDER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.make_recipe(expected, stage)

    def expected(self):
        names = ['allocation_ledger.py', 'support.py', 'capture_owned_fixture.py',
                 'operation_boundaries.py', 'rsp_transport.py', 'selected-binding.json',
                 'fixture-binding.json', 'dvd-route-windows-guard.ps1', 'windows-allocation-guard.ps1']
        return dict(expected_config_sha256='1'*64, expected_flash_sha256='2'*64,
                    expected_iso_sha256='3'*64, expected_job='pr248-native-test-fixture',
                    expected_launcher_sha256='4'*64,
                    expected_package=r'C:\owned\Queue\Testing\agent-pr248-native-test-fixture',
                    expected_xemu_sha256='5'*64, gdb_port=58931, kernel_sha256='6'*64,
                    python_executable=r'C:\Program Files\Python312\python.exe',
                    source_pins={name:'7'*64 for name in names})

    def test_recipe_hashes_before_dot_source_and_keeps_actual_owned_context(self):
        recipe = self.make(self.expected())
        self.assertEqual(recipe['type'], 'external')
        self.assertEqual(recipe['id'], 'allocation-before-gdb-guard')
        self.assertEqual(recipe['toolArguments'][:3], ['-NoProfile', '-NonInteractive', '-Command'])
        command = recipe['toolArguments'][3]
        self.assertLess(command.index('Frozen allocation guard source differs'), command.index('Invoke-Pr248AllocationGuard'))
        self.assertIn("wrapper_pid=[int]'{pid}';package='{packageDir}';result='{resultDir}'", command)
        self.assertIn("python_executable='C:\\Program Files\\Python312\\python.exe'", command)
        self.assertFalse(recipe['resumeDuring'])
        self.assertNotIn('Start-Process', command)

    def test_missing_python_or_source_pin_does_not_emit_recipe(self):
        for field in ('python_executable', 'source_pins'):
            expected = self.expected(); del expected[field]
            with self.assertRaises(ValueError): self.make(expected)
        expected = self.expected(); del expected['source_pins']['support.py']
        with self.assertRaises(ValueError): self.make(expected)

    def test_wrong_package_job_and_placeholder_expectations_reject(self):
        for field, value in [('expected_package', r'C:\owned\other-job'),
                             ('python_executable', 'python.exe'),
                             ('expected_xemu_sha256', '{hash}'),
                             ('gdb_port', True)]:
            expected = self.expected(); expected[field] = value
            with self.assertRaises(ValueError): self.make(expected)
        with self.assertRaises(ValueError): self.make(self.expected(), 'unknown')


if __name__ == '__main__':
    unittest.main()
