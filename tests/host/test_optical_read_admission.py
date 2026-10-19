"""Lock the optical request-admission fix that prevents game read loss."""
import hashlib
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
PATCH = "patches/roswell/0160-optical-qd12-admission.patch"


class OpticalReadAdmissionTests(unittest.TestCase):
    def test_qd12_fix_is_hash_locked_roswell_patch(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entry = next(item for item in lock["repositories"]["roswell"]["patches"]
                     if item["path"] == PATCH)
        data = (ROOT / PATCH).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_production_optical_profile_and_native_fixture_admit_twelve(self):
        patch = (ROOT / PATCH).read_text()
        added = "\n".join(
            line[1:] for line in patch.splitlines()
            if line.startswith("+") and not line.startswith("+++")
        )
        self.assertIn("NX_NATIVE_CDROM_SLOTS = 16", added)
        self.assertIn("parent_fixture optical_reads[12]", added)
        self.assertIn("lower_calls==12&&pending_child_count==12", added)
        self.assertIn("optical_reads[index].irp.IoStatus.Status==STATUS_SUCCESS", added)


if __name__ == "__main__":
    unittest.main()
