#!/usr/bin/env python3
"""Lock the measured XDVDFS direct-forward candidate and its safety gates."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATCH_PATH = "patches/roswell/0153-xdvdfs-direct-forwarding.patch"


class XdvdfsDirectForwardingTests(unittest.TestCase):
    def test_candidate_is_last_and_hash_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        self.assertEqual(entries[-1]["path"], PATCH_PATH)
        data = (ROOT / PATCH_PATH).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), entries[-1]["sha256"])

    def test_admission_retains_unsafe_requests_on_existing_path(self):
        patch = (ROOT / PATCH_PATH).read_text()
        for token in (
            "IRP_PAGING_IO | IRP_ASSOCIATED_IRP",
            "mdl->Next != NULL",
            "MDL_PAGES_LOCKED | MDL_SOURCE_IS_NONPAGED_POOL",
            "requiredSize = sizeof(MDL) + pages * sizeof(PFN_NUMBER)",
            "TargetDevice->AlignmentRequirement",
            "return FALSE;",
        ):
            self.assertIn(token, patch)
        self.assertIn("return XdvdForwardRead(Irp, fcb, sp, &plan);", patch)
        self.assertIn("fileOff = (ULONGLONG)sp->Parameters.Read.ByteOffset.QuadPart;", patch)

    def test_forwarding_reuses_parent_without_allocation_or_wait(self):
        patch = (ROOT / PATCH_PATH).read_text()
        start = patch.index("XdvdForwardRead(_In_ PIRP Irp")
        end = patch.index("\n \n /*\n  * Per-handle", start)
        body = patch[start:end]
        for token in (
            "IoCopyCurrentIrpStackLocationToNext",
            "IoSetCompletionRoutine",
            "IoCallDriver",
        ):
            self.assertIn(token, body)
        for token in ("IoBuildSynchronousFsdRequest", "KeWaitForSingleObject",
                      "ExAllocatePool", "MmProbeAndLockPages"):
            self.assertNotIn(token, body)

    def test_completion_normalizes_every_terminal_shape(self):
        patch = (ROOT / PATCH_PATH).read_text()
        for token in (
            "Irp->Cancel",
            "STATUS_CANCELLED",
            "!NT_SUCCESS(Irp->IoStatus.Status)",
            "Irp->IoStatus.Information < expected",
            "STATUS_END_OF_FILE",
            "Irp->IoStatus.Information > expected",
            "STATUS_DEVICE_PROTOCOL_ERROR",
            "fo->CurrentByteOffset.QuadPart",
            "IoMarkIrpPending(Irp)",
        ):
            self.assertIn(token, patch)

    def test_feature_is_explicit_and_in_all_advanced_toggle(self):
        header = (ROOT / "src/boot/setup/boot_setup.h").read_text()
        source = (ROOT / "src/boot/setup/boot_setup.c").read_text()
        self.assertIn("SB_EXPERIMENT_XDVDFS_ASYNC", header)
        self.assertIn("SB_EXPERIMENT_ADVANCED_ALL_MASK", header)
        self.assertIn("SB_EXPERIMENT_XDVDFS_ASYNC |", header)
        self.assertIn('TEXT(label_xdvdfs_async, "Optical async reads")', source)


if __name__ == "__main__":
    unittest.main()
