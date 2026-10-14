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
from storage_evidence_fixture import capture_fixture, hash_file, pe_image


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
        command = self.candidate_link if link is None else link
        capture_fixture(self.root, self.source, self.manifest, command, symbols)
        return gate.check(
            self.source, self.manifest,
            command, symbols, mode)

    def test_changed_worktree_with_unchanged_claimed_tree_is_rejected(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        (self.new / "request.c").write_text("void ChangedSource(void) {}\n")
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_git_checkout_line_endings_are_bound_without_rejecting_valid_crlf(self):
        import subprocess
        (self.source / '.gitattributes').write_text('*.txt text eol=crlf\n')
        text = self.source / 'notice.txt'
        text.write_bytes(b'first\nsecond\n')
        subprocess.run(['git', 'init', '-q', str(self.source)], check=True)
        subprocess.run(['git', '-C', str(self.source), 'add', '.'], check=True)
        text.write_bytes(b'first\r\nsecond\r\n')
        self.assertTrue(self.run_check()['passed'])
        # Canonically identical LF cannot substitute for the captured CRLF.
        text.write_bytes(b'first\nsecond\n')
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link,
                       '84001000 T _NxDiskDriverEntry@8\n', 'candidate')

    def test_missing_or_changed_flash_is_rejected(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        for change in ("missing", "changed"):
            with self.subTest(change=change):
                _, flash, _ = capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
                if change == "missing":
                    flash.unlink()
                else:
                    flash.write_bytes(b"different image")
                with self.assertRaises((ValueError, OSError)):
                    gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_refreshing_flash_manifest_cannot_replace_the_recorded_packed_image(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        _, flash, _ = capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        flash.write_bytes(b"unrelated replacement flash")
        self.manifest["flash_sha256"] = hash_file(flash)
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_stale_pe_or_linker_map_is_rejected(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        for artifact in ("kernel", "map"):
            with self.subTest(artifact=artifact):
                kernel, _, linker_map = capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
                file = kernel if artifact == "kernel" else linker_map
                file.write_bytes(file.read_bytes() + b"stale")
                with self.assertRaises(ValueError):
                    gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_nm_listing_must_match_the_actual_pe(self):
        capture_fixture(self.root, self.source, self.manifest, self.candidate_link,
                        "84001000 T _NxDiskDriverEntry@8\n")
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link,
                       "84001000 T _CompletelyDifferent@8\n", "candidate")

    def test_supplied_link_line_must_match_recorded_build(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link + " -lharmless", listing, "candidate")

    def test_executed_link_record_is_mandatory_and_inputs_stay_bound(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        for change in ("missing", "input", "linked", "source", "failed"):
            with self.subTest(change=change):
                capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
                record_path = Path(self.manifest["storage_link_run"]["path"])
                record = json.loads(record_path.read_text())
                if change == "missing":
                    record_path.unlink()
                elif change == "input":
                    Path(record["resolved_inputs"][0]["path"]).write_bytes(b"changed archive")
                elif change == "linked":
                    Path(record["linked_output"]["path"]).write_bytes(b"changed linked image")
                else:
                    record["source_tree" if change == "source" else "exit_code"] = "c" * 40 if change == "source" else 1
                    record_path.write_text(json.dumps(record))
                    self.manifest["storage_link_run"]["sha256"] = hash_file(record_path)
                with self.assertRaises((ValueError, OSError)):
                    gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_recorded_nm_may_not_omit_a_defined_pe_symbol(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        kernel, _, _ = capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        kernel.write_bytes(pe_image([(0x84001000, "_NxDiskDriverEntry@8"), (0x84001004, "_Extra@0")]))
        self.manifest["kernel_unstripped"]["sha256"] = hash_file(kernel)
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_original_linked_symbols_cannot_be_renamed_in_unstripped_copy(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n84001004 T _ClassReadWrite@8\n"
        capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        kernel = Path(self.manifest["kernel_unstripped"]["path"])
        kernel.write_bytes(pe_image([(0x84001000, "_NxDiskDriverEntry@8"), (0x84001004, "_Harmless@8")]))
        listing = listing.replace("_ClassReadWrite@8", "_Harmless@8")
        Path(self.manifest["storage_symbols"]["path"]).write_text(listing)
        self.manifest["kernel_unstripped"]["sha256"] = hash_file(kernel)
        self.manifest["storage_symbols"]["sha256"] = hash_file(self.manifest["storage_symbols"]["path"])
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_map_output_must_match_the_real_linked_kernel(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        _, _, linker_map = capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        linker_map.write_text(linker_map.read_text().replace("xboxkrnl.exe", "other-build.exe"))
        self.manifest["linker_map"]["sha256"] = hash_file(linker_map)
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_stripped_kernel_must_retain_the_recorded_unstripped_code(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        final = self.root / "xboxkrnl.exe"
        changed = bytearray(final.read_bytes())
        changed[512] = 0xcc
        final.write_bytes(changed)
        self.manifest["kernel_final"]["sha256"] = hash_file(final)
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_resolved_map_must_contain_the_required_archives(self):
        listing = "84001000 T _NxDiskDriverEntry@8\n"
        _, _, linker_map = capture_fixture(self.root, self.source, self.manifest, self.candidate_link, listing)
        linker_map.write_text("OUTPUT(" + str(self.root / "xboxkrnl.unstripped.exe") + " pei-i386)\n")
        import hashlib
        self.manifest["linker_map"]["sha256"] = hashlib.sha256(linker_map.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            gate.check(self.source, self.manifest, self.candidate_link, listing, "candidate")

    def test_candidate_passes_the_preflight_only(self):
        result = self.run_check(symbols="84001000 T _NxDiskDriverEntry@8\n")
        self.assertTrue(result["passed"])
        self.assertEqual(result["scope"], "PRECHECK_ONLY_NOT_LICENSE_CERTIFICATION")
        self.assertEqual(result["mode"], "candidate")
        self.assertEqual(result["source_tree"], self.manifest["source_tree"])

    def test_baseline_expected_archive_names(self):
        result = self.run_check(mode="baseline", link=self.baseline_link,
                                symbols="84001000 T _ClassInitialize@12\n")
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

    def test_hidden_compiler_and_linker_library_forms_fail(self):
        for flag in ("-Wl,-lclasspnp", "-l:libdisk.a",
                     "-Wl,--library=classpnp", "-Xlinker -lclasspnp",
                     "-Wl,--start-group,-ldisk,--end-group", "-l disk"):
            with self.subTest(flag=flag):
                self.assertFalse(self.run_check(link=self.candidate_link + " " + flag)["passed"])

    def test_grouped_response_files_cannot_hide_linked_libraries(self):
        for flag in ("-Wl,--start-group,@hidden.rsp,--end-group",
                     "-Xlinker @hidden.rsp", "-Wl,-Map=result.map,@hidden.rsp"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.run_check(link=self.candidate_link + " " + flag)

    def test_non_nm_garbage_is_rejected(self):
        for listing in ("this is not an nm listing\n", "84001000 TT _Thing\n",
                        "84001000 T _Thing\nnot a listing\n"):
            with self.subTest(listing=listing), self.assertRaises(ValueError):
                self.run_check(symbols=listing)

    def test_optimized_legacy_symbol_is_identified(self):
        result = self.run_check(symbols="84001000 t _TransferPktComplete.constprop.0\n")
        self.assertFalse(result["passed"])
        self.assertIn("TransferPktComplete", result["checks"][2]["detail"])

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

    def test_incompatible_srb_helpers_are_not_approved_interface_headers(self):
        (self.new / 'nxstorage.h').write_text('#include <ddk/srbhelper.h>\n')
        result = self.run_check()
        self.assertFalse(result['passed'])
        self.assertTrue(any('private storage header' in item
                            for item in result['checks'][3]['detail']))

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
        capture_fixture(self.root, self.source, self.manifest, self.candidate_link,
                        "84001000 T _NxDiskDriverEntry@8\n")
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
        self.assertEqual(status, 2)
        self.assertFalse(json.loads(stdout.getvalue())["passed"])

        (self.root / "link.txt").write_text("gcc @opaque.rsp", encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            status = gate.main(args)
        self.assertEqual(status, 2)
        self.assertIn("opaque", json.loads(stdout.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
