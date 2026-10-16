#!/usr/bin/env python3
"""Lock the ordinary ATA read cache-capture fast path."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AtaCacheCaptureCandidateTests(unittest.TestCase):
    def test_patch_order_and_hash_are_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        paths = [entry["path"] for entry in entries]
        expected = [
            "patches/roswell/0150-native-packet-prepare-hotpath.patch",
            "patches/roswell/0151-ata-cache-capture-hotpath.patch",
        ]
        start = paths.index(expected[0])
        self.assertEqual(paths[start:start + 2], expected)
        for entry in entries[start:start + 2]:
            data = (ROOT / entry["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry["sha256"])

    def test_ordinary_requests_skip_unconsumed_cache_records(self):
        patch = (ROOT / "patches/roswell/0151-ata-cache-capture-hotpath.patch").read_text()
        self.assertIn("command != 0xec && command != 0xa1", patch)
        self.assertIn("NxAtapiCacheCaptureResult", patch)
        self.assertIn("Request->Complete != NULL", patch)
        self.assertIn("REQUEST_FLAG_INTERNAL", patch)
        self.assertIn("result_copy_calls == 0", patch)
        self.assertIn("memset(&request.NxCacheResult, 0x5a", patch)

    def test_contract_keeps_identify_publication_and_hardware_paths(self):
        spec = (ROOT / "docs/storage-replacement/independent-implementation/"
                "request-engine/ATA-PATA-HOTPATH-SPEC.md").read_text()
        for token in ("IDENTIFY", "PATA device selection", "port-leave",
                      "remain unchanged", "release-i386"):
            self.assertIn(token, spec)


if __name__ == "__main__":
    unittest.main()
