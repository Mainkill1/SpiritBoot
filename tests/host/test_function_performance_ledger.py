#!/usr/bin/env python3
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = (ROOT / "docs/performance/evidence/forza-map-hotpath-20261015/"
            "deck-function-census")


class FunctionPerformanceLedgerTests(unittest.TestCase):
    def test_complete_entry_list_gets_explicit_disposition(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "ledger.csv"
            subprocess.run([
                sys.executable, str(ROOT / "tools/function_performance_ledger.py"),
                "--functions", str(EVIDENCE / "tools/spiritboot-final.functions"),
                "--executed", str(EVIDENCE / "results/executed-kernel-function-ledger.csv"),
                "--renames", str(EVIDENCE / "results/final-function-renames.json"),
                "--output", str(output),
            ], check=True)
            with output.open() as stream:
                rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 1684)
        self.assertEqual(sum(r["forza_marker_observed"] == "yes" for r in rows), 190)
        self.assertTrue(all(r["performance_treatment"] for r in rows))
        self.assertTrue(all(r["evidence_limit"] for r in rows))
        self.assertEqual(sum(r["primary_disposition"] == "requires_relevant_workload"
                             for r in rows), 1494)


if __name__ == "__main__":
    unittest.main()
