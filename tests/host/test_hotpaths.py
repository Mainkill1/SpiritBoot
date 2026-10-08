"""Contract tests for bounded execution-frequency reports and symbol attribution."""

import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

PATH = Path(__file__).resolve().parents[2] / "tools" / "kernel_hotpaths.py"
spec = importlib.util.spec_from_file_location("kernel_hotpaths", PATH)
hot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hot)


class ReportTests(unittest.TestCase):
    def report(self, rows, **extra):
        header = {"type": "header", "schema": 1,
                  "max_records": len(rows) if extra.get("dropped_translations") else 8}
        footer = {"type": "complete", "dropped_translations": 0,
                  "untracked_executions": 0, "untracked_weight": 0, **extra}
        return "\n".join(json.dumps(x) for x in [header, *rows, footer])

    def row(self, pc=0x84001001, count=3, digest="a" * 64):
        return {"type": "tb", "pc": hex(pc), "code_sha256": digest,
                "instructions": 2, "translations": 1, "executions": count}

    def symbols(self):
        return hot.parse_symbols(
            "84001000 T _First@0\n84001000 T _Alias@0\n"
            "84001008 t .l1\n84001010 T _Second@0\n84002000 T _Outside@0\n",
            [(".text", 0x84001000, 0x84001020)])

    def test_single_final_record_is_retained_and_large_counts_stay_exact(self):
        rows, meta = hot.parse_capture(self.report([self.row(count=2**54 + 1)]))
        self.assertEqual(rows[0]["executions"], 2**54 + 1)
        result = hot.rank(rows, self.symbols(), meta)
        self.assertEqual(result["functions"][0]["weighted_instructions"], (2**54 + 1) * 2)

    def test_aliases_preserved_local_labels_do_not_create_functions(self):
        result = hot.rank(*self.capture_args([self.row(pc=0x84001009)]))
        self.assertEqual(result["functions"][0]["symbols"], ["_Alias@0", "_First@0"])

    def capture_args(self, rows):
        records, meta = hot.parse_capture(self.report(rows))
        return records, self.symbols(), meta

    def test_unknown_addresses_are_not_assigned_to_last_function(self):
        result = hot.rank(*self.capture_args([self.row(pc=0x84001020)]))
        self.assertEqual(result["functions"], [])
        self.assertEqual(result["unknown_weighted_instructions"], 6)

    def test_changed_code_same_pc_remains_separate_in_raw_evidence(self):
        records, meta = hot.parse_capture(self.report([self.row(), self.row(digest="b" * 64)]))
        self.assertEqual(len(records), 2)
        result = hot.rank(records, self.symbols(), meta)
        self.assertEqual(result["functions"][0]["tb_variants"], 2)

    def test_overflow_is_reported_as_incomplete_coverage(self):
        rows, meta = hot.parse_capture(self.report([self.row()], dropped_translations=4,
                                                  untracked_executions=10, untracked_weight=20))
        result = hot.rank(rows, self.symbols(), meta)
        self.assertFalse(result["complete_coverage"])
        self.assertEqual(result["total_weighted_instructions"], 26)

    def test_truncated_capture_and_duplicate_identity_are_rejected(self):
        text = self.report([self.row()])
        for bad in (text.rsplit("\n", 1)[0], self.report([self.row(), self.row()])):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                hot.parse_capture(bad)

    def test_invalid_counts_and_identity_are_rejected(self):
        for key, value in (("executions", -1), ("executions", True),
                           ("instructions", 0), ("code_sha256", "wrong")):
            row = self.row(); row[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                hot.parse_capture(self.report([row]))

    def test_impossible_overflow_metadata_cannot_claim_complete_coverage(self):
        for extra in ({"untracked_executions": 3, "untracked_weight": 6},
                      {"dropped_translations": 1, "untracked_weight": 6},
                      {"dropped_translations": 1, "untracked_executions": 3, "untracked_weight": 1}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                hot.parse_capture(self.report([self.row()], **extra))
        text = self.report([self.row()]).replace('"max_records": 8', '"max_records": 131073')
        with self.assertRaises(ValueError):
            hot.parse_capture(text)


@unittest.skipUnless(os.environ.get("XEMU_PLUGIN_INCLUDE"), "set XEMU_PLUGIN_INCLUDE to the pinned QEMU header directory")
class NativePluginTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.executable = Path(cls.workspace.name) / "harness"
        flags = shlex.split(subprocess.check_output(["pkg-config", "--cflags", "--libs", "glib-2.0"], text=True))
        subprocess.run(["cc", "-Wall", "-Wextra", "-Wno-unused-parameter", "-Werror",
                        "-I" + os.environ["XEMU_PLUGIN_INCLUDE"],
                        str(Path(__file__).with_name("tb_plugin_harness.c")), "-o", str(cls.executable), *flags], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def test_production_callbacks_track_modified_code_and_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "capture"
            subprocess.run([str(self.executable), "output=" + str(out), "max_records=2"], check=True)
            rows, footer = hot.parse_capture(out.read_text())
            self.assertEqual(sorted(row["executions"] for row in rows), [5, 7])
            self.assertEqual(sorted(row["translations"] for row in rows), [1, 2])
            self.assertEqual(footer["dropped_translations"], 1)
            self.assertEqual(footer["untracked_executions"], 11)
            self.assertEqual(footer["untracked_weight"], 22)

    def test_existing_evidence_and_invalid_options_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "capture"; out.write_text("preserve")
            r = subprocess.run([str(self.executable), "output=" + str(out)], capture_output=True)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(out.read_text(), "preserve")
            for value in ("0", "131073", "-1", "2junk"):
                fresh = Path(directory) / ("invalid-" + value)
                r = subprocess.run([str(self.executable), "output=" + str(fresh),
                                    "max_records=" + value], capture_output=True)
                self.assertEqual(r.returncode, 2)
                self.assertFalse(fresh.exists())


if __name__ == "__main__":
    unittest.main()
