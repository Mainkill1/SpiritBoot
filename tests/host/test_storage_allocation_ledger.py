# SPDX-License-Identifier: GPL-2.0-only
import json
import subprocess
import sys
import unittest
from pathlib import Path

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/storage_allocation_diagnostic'))

from allocation_ledger import ReturnMatcher, analyze


def capture(body, baseline=None):
    events = [{"kind": "start", "baseline_complete": baseline is not None,
               "baseline": baseline or []}, *body, {"kind": "end", "status": "ok", "error": None}]
    return [dict(event, seq=i) for i, event in enumerate(events)]


def entry(call_id, call="allocate", size=100, address=0x9000, thread=0x80004000,
          owner=None):
    return dict(kind="entry", call_id=call_id, call=call, thread=thread,
                caller_pc=0x84001000 + call_id * 4, entry_esp=0x80008000 - call_id * 32,
                args=[0, size, 0x12345678] if call == "allocate" else [address, 0],
                owner=owner or {"kind": "unknown", "evidence_sha256": None})


def returned(call, pointer=0x9000, **updates):
    return dict(kind="return", call_id=call["call_id"], thread=call["thread"],
                pc=call["caller_pc"], esp=call["entry_esp"] + (16 if call["call"] == "allocate" else 12),
                eax=pointer, **updates)


