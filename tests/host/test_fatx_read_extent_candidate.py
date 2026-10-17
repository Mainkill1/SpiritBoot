#!/usr/bin/env python3
"""Lock the bounded FATX read-extent fast lane and its exact-body checks."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class FatxReadExtentCandidateTests(unittest.TestCase):
    def test_candidate_follows_qd12_patch_and_is_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        paths = [entry["path"] for entry in entries]
        index = paths.index("patches/roswell/0149-fatx-hot-read-extent.patch")
        self.assertEqual(paths[index - 1],
                         "patches/roswell/0148-native-storage-qd12-hotpath.patch")
        entry = entries[index]
        self.assertEqual(entry["path"],
                         "patches/roswell/0149-fatx-hot-read-extent.patch")
        data = (ROOT / entry["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_patch_keeps_one_bounded_generation_checked_extent(self):
        patch = (ROOT / "patches/roswell/0149-fatx-hot-read-extent.patch").read_text()
        self.assertIn("VFAT_READ_EXTENT ReadExtent;", patch)
        self.assertNotIn("ReadExtents[", patch)
        self.assertIn("Extent->Generation != Cache->Generation", patch)
        self.assertIn("VfatInvalidateSeekCheckpoints", patch)
        self.assertIn("VfatTryMapRead", patch)

    def test_patch_carries_exact_body_and_coupling_checks(self):
        patch = (ROOT / "patches/roswell/0149-fatx-hot-read-extent.patch").read_text()
        for path in ("check-read-extent-cache.py", "check-async-coupling.py",
                     "check-async-read.py", "check-seek-checkpoints.py"):
            self.assertIn(path, patch)
        self.assertIn("FATX extent cache: %u checks, 0 failures", patch)

    def test_contract_records_locking_fallback_and_invalidation(self):
        spec = (ROOT / "docs/storage-replacement/independent-implementation/fatx/"
                "FATX-READ-EXTENT-CACHE-SPEC.md").read_text()
        for token in ("MainResource", "LastMutex", "falls through",
                      "before its first mutation", "No prohibited legacy"):
            self.assertIn(token, spec)


if __name__ == "__main__":
    unittest.main()
