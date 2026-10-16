#!/usr/bin/env python3
"""Lock the native page-pin workload and narrow scalar optimization shape."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class PagePinScalarCandidateTests(unittest.TestCase):
    def test_ordered_patches_are_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        paths = [entry["path"] for entry in entries]
        self.assertEqual(paths[-2:], [
            "patches/roswell/0144-page-pin-native-workload.patch",
            "patches/roswell/0145-scalar-page-pin-hotpath.patch",
        ])
        for entry in entries[-2:]:
            data = (ROOT / entry["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_workload_covers_physical_and_scatter_paths(self):
        patch = (ROOT / "patches/roswell/0144-page-pin-native-workload.patch").read_text()
        for token in ("physical-valid", "physical-reject-device", "scatter-accepted",
                      "scatter-rejected", "cleanup-after-reject"):
            self.assertIn(token, patch)
        self.assertIn("MmLockUnlockPhysicalPage", patch)
        self.assertIn("NtWriteFileGather", patch)
        regressions = json.loads((ROOT / "sources/native-regressions.json").read_text())
        self.assertEqual(regressions["page-pin-performance"], {
            "iso": "page-pin-performance.iso", "checks": 7,
        })

    def test_scalar_patch_keeps_unlock_out_of_line(self):
        patch = (ROOT / "patches/roswell/0145-scalar-page-pin-hotpath.patch").read_text()
        self.assertIn("NxpCanPin", patch)
        self.assertIn("NxkPageSupplyCommitPin(pfn)", patch)
        self.assertIn('assert "NxkPageSupplyCanPin(Page, TRUE)" in try_unlock', patch)
        self.assertIn('assert "NxpCanPin(Page, TRUE)" not in try_unlock', patch)


if __name__ == "__main__":
    unittest.main()
