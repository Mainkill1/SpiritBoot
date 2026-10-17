import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "forza_map_stream.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("forza_map_stream", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serial(passes=16, qd=12, pressure=900, failures=0, ticks=2_000_000):
    lines = [
        "# STORAGE-FORZA-MAP-META version=1 source=public-api-metadata "
        "requests=1024 observed_title_high_water=10 reference_high_water=12 "
        "measured_qd=12 pressure_pages=900 passes=16"
    ]
    for index in range(1, passes + 1):
        lines += [
            f"# STORAGE-FORZA-MAP-PASS index={index} count={passes}",
            "# STORAGE-IO-V6-META version=6 fixture_generation=6 route=fatx-file "
            f"dataset=0 qd_requested={qd} pressure_target={pressure} cache=warm",
            "# STORAGE-IO-V6-CASE operations_expected=1024 operations_completed=1024 "
            f"bytes_completed=10871296 apc_batch_ticks={ticks + index} caller_batch_ticks={ticks + index + 3} "
            f"submit_sum_ticks=500000 post_return_to_apc_sum_ticks=1400000 qd_requested={qd} "
            f"max_active_slots={qd} measured_pages_before={pressure} failures={failures} "
            "caller_occupancy=issue_to_apc_entry oracle=post_batch_full_bytes route=fatx-file",
            f"# STORAGE-IO-V6-END operations_submitted=1024 failures={failures} cleanup_complete=1 callback_buffers_retained=0",
        ]
    lines.append("ok 1 - Forza map streaming public request replay")
    return "\n".join(lines) + "\n"


