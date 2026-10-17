"""Regression checks for lifecycle joins and alertable polling evidence."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("latency", ROOT / "tools/forza_live_latency.py")
latency = importlib.util.module_from_spec(spec)
spec.loader.exec_module(latency)


def event(kind, time, **fields):
    return dict(kind=kind, host_ns=time, virtual_ns=time, thread="thread", free_pages="783", **fields)


def request():
    return [
        event("_XeNtReadFile@32", 0, returning="0", esp="stack", a5="iosb", ret="caller", a7="00000200"),
        event("fatx_dispatch", 1000, iosb="iosb", name="\\FarmersLipShort.res"),
        event("native_submit", 2000, iosb="iosb", irp="irp"),
        event("_XeNtReadFile@32", 3000, returning="1", esp="stack", eax="00000103"),
        event("delay_thread", 4000, a1="00000001", a2="00000001", zero_interval=True),
        event("io_complete", 10000, irp="irp", status="00000000", info="512"),
        event("delay_thread", 30000000, a1="00000001", a2="00000001", zero_interval=True),
        event("title_apc_dispatch", 30001000, a2="iosb"),
        event("world_completion_callback", 30002000, a3="iosb", a1="00000000", a2="00000200"),
    ]


class LatencyTest(unittest.TestCase):
    def test_measures_storage_and_poll_separately(self):
        result = latency.analyze(request())
        self.assertEqual(result["native_ms"]["median"], .008)
        self.assertEqual(result["done_to_title_ms"]["median"], 29.991)
        self.assertEqual(result["read_completed_after_first_zero_timeout_poll"], 1)
        self.assertEqual(result["world_callback_byte_count_mismatches"], 0)
        self.assertEqual(result["world_actual_callbacks"], 1)

    def test_reused_completed_irp_does_not_overwrite_old_completion(self):
        rows = request()
        rows.insert(6, event("io_complete", 20000, irp="irp", status="c0000001", info="0"))
        self.assertEqual(latency.analyze(rows)["native_ms"]["median"], .008)

    def test_duplicate_callback_is_not_counted_twice(self):
        rows = request() + [event("title_apc_dispatch", 30003000, a2="iosb")]
        result = latency.analyze(rows)
        self.assertEqual(result["world_reads_delivered"], 1)
        self.assertEqual(result["capture_join_notes_all_files"]["duplicate_title_dispatch"], 1)

    def test_two_eligible_entries_remain_visible(self):
        rows = request()
        rows.insert(6, event("delay_thread", 20000, a1="00000001", a2="00000001", zero_interval=True))
        self.assertEqual(latency.analyze(rows)["alertable_delay_entries_between_completion_and_callback"], {"2": 1})

    def test_nonalertable_wait_is_not_eligible(self):
        rows = request()
        rows[6]["a2"] = "00000000"
        self.assertEqual(latency.analyze(rows)["alertable_delay_entries_between_completion_and_callback"], {"0": 1})

    def test_virtual_clock_rewind_rejected(self):
        rows = request()
        rows[7]["virtual_ns"] = 0
        with self.assertRaisesRegex(ValueError, "rewind"):
            latency.analyze(rows)

    def test_interval_requires_both_halves_and_discards_unneeded_memory(self):
        line = ("forza_io kind=delay_thread host_ns=1 virtual_ns=1 thread=1 free_pages=1 "
                "a1=00000001 a2=00000001 esp=00001000 a3=00001014 a5=00000000 "
                "a6=ffffffff p1=12345678")
        self.assertFalse(latency.normalize(line)["zero_interval"])
        self.assertTrue(latency.normalize(line.replace("a6=ffffffff", "a6=00000000"))["zero_interval"])
        self.assertNotIn("p1", latency.normalize(line))


if __name__ == "__main__":
    unittest.main()
