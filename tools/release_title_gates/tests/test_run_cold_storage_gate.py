# SPDX-License-Identifier: GPL-2.0-or-later
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_cold_storage_gate import build_cold_job


class ColdStorageGateTests(unittest.TestCase):
    def setUp(self):
        self.base = json.loads((ROOT / "fixtures" / "base-job.json").read_text())
        self.firmware = {"id": "firmware", "sha256": "a" * 64}
        self.disc = {"id": "cold-xiso", "sha256": "b" * 64}
        self.seed = {"id": "clean-hdd", "sha256": "c" * 64}

    def test_phase_a_retains_candidate_authored_hdd_and_waits_for_pass_line(self):
        job = build_cold_job(self.base, "candidate", "A", self.firmware,
                             self.disc, self.seed)
        self.assertTrue(job["runtimeState"]["keepOnSuccess"])
        self.assertEqual(job["runtimeState"]["diskAssets"][0]["assetId"], "clean-hdd")
        self.assertEqual(job["runtimeState"]["diskAssets"][0]["retention"], "keep")
        self.assertEqual(job["plan"][0]["type"], "wait_for_artifact")
        self.assertEqual(job["plan"][0]["condition"]["containsText"],
                         "COLD_STORAGE_RESULT phase=A status=PASS")

    def test_phase_b_uses_exact_import_and_requires_pending_read_result(self):
        imported = {"id": "candidate-authored", "sha256": "d" * 64}
        job = build_cold_job(self.base, "candidate", "B", self.firmware,
                             self.disc, imported)
        self.assertFalse(job["runtimeState"]["keepOnSuccess"])
        self.assertEqual(job["runtimeState"]["diskAssets"][0]["assetId"],
                         "candidate-authored")
        self.assertEqual(job["runtimeState"]["diskAssets"][0]["retention"],
                         "deleteAfterEvidence")
        checks = job["workload"]["correctnessChecks"]
        self.assertIn("pending_reads=", checks[1]["containsText"])
        dvd = next(row for row in job["runtimeState"]["isolation"]["readOnlyAssets"]
                   if row["field"] == "dvd_path")
        self.assertEqual((dvd["assetId"], dvd["expectedSha256"]),
                         ("cold-xiso", "b" * 64))


if __name__ == "__main__":
    unittest.main()
