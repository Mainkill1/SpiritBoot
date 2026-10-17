# SPDX-License-Identifier: GPL-2.0-only
"""Keep new fixture license grants bound to the exact reviewed source bytes."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = {
    ROOT / "tests/xbe/kernel-export-contracts": {
        "Makefile", "main.c", "regression.h", "tap.c", "tap.h",
    },
    ROOT / "tests/xbe/storage-io-recorder-v3": {
        "Makefile", "main.c", "recorder.c", "host-mock/recorder-mock.c",
        "host-mock/selection-mock.c", "host-mock/xboxkrnl/xboxkrnl.h",
        "test_recorder.py", "replay-requests.csv", "replay-requests.h",
        "tap.c", "tap.h", "public-input-lineage.json", "source-provenance.json",
    },
}
ALLOWED = {"GPL-2.0-only", "GPL-2.0-or-later"}


class FixtureLicenseRecordTests(unittest.TestCase):
    def test_records_bind_each_named_file_and_grant(self):
        for fixture, expected in FIXTURES.items():
            with self.subTest(fixture=fixture.name):
                record = json.loads((fixture / "LICENSES.json").read_text())
                self.assertEqual(record["schema_version"], 1)
                paths = [row["path"] for row in record["files"]]
                self.assertEqual(len(paths), len(set(paths)))
                self.assertEqual(set(paths), expected)
                self.assertEqual(set(record["non_source_exclusions"]),
                                 {".gitignore", "LICENSES.json", "README.md"})
                for row in record["files"]:
                    self.assertEqual(set(row), {"path", "sha256", "spdx", "origin"})
                    self.assertIn(row["spdx"], ALLOWED)
                    self.assertTrue(row["origin"])
                    relative = Path(row["path"])
                    self.assertFalse(relative.is_absolute())
                    self.assertNotIn("..", relative.parts)
                    source = fixture / relative
                    self.assertTrue(source.is_file())
                    self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),
                                     row["sha256"])


if __name__ == "__main__":
    unittest.main()
