# SPDX-License-Identifier: GPL-2.0-only
"""Discover both small V3 actual-C fault profiles in one host-suite invocation."""
import csv
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import unittest
from unittest.mock import patch

FIXTURE = Path(__file__).resolve().parents[1] / 'xbe/storage-io-recorder-v3'
SPEC = importlib.util.spec_from_file_location('storage_io_v3_fixture_tests', FIXTURE / 'test_recorder.py')
FIXTURE_TESTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FIXTURE_TESTS)
HOST_C_AVAILABLE = os.name == 'posix' and shutil.which('cc') is not None


@unittest.skipUnless(HOST_C_AVAILABLE, 'V3 memory-protection fault tests require POSIX and cc')
class StorageIoV3O0Tests(FIXTURE_TESTS.ActualRecorderTests):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'RECORDER_TEST_OPT': '-O0'}):
            super().setUpClass()


@unittest.skipUnless(HOST_C_AVAILABLE, 'V3 memory-protection fault tests require POSIX and cc')
class StorageIoV3O2Tests(FIXTURE_TESTS.ActualRecorderTests):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'RECORDER_TEST_OPT': '-O2'}):
            super().setUpClass()


class StorageIoV3MetadataTests(unittest.TestCase):
    def test_public_input_lineage_uses_valid_repository_relative_hashes(self):
        repository = FIXTURE.parents[2]
        lineage = json.loads((FIXTURE / 'public-input-lineage.json').read_text())
        self.assertEqual(lineage['scope'], 'owned public metadata/TAP fixture only; no driver bodies')
        self.assertEqual(len(lineage['files']), 4)
        for row in lineage['files']:
            source = Path(row['source'])
            self.assertFalse(source.is_absolute())
            self.assertNotIn('..', source.parts)
            current = repository / source
            copied = FIXTURE / row['path']
            self.assertTrue(current.is_file())
            self.assertEqual(current.read_bytes(), copied.read_bytes())
            self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(), row['sha256'])

    def test_checked_in_initializer_matches_both_complete_public_schedules(self):
        with (FIXTURE / 'replay-requests.csv').open(newline='') as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2048)
        expected = []
        for ordinal, row in enumerate(rows):
            values = tuple(int(row[key]) for key in ('dataset', 'index', 'offset', 'length', 'alignment'))
            dataset, index, offset, length, alignment = values
            self.assertEqual((dataset, index), divmod(ordinal, 1024))
            self.assertEqual(offset % 512, 0)
            self.assertTrue(0 < length <= 65536 and length % 512 == 0)
            self.assertTrue(0 <= alignment < 4096)
            expected.append((offset, length, alignment))
        actual = [tuple(map(int, values)) for values in re.findall(
            r'\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}',
            (FIXTURE / 'replay-requests.h').read_text())]
        self.assertEqual(actual, expected)
        for dataset, payload, resident in ((0, 10871296, 14823424), (1, 6526464, 10477568)):
            selected = expected[dataset * 1024:(dataset + 1) * 1024]
            self.assertEqual(sum(length for _, length, _ in selected), payload)
            self.assertEqual(sum((alignment + length + 4095) // 4096 * 4096
                                 for _, length, alignment in selected), resident)


if __name__ == '__main__':
    unittest.main(verbosity=2)
