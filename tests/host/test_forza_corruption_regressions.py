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
OPTICAL_ADMISSION = "patches/roswell/0160-optical-qd12-admission.patch"
COMPLETION_LIFETIME = "patches/roswell/0161-defer-native-child-completion.patch"
TRANSIENT_ENVELOPE_GROWTH = "patches/roswell/0162-transient-native-envelope-growth.patch"

QUEUED_ADMISSION = "patches/roswell/0163-queue-saturated-native-admission.patch"

COMPACT_ENVELOPES = "patches/roswell/0164-compact-data-overflow-envelopes.patch"

PRE_ADMISSION_CANCEL = "patches/roswell/0165-cancel-before-native-admission.patch"
SEALED_RUNDOWN = "patches/roswell/0166-sealed-rundown-notifications.patch"
ACTIVE_SCAN = "patches/roswell/0167-skip-inactive-native-slots.patch"
ADAPTER_BOOKKEEPING = "patches/roswell/0168-coalesce-native-adapter-bookkeeping.patch"
FIRST_READ_START = "patches/roswell/0173-fast-start-first-read-command.patch"
ADMISSION_HANDOFF = "patches/roswell/0175-handoff-native-admission-lock.patch"
SUBMIT_LOCK_RETURN = "patches/roswell/0176-transfer-submit-lock-to-core.patch"


class ForzaCorruptionRegressionTests(unittest.TestCase):
    def setUp(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        self.entries = lock["repositories"]["roswell"]["patches"]

    def test_corrective_patches_are_consecutive_and_hash_locked(self):
        self.assertEqual(
            [entry["path"] for entry in self.entries[-16:]],
            [SYSVA_REVERT, XDVDFS_REPAIR, PAYLOAD_QUALIFICATION,
             RESET_MEDIA_LIFETIME, OPTICAL_ADMISSION, COMPLETION_LIFETIME,
             TRANSIENT_ENVELOPE_GROWTH, QUEUED_ADMISSION, COMPACT_ENVELOPES,
             PRE_ADMISSION_CANCEL, SEALED_RUNDOWN, ACTIVE_SCAN,
             ADAPTER_BOOKKEEPING, FIRST_READ_START, ADMISSION_HANDOFF,
             SUBMIT_LOCK_RETURN],
        )
        for entry in self.entries[-16:]:
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

    def test_child_irp_reuse_is_deferred_past_lower_completion(self):
        patch = (ROOT / COMPLETION_LIFETIME).read_text()
        for token in (
            "KDPC completion_dpc",
            "KeInsertQueueDpc(&envelope->completion_dpc",
            "NxNativeCompletionDpc",
            "async_split_waits_until_completion_callback_returns",
            "child_reuse_during_completion",
        ):
            self.assertIn(token, patch)

    def test_storage_bursts_grow_transiently_instead_of_failing_reads(self):
        patch = (ROOT / TRANSIENT_ENVELOPE_GROWTH).read_text()
        for token in (
            "allocate_dynamic_envelope",
            "NxNativeTrimDpc",
            "core_count=slot_count*4u",
            "saturated_pool_grows_transiently_instead_of_failing_game_reads",
            "pool_live==pools_before",
        ):
            self.assertIn(token, patch)

    def test_selected_read_path_keeps_single_owners_and_lock_handoffs(self):
        first = (ROOT / FIRST_READ_START).read_text()
        admission = (ROOT / ADMISSION_HANDOFF).read_text()
        submit = (ROOT / SUBMIT_LOCK_RETURN).read_text()
        for token in (
            "rescan_requested",
            "r->operation==NX_READ",
            "!s->done && !s->cancelled && !d->quarantined",
            "single-command pending submit",
        ):
            self.assertIn(token, first)
        for token in (
            "admit_waiting_requests_locked",
            "adapter->admission_active",
            "admit_waiting_requests_locked(adapter,envelope)",
            "CHECK(used<=9)",
        ):
            self.assertIn(token, admission)
        for token in (
            "NX_SUBMIT_LOCK_HELD",
            "if (!(submitted & NX_SUBMIT_LOCK_HELD)) lock(d)",
            "return (status==STATUS_PENDING ? NX_SUBMIT_PENDING:0)|NX_SUBMIT_LOCK_HELD",
            "CHECK(used<=7)",
        ):
            self.assertIn(token, submit)


if __name__ == "__main__":
    unittest.main()
