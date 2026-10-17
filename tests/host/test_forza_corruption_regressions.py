#!/usr/bin/env python3
"""Lock the Forza corruption rollback and file-position repair."""

import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SYSVA_REVERT = "patches/roswell/0155-revert-sysva-local-invalidation.patch"
XDVDFS_REPAIR = "patches/roswell/0156-xdvdfs-preserve-file-position.patch"
PAYLOAD_QUALIFICATION = "patches/roswell/0157-forza-payload-association-qualification.patch"
RESET_MEDIA_LIFETIME = "patches/roswell/0158-reset-media-lifetime.patch"


class ForzaCorruptionRegressionTests(unittest.TestCase):
    def setUp(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        self.entries = lock["repositories"]["roswell"]["patches"]

    def test_corrective_patches_are_consecutive_and_hash_locked(self):
        self.assertEqual(
            [entry["path"] for entry in self.entries[-4:]],
            [SYSVA_REVERT, XDVDFS_REPAIR, PAYLOAD_QUALIFICATION, RESET_MEDIA_LIFETIME],
        )
        for entry in self.entries[-4:]:
            self.assertEqual(
                hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest(),
                entry["sha256"],
            )

    def test_sysva_candidate_is_rolled_back_to_global_invalidation(self):
        patch = (ROOT / SYSVA_REVERT).read_text()
        self.assertIn("-#define NXK_SYSVA_LOCAL_TLB_MAX 4", patch)
        self.assertIn("+    __writecr3(__readcr3());", patch)
        self.assertNotIn("+            __invlpg", patch)

    def test_async_optical_handles_stay_on_legacy_ordered_path(self):
        patch = (ROOT / XDVDFS_REPAIR).read_text()
        self.assertIn("Sp->FileObject->Flags & FO_SYNCHRONOUS_IO", patch)
        self.assertIn("fo.Flags=0;CHECK(!XdvdPlanForwardRead", patch)
        self.assertIn("completion order and can redirect", patch)

    def test_qd12_stress_verifies_request_to_buffer_association(self):
        patch = (ROOT / PAYLOAD_QUALIFICATION).read_text()
        for token in (
            "stamp_read_payloads",
            "request_index[WINDOW]",
            "pending_children[pick]",
            "CHECK(first==expected&&last==~expected)",
            'TEXT(label_xdvdfs_async, "Optical direct reads")',
        ):
            self.assertIn(token, patch)


if __name__ == "__main__":
    unittest.main()
