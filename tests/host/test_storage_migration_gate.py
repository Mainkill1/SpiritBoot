"""Synthetic regression tests for the read-only storage migration preflight.

These do not certify a real firmware build, independence, or license compliance.
"""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from tools import storage_migration_gate as gate


class StorageMigrationGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "assembled"
        self.new = self.source / "drivers/storage/class/nxstorage"
        self.optical = self.source / "drivers/storage/class/nxcdrom"
        self.new.mkdir(parents=True)
        self.optical.mkdir(parents=True)
        (self.new / "request.c").write_text(
            '#include <ntddk.h>\nvoid NxStorageSubmit(void) {}\n', encoding="utf-8")
        (self.new / "nxstorage.h").write_text(
            '#pragma once\n', encoding="utf-8")
        (self.optical / "nxcdrom.c").write_text(
            '#include <ntddk.h>\nvoid CdromDispatch(void) {}\n',
            encoding="utf-8")
        self.manifest = {
            "schema": 1, "status": "built", "source_directory": str(self.source),
            "source_tree": "a" * 40, "flash_sha256": "b" * 64,
        }
        self.candidate_link = (
            "i686-w64-mingw32-gcc -o xboxkrnl.exe "
            "libatapi.a libpciide.a libpciidex.a "
            "libnxstorage.a libnxcdrom.a libpartmgr.a "
            "libmountmgr.a libxdvdfs.a libvfatfs.a"
        )
        self.baseline_link = (
            "i686-w64-mingw32-gcc -o xboxkrnl.exe "
            "libclasspnp.a libdisk.a libnxcdrom.a"
        )

    def run_check(self, mode="candidate", link=None,
                  symbols="84001000 T _NxDiskDriverEntry@8\n"):
        return gate.check(
            self.source, self.manifest,
            self.candidate_link if link is None else link, symbols, mode)

    def test_candidate_passes_the_preflight_only(self):
        result = self.run_check(symbols="84001000 T _NxDiskDriverEntry@8\n")
        self.assertTrue(result["passed"])
        self.assertEqual(result["scope"], "PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION")
        self.assertEqual(result["mode"], "candidate")
        self.assertEqual(result["source_tree"], self.manifest["source_tree"])

    def test_baseline_expected_archive_names(self):
        result = self.run_check(mode="baseline", link=self.baseline_link,
                                symbols="84000000 T _ClassInitialize@12\n")
        self.assertTrue(result["passed"])
        self.assertEqual(result["linked_libraries"],
                         ["classpnp", "disk", "nxcdrom"])
        self.assertFalse(self.run_check(mode="baseline")["passed"])

    def test_missing_required_lower_driver_fails(self):
        result = self.run_check(link=self.candidate_link.replace("libatapi.a", ""))
        self.assertFalse(result["passed"])
        self.assertIn("atapi", result["checks"][0]["detail"])

    def test_linked_legacy_archives_fail_even_if_candidate_present(self):
        result = self.run_check(link=self.candidate_link + " libclasspnp.a libdisk.a")
        self.assertFalse(result["passed"])
        self.assertEqual(result["checks"][1]["detail"], ["classpnp", "disk"])

    def test_known_microsoft_derived_symbols_fail(self):
        result = self.run_check(symbols=(
            "84001000 T _ClassReadWrite@8\n"
            "84001040 T _DiskReadWriteVerification@8\n"
            "84001080 t _SubmitTransferPacket\n"))
        self.assertFalse(result["passed"])
        self.assertIn("SubmitTransferPacket", result["checks"][2]["detail"])
        self.assertIn("ClassReadWrite", result["checks"][2]["detail"])

    def test_direct_class_calls_and_headers_fail_in_owned_sources(self):
        (self.optical / "nxcdrom.c").write_text(
            '#include "classpnp.h"\nvoid f(void) { ClassInitialize(); }\n',
            encoding="utf-8")
        result = self.run_check()
        self.assertFalse(result["passed"])
        self.assertTrue(any("private storage header" in item
                            for item in result["checks"][3]["detail"]))
        self.assertTrue(any("Class* direct call" in item
                            for item in result["checks"][3]["detail"]))

    def test_new_driver_also_checked(self):
        (self.new / "helper.h").write_text('#include <classp.h>\n',
                                            encoding="utf-8")
        self.assertFalse(self.run_check()["passed"])

    def test_comments_do_not_trigger_a_false_failure(self):
        (self.optical / "nxcdrom.c").write_text(
            '/* #include "classpnp.h" */\n'
            '// ClassInitialize();\n'
            'int valid(void) { return 0; }\n', encoding="utf-8")
        self.assertTrue(self.run_check()["passed"])

    def test_unused_legacy_source_archive_does_not_trigger(self):
        old = self.source / "drivers/storage/class/classpnp"
        old.mkdir(parents=True)
        (old / "class.c").write_text('void ClassInitialize(void) {}\n',
                                      encoding="utf-8")
        self.assertTrue(self.run_check()["passed"])

    def test_missing_candidate_source_fails(self):
        (self.new / "request.c").unlink()
        self.assertFalse(self.run_check()["passed"])

    def test_linker_response_files_are_rejected_not_silently_ignored(self):
        with self.assertRaisesRegex(ValueError, "opaque @response"):
            gate.linked_archives("gcc @some_objects.rsp libnxstorage.a")
        with self.assertRaisesRegex(ValueError, "opaque @response"):
            gate.linked_archives("gcc -Wl,@link.rsp")
        with self.assertRaisesRegex(ValueError, "empty linker"):
            gate.linked_archives("")

    def test_archive_parsing_supports_paths_and_l_flags(self):
        result = gate.linked_archives(
            r"gcc -o xboxkrnl.exe ../build/libclasspnp.a "
            "../build/drivers/libdisk.a -latapi -Wl,--start-group")
        self.assertEqual(result, {"classpnp", "disk", "atapi"})

    def test_wrong_manifest_is_rejected(self):
        bad = dict(self.manifest)
        for field, value in (
            ("status", "failed"), ("source_tree", "short"),
            ("source_directory", "/wrong/tree"), ("flash_sha256", "bad")
        ):
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                gate.check(self.source, bad, self.candidate_link, "", "candidate")
            bad = dict(self.manifest)

    def test_cli_exit_status_and_machine_readable_diagnostic(self):
        (self.root / "build.json").write_text(json.dumps(self.manifest),
                                              encoding="utf-8")
        (self.root / "link.txt").write_text(self.candidate_link, encoding="utf-8")
        (self.root / "nm.txt").write_text("84001000 T _NxDiskDriverEntry@8\n", encoding="utf-8")
        args = [
            "--mode", "candidate", "--source", str(self.source),
            "--build-json", str(self.root / "build.json"),
            "--link-line", str(self.root / "link.txt"),
            "--symbols", str(self.root / "nm.txt")
        ]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = gate.main(args)
        self.assertEqual(status, 0)
        self.assertTrue(json.loads(stdout.getvalue())["passed"])

        (self.root / "link.txt").write_text(
            self.candidate_link + " -lclasspnp", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = gate.main(args)
        self.assertEqual(status, 1)
        self.assertFalse(json.loads(stdout.getvalue())["passed"])

        (self.root / "link.txt").write_text("gcc @opaque.rsp", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = gate.main(args)
        self.assertEqual(status, 2)
        self.assertIn("opaque", json.loads(stdout.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