class ForzaMapStreamTests(unittest.TestCase):
    def test_accepts_sustained_game_shaped_qd12_capture(self):
        result = load_tool().parse_serial(serial())
        self.assertEqual(result["status"], "qualified")
        self.assertEqual(result["passes"], 16)
        self.assertEqual(result["operations"], 16384)
        self.assertEqual(result["queue_high_water_min"], 12)
        self.assertEqual(result["pressure_pages"], 900)
        self.assertEqual(result["timing_median_ticks"]["submit_sum"], 500000)
        self.assertEqual(result["timing_median_ticks"]["post_return_to_apc_sum"], 1400000)
        self.assertEqual(result["timing_median_ticks"]["caller_batch"], 2000011.5)

    def test_rejects_short_shallow_or_failed_capture(self):
        tool = load_tool()
        for capture in (serial(passes=1), serial(qd=8), serial(failures=1)):
            with self.subTest(capture=capture.splitlines()[1]):
                self.assertEqual(tool.parse_serial(capture)["status"], "rejected")

        failed = tool.parse_serial(
            "# STORAGE-FORZA-MAP-META version=1\n"
            "# STORAGE-FORZA-MAP-PASS index=1 count=16\n"
            "# STORAGE-IO-V6-SETUP warmup_oracle_failures=339\n"
            "# STORAGE-IO-V6-ERROR stage=warmup-oracle\n"
            "# STORAGE-IO-V6-END operations_submitted=1024 failures=339 cleanup_complete=1 callback_buffers_retained=0\n"
            "not ok 1 - Forza map streaming public request replay\n"
        )
        self.assertEqual(failed["reported_failures"], 339)
        self.assertEqual(failed["warmup_oracle_failures"], 339)
        self.assertEqual(failed["error_stages"], ["warmup-oracle"])

    def test_compares_complete_captures_by_per_pass_median(self):
        tool = load_tool()
        better = tool.parse_serial(serial(ticks=1_000_000))
        slower = tool.parse_serial(serial(ticks=1_300_000))
        comparison = tool.compare(better, slower)
        self.assertAlmostEqual(comparison["candidate_over_reference"], 1.2999974500216748)
        self.assertAlmostEqual(comparison["candidate_change_percent"], 29.999745002167487)
        self.assertEqual(comparison["status"], "regressed")
        self.assertAlmostEqual(comparison["timing_change_percent"]["caller_batch"], 29.999655003967455)
        self.assertEqual(comparison["timing_change_percent"]["submit_sum"], 0.0)
        self.assertEqual(comparison["timing_change_percent"]["post_return_to_apc_sum"], 0.0)

    def test_cli_fails_closed_for_rejected_capture(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = pathlib.Path(temporary) / "serial.log"
            path.write_text("not ok 1 - Forza map streaming public request replay\n")
            result = subprocess.run(
                [sys.executable, str(TOOL), str(path)], capture_output=True, text=True
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('"status": "rejected"', result.stdout)

    def test_rejects_changed_fixture_identity_and_ambiguous_tap(self):
        tool = load_tool()
        valid = serial()
        mutations = (
            valid.replace("version=1 source=public-api-metadata", "version=9 source=junk"),
            valid.replace("route=fatx-file", "route=raw-device"),
            valid.replace("dataset=0", "dataset=1"),
            valid.replace("qd_requested=12", "qd_requested=10"),
            valid.replace("cache=warm", "cache=cold-ish"),
            valid.replace("index=2 count=16", "index=1 count=16"),
            valid.replace("index=16 count=16", "index=16 count=17"),
            valid + "not ok 1 - Forza map streaming public request replay\n",
        )
        for capture in mutations:
            with self.subTest(capture=capture[-120:]):
                self.assertEqual(tool.parse_serial(capture)["status"], "rejected")

    def test_rejects_extra_or_out_of_order_records(self):
        tool = load_tool()
        valid = serial()
        case = next(line for line in valid.splitlines() if "STORAGE-IO-V6-CASE" in line)
        self.assertEqual(
            tool.parse_serial(valid.replace("ok 1 -", case + "\nok 1 -"))["status"],
            "rejected",
        )
        first_pass = "# STORAGE-FORZA-MAP-PASS index=1 count=16\n"
        self.assertEqual(
            tool.parse_serial(valid.replace(first_pass, "", 1) + first_pass)["status"],
            "rejected",
        )

    def test_rejects_any_error_or_invalid_cleanup_and_timing(self):
        tool = load_tool()
        valid = serial()
        mutations = (
            valid.replace("# STORAGE-IO-V6-CASE", "# STORAGE-IO-V6-ERROR stage=timeout\n# STORAGE-IO-V6-CASE", 1),
            valid.replace("# STORAGE-IO-V6-CASE", "# STORAGE-IO-V6-SETUP warmup_oracle_failures=1\n# STORAGE-IO-V6-CASE", 1),
            valid.replace("# STORAGE-IO-V6-CASE", "# STORAGE-IO-V6-ORACLE-FAIL index=1 callback_status=c000009a\n# STORAGE-IO-V6-CASE", 1),
            valid.replace("callback_buffers_retained=0", "callback_buffers_retained=1", 1),
            valid.replace("apc_batch_ticks=2000001", "apc_batch_ticks=0", 1),
        )
        for capture in mutations:
            with self.subTest(capture=capture[:160]):
                self.assertEqual(tool.parse_serial(capture)["status"], "rejected")

    def test_rejects_prefixed_duplicate_or_incomplete_records(self):
        tool = load_tool()
        valid = serial()
        mutations = (
            valid.replace("# STORAGE-FORZA-MAP-META", "junk STORAGE-FORZA-MAP-META", 1),
            valid.replace("version=1 source=public-api-metadata", "version=9 version=1 source=public-api-metadata", 1),
            valid.replace("bytes_completed=10871296 ", "", 1),
            valid.replace("oracle=post_batch_full_bytes ", "", 1),
            valid.replace("caller_occupancy=issue_to_apc_entry ", "", 1),
        )
        for capture in mutations:
            with self.subTest(capture=capture[:180]):
                self.assertEqual(tool.parse_serial(capture)["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
