# SPDX-License-Identifier: GPL-2.0-or-later
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_release_gates import common_score, import_retained_hdd


class FakeApi:
    def __init__(self):
        self.calls = []

    def json(self, path, method="GET", body=None):
        self.calls.append((path, method, body))
        if method == "POST":
            return {"state": "queued"}
        if path.endswith("/import-local"):
            return {"state": "completed"}
        return {"ready": True, "sha256": "a" * 64}


class RetainedHddImportTests(unittest.TestCase):
    def test_import_is_generic_and_uses_exact_retained_runtime_hdd(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "runtime-state.json").write_text(json.dumps({
                "directory": r"C:\runner\runtime\candidate"
            }))
            api = FakeApi()
            result = import_retained_hdd(api, root, "candidate", "pgr2-profile")
            self.assertEqual(result["id"], "sb-candidate-pgr2-profile-" + root.name[:17].lower())
            post = next(call for call in api.calls if call[1] == "POST")
            self.assertEqual(post[2]["path"], r"C:\runner\runtime\candidate\hdd.qcow2")
            self.assertIn("PGR2 profile", post[2]["description"])

    def test_planned_diagnostics_do_not_count_as_operator_intervention(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "qemu.log").write_text("")
            (root / "job.json").write_text(json.dumps({
                "plan": [{"type": "diagnostic"}, {"type": "diagnostic"}]
            }))
            (root / "result.json").write_text(json.dumps({
                "status": "completed", "exitCode": 0, "crash": {"Crashed": False},
                "operatorActivity": {
                    "Intervened": True, "ManualInputs": 0, "Pauses": 0,
                    "Screenshots": 0, "PreviewCaptures": 0, "BulkTransfers": 0,
                    "HostStateChanges": 0, "Diagnostics": 2,
                },
                "diagnostics": [{"Status": "completed"}, {"Status": "completed"}],
                "workload": {"Correctness": "passed", "Evidence": "complete"},
            }))
            self.assertTrue(common_score(root)["unattended"])
            result = json.loads((root / "result.json").read_text())
            result["operatorActivity"]["Diagnostics"] = 3
            (root / "result.json").write_text(json.dumps(result))
            self.assertFalse(common_score(root)["unattended"])


if __name__ == "__main__":
    unittest.main()