class LedgerTests(unittest.TestCase):
    def test_simultaneous_peak_is_not_sum_of_separate_peaks(self):
        a, fa = entry(1, size=1000), entry(2, "free")
        b, fb = entry(3, size=1500, address=0xa000), entry(4, "free", address=0xa000)
        sequential = capture([a, returned(a), fa, returned(fa), b, returned(b, 0xa000), fb, returned(fb)], [])
        simultaneous = capture([a, returned(a), b, returned(b, 0xa000), fa, returned(fa), fb, returned(fb)], [])
        self.assertEqual(analyze(sequential)["observed"]["peak_requested_bytes"], 1500)
        self.assertEqual(analyze(simultaneous)["observed"]["peak_requested_bytes"], 2500)
        self.assertEqual(analyze(simultaneous)["observed"]["current_requested_bytes"], 0)

    def test_failed_allocation_does_not_create_live_allocation(self):
        a = entry(1, size=1000)
        result = analyze(capture([a, returned(a, 0)], []))
        self.assertEqual(result["observed"]["failed_allocations"], 1)
        self.assertEqual(result["observed"]["successful_allocations"], 0)
        self.assertEqual(result["observed"]["peak_requested_bytes"], 0)

    def test_unknown_owner_and_missing_boot_inventory_are_explicit(self):
        a = entry(1)
        result = analyze(capture([a, returned(a)]))
        self.assertEqual(result["observed"]["unknown_owner_successful_allocations"], 1)
        self.assertFalse(result["baseline_complete"])
        self.assertIsNone(result["physical_storage_peak_bytes"])
        self.assertFalse(result["native_qualified"])

    def test_duplicate_live_pointer_does_not_overwrite_original(self):
        a, b = entry(1, size=100), entry(2, size=999)
        result = analyze(capture([a, returned(a), b, returned(b)], []))
        self.assertEqual(result["integrity"], "unknown")
        self.assertIn("duplicate-live-address", [x["code"] for x in result["issues"]])
        self.assertEqual(result["observed"]["current_requested_bytes"], 100)

    def test_unknown_free_and_address_reuse(self):
        a, f, b = entry(1), entry(2, "free"), entry(3, size=300)
        result = analyze(capture([a, returned(a), f, returned(f), b, returned(b)], []))
        self.assertEqual(result["integrity"], "complete")
        self.assertEqual(result["observed"]["current_requested_bytes"], 300)
        missing = entry(4, "free", address=0xd000)
        result = analyze(capture([missing, returned(missing)], []))
        self.assertIn("free-without-live-allocation", [x["code"] for x in result["issues"]])

    def test_free_entry_does_not_claim_completed_release(self):
        a, f = entry(1), entry(2, "free")
        result = analyze(capture([a, returned(a), f], []))
        self.assertEqual(result["observed"]["current_requested_bytes"], 100)
        self.assertEqual(result["observed"]["completed_frees"], 0)
        self.assertIn("pending-call", [x["code"] for x in result["issues"]])

    def test_wrong_thread_pc_or_esp_cannot_complete_call(self):
        a = entry(1)
        for field, wrong in (("thread", a["thread"] + 4), ("pc", a["caller_pc"] + 4),
                             ("esp", a["entry_esp"] + 12)):
            ret = returned(a)
            ret[field] = wrong
            result = analyze(capture([a, ret], []))
            self.assertEqual(result["observed"]["successful_allocations"], 0)
            self.assertIn("return-identity-mismatch", [x["code"] for x in result["issues"]])

    def test_gaps_loss_and_incomplete_eof_are_unknown(self):
        a = entry(1)
        events = capture([a, returned(a)], [])
        events[2]["seq"] += 1
        for rows, code in ((events, "sequence-gap-or-duplicate"),
                           (capture([{"kind": "loss", "reason": "disconnect"}], []), "capture-loss"),
                           (capture([], [])[:-1], "missing-end")):
            result = analyze(rows)
            self.assertEqual(result["integrity"], "unknown")
            self.assertIn(code, [x["code"] for x in result["issues"]])

    def test_declared_owner_requires_bound_evidence_and_is_not_native_proof(self):
        a = entry(1, owner={"kind": "storage", "evidence_sha256": None})
        result = analyze(capture([a, returned(a)], []))
        self.assertEqual(result["observed"]["unknown_owner_successful_allocations"], 1)
        self.assertIn("unbound-owner-claim", [x["code"] for x in result["issues"]])
        a["owner"]["evidence_sha256"] = "e" * 64
        result = analyze(capture([a, returned(a)], []))
        self.assertEqual(result["observed"]["declared_storage_successful_allocations"], 1)
        self.assertIsNone(result["physical_storage_peak_bytes"])

    def test_existing_isr_counter_needs_no_reset_no_wrap_evidence(self):
        readings = [{"kind": "service_count", "value": 100}, {"kind": "service_count", "value": 117}]
        result = analyze(capture(readings, []))
        self.assertEqual(result["service_count"]["observed_modulo_delta"], 17)
        self.assertIsNone(result["service_count"]["qualified_isr_entries"])

    def test_free_cannot_delete_allocation_created_after_free_entry(self):
        f, a = entry(1, "free"), entry(2, size=700)
        result = analyze(capture([f, a, returned(a), returned(f)], []))
        self.assertEqual(result["observed"]["current_requested_bytes"], 700)
        self.assertEqual(result["integrity"], "unknown")

    def test_matcher_preserves_call_until_exact_thread_pc_and_esp_return(self):
        matcher, a = ReturnMatcher(), entry(1)
        key = matcher.enter(a)
        for wrong in ((key[0] + 4, key[1], key[2]), (key[0], key[1] + 4, key[2]),
                      (key[0], key[1], key[2] - 4)):
            self.assertIsNone(matcher.returned(*wrong))
        self.assertIs(matcher.returned(*key), a)
        self.assertIsNone(matcher.returned(*key))

    def test_matcher_rejects_identity_collision_and_capacity(self):
        matcher, a = ReturnMatcher(limit=1), entry(1)
        matcher.enter(a)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            matcher.enter(dict(a, call_id=2))
        with self.assertRaisesRegex(ValueError, "capacity"):
            matcher.enter(entry(3))

    def test_bool_and_oversized_pointer_rejected_without_exception(self):
        a = entry(1)
        for value in (True, -1, 2**32, 10**400):
            ret = returned(a)
            ret["eax"] = value
            result = analyze(capture([a, ret], []))
            self.assertEqual(result["integrity"], "unknown")
            self.assertEqual(result["observed"]["successful_allocations"], 0)

    def test_ambiguous_return_identity_cannot_add_a_second_allocation(self):
        a = entry(1)
        b = dict(a, call_id=2, args=[0, 500, 0])
        result = analyze(capture([a, b, returned(b, 0xa000)], []))
        self.assertEqual(result["observed"]["successful_allocations"], 0)
        self.assertIn("ambiguous-return-identity", [x["code"] for x in result["issues"]])

    def test_baseline_and_zero_byte_request_remain_distinct_from_absence(self):
        baseline = [{"address": 0xa000, "requested_bytes": 123, "owner": {"kind": "unknown"}}]
        a = entry(1, size=0)
        result = analyze(capture([a, returned(a)], baseline))
        self.assertEqual(result["observed"]["successful_allocations"], 1)
        self.assertEqual(result["observed"]["current_requested_bytes"], 123)
        self.assertTrue(result["baseline_complete"])
        self.assertIsNone(result["physical_storage_peak_bytes"])

    def test_failed_capture_outcome_and_missing_error_remain_unknown(self):
        for outcome in ({"kind": "end", "status": "ok"},
                        {"kind": "end", "status": "error", "error": "timed out"}):
            events = capture([], [])
            events[-1] = dict(outcome, seq=1)
            self.assertEqual(analyze(events)["integrity"], "unknown")

    def test_cli_preserves_malformed_json_and_incomplete_eof(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text(json.dumps(capture([], [])[0]) + "\n{bad json\n")
            run = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[2] / "tools/storage_allocation_diagnostic/allocation_ledger.py"), str(path)],
                                 text=True, capture_output=True, check=True)
            result = json.loads(run.stdout)
            self.assertEqual(result["integrity"], "unknown")
            self.assertIsNone(result["physical_storage_peak_bytes"])
            self.assertIn("capture-loss", [x["code"] for x in result["issues"]])

    def test_cli_requires_terminal_jsonl_frame(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in capture([], [])))
            run = subprocess.run([sys.executable, str(Path(__file__).resolve().parents[2] / "tools/storage_allocation_diagnostic/allocation_ledger.py"), str(path)],
                                 text=True, capture_output=True, check=True)
            result = json.loads(run.stdout)
            self.assertEqual(result["integrity"], "unknown")
            self.assertIn("incomplete-terminal-frame", [x["code"] for x in result["issues"]])


if __name__ == "__main__":
    unittest.main()
