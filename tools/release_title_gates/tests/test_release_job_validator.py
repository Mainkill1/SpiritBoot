# SPDX-License-Identifier: GPL-2.0-or-later
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from release_job_validator import validate_release_job


class ReleaseJobValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        job_path = ROOT / "packages/forza-rclass-gate-0168/job.json"
        if not job_path.is_file():
            job_path = ROOT / "fixtures/base-job.json"
        cls.job = json.loads(job_path.read_text())
        cls.spec = {
            "firmware_sha256": "2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6",
            "xemu_sha256": "5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564",
            "hdd": {
                "id": "spiritboot-forza-hdd-pr253-0183-compact-v3",
                "sha256": "06c023a97ae1203ff2ab0533fd0b4deb238071e4457d930340146a0aa45044d6",
            },
            "disc": {
                "id": "forza-world-readonly-v1",
                "sha256": "63817cbbe70d07ca1d1dabfecdc61c859c154ca417ec20b0f51bec4e29b91c66",
            },
            "plan": cls.job["plan"],
        }

    def test_known_release_job_satisfies_fresh_private_contract(self):
        self.assertEqual(validate_release_job(self.job, self.spec), [])

    def test_unresolved_or_stale_firmware_is_rejected(self):
        spec = copy.deepcopy(self.spec)
        spec["firmware_sha256"] = None
        self.assertIn("firmware hash is unresolved", validate_release_job(self.job, spec))
        spec["firmware_sha256"] = self.spec["firmware_sha256"]
        spec["rejected_firmware_sha256"] = [self.spec["firmware_sha256"]]
        self.assertIn("firmware hash is explicitly rejected", validate_release_job(self.job, spec))

    def test_debug_snapshot_shared_hdd_and_route_drift_are_rejected(self):
        job = copy.deepcopy(self.job)
        job["startPaused"] = True
        job["snapshotName"] = "stale"
        job["runtimeState"]["isolation"]["requirePrivateGuestState"] = False
        job["runtimeState"]["diskAssets"][0]["retention"] = "keep"
        job["arguments"].append("-s")
        job["plan"] = job["plan"][:-1]
        errors = validate_release_job(job, self.spec)
        for expected in (
            "startPaused must be false",
            "snapshotName must be null",
            "private guest state is required",
            "release job contains a debugger argument",
            "job plan differs from the frozen route",
            "HDD retention must be deleteAfterEvidence",
        ):
            self.assertIn(expected, errors)

    def test_wrong_hdd_and_disc_are_rejected(self):
        job = copy.deepcopy(self.job)
        job["runtimeState"]["diskAssets"][0]["assetId"] = "wrong"
        dvd = next(x for x in job["runtimeState"]["isolation"]["readOnlyAssets"]
                   if x["field"] == "dvd_path")
        dvd["expectedSha256"] = "0" * 64
        errors = validate_release_job(job, self.spec)
        self.assertIn("HDD asset differs from the frozen contract", errors)
        self.assertIn("disc asset differs from the frozen contract", errors)


if __name__ == "__main__":
    unittest.main()
