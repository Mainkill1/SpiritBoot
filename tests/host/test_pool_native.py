from pathlib import Path
import shutil
import tempfile
import unittest

from tools.pool_native import analyze, read_run


EVIDENCE = Path(__file__).resolve().parents[2] / "docs/optimization/pool-audit-2026-10-13/native"


class PoolNativeEvidenceTests(unittest.TestCase):
    def test_all_seven_triplets_conserve_pages_and_keep_every_timing(self):
        result = analyze(EVIDENCE)
        self.assertEqual(result["checks"], 14637)
        self.assertEqual(len(result["runs"]), 7)
        for request in (64, 280):
            self.assertTrue(all(value > 7 for value in result["comparisons"]["count"][request]["paired_percent_deltas"]))

    def test_wrong_public_capacity_cannot_pass_with_clean_tap(self):
        source = next(EVIDENCE.glob("*pool-seven-0-classes-*"))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / source.name
            shutil.copytree(source, destination)
            path = destination / "serial.log"
            path.write_text(path.read_text().replace("request=256 usable=264", "request=256 usable=504"))
            with self.assertRaisesRegex(ValueError, "public capacity"):
                read_run(destination, "classes")

    def test_missing_timing_round_cannot_publish_comparison(self):
        source = next(EVIDENCE.glob("*pool-seven-0-baseline-*"))
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / source.name
            shutil.copytree(source, destination)
            path = destination / "serial.log"
            path.write_text("\n".join(line for line in path.read_text().splitlines() if "pool_cost request=64 round=4" not in line))
            with self.assertRaisesRegex(ValueError, "incomplete five-round"):
                read_run(destination, "baseline")
