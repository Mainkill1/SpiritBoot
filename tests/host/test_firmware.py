import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="firmware test ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source tree"
        self.source.mkdir()
        (self.source / "toolchain-gcc.cmake").write_text("# fixture\n")
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.source), "-c", "user.name=Test",
                        "-c", "user.email=test@example.org", "commit", "-qm", "fixture"], check=True)
        self.revision = subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip()
        self.lock = self.root / "lock.json"
        self.lock.write_text(json.dumps({"schema": 1, "repositories": {
            "roswell": {"url": "https://github.com/mborgerson/roswell.git", "revision": self.revision},
            "xemu": {"url": "https://github.com/Mainkill1/xemu.git", "revision": "1" * 40}}}))
        self.output = self.root / "output tree"
        self.bin = self.root / "bin"
        self.bin.mkdir()
        cmake = self.bin / "cmake"
        cmake.write_text("#!" + sys.executable + "\n" + '''
import os, pathlib, sys
if '--version' in sys.argv:
    print('cmake fixture 1.0')
elif '-B' in sys.argv:
    p = pathlib.Path(sys.argv[sys.argv.index('-B') + 1]); p.mkdir(parents=True, exist_ok=True)
    if not (p / 'CMakeCache.txt').exists():
        (p / 'CMakeCache.txt').write_text('clean flags')
elif '--build' in sys.argv:
    print('epoch=' + os.environ.get('SOURCE_DATE_EPOCH', 'unset'))
    if os.environ.get('FAIL_BUILD'):
        print('compile error', file=sys.stderr)
        sys.exit(3)
    p = pathlib.Path(sys.argv[2]); p.mkdir(parents=True, exist_ok=True)
    byte = b'E' if 'EVIL' in (p / 'CMakeCache.txt').read_text() else b'X'
    (p / 'flash.bin').write_bytes(byte * int(os.environ.get('FLASH_SIZE', '262144')))
''')
        cmake.chmod(0o755)
        for name in ("ninja", "i686-w64-mingw32-gcc", "i686-w64-mingw32-g++"):
            (self.bin / name).symlink_to(cmake)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ["PATH"])

    def build(self, **env):
        return subprocess.run([sys.executable, str(ROOT / "scripts/build-firmware.py"),
                               "--source", str(self.source), "--output", str(self.output),
                               "--lock", str(self.lock)], env=dict(self.env, **env),
                              capture_output=True, text=True)

    def test_build_records_image_hash_and_revision(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertEqual(manifest["status"], "built")
        self.assertEqual(manifest["source_revision"], self.revision)
        self.assertEqual(manifest["flash_size"], 262144)
        self.assertEqual(manifest["flash_sha256"], hashlib.sha256(b"X" * 262144).hexdigest())
        self.assertTrue((self.output / "build.log").exists())

    def test_failed_build_invalidates_previous_flash(self):
        self.output.mkdir()
        (self.output / "flash.bin").write_bytes(b"stale")
        result = self.build(FAIL_BUILD="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.output / "flash.bin").exists())
        self.assertEqual(json.loads((self.output / "build.json").read_text())["status"], "failed")
        self.assertIn("compile error", (self.output / "build.log").read_text())

    def test_wrong_image_size_is_rejected(self):
        result = self.build(FLASH_SIZE="10")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("size", result.stderr.lower())
        self.assertFalse((self.output / "flash.bin").exists())

    def test_wrong_revision_is_rejected(self):
        lock = json.loads(self.lock.read_text())
        lock["repositories"]["roswell"]["revision"] = "0" * 40
        self.lock.write_text(json.dumps(lock))
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("revision", result.stderr.lower())

    def test_modified_source_is_rejected(self):
        (self.source / "toolchain-gcc.cmake").write_text("modified")
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty", result.stderr.lower())

    def test_malformed_lock_is_rejected(self):
        self.lock.write_text('{"schema": 2}')
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lock", result.stderr.lower())

    def test_build_uses_commit_epoch_for_reproducible_pe_headers(self):
        epoch = subprocess.check_output(["git", "-C", str(self.source), "show", "-s",
                                         "--format=%ct", "HEAD"], text=True).strip()
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("epoch=" + epoch, (self.output / "build.log").read_text())
        self.assertEqual(json.loads((self.output / "build.json").read_text())["source_date_epoch"], epoch)

    def test_rebuild_cleans_cached_linker_products(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        commands = json.loads((self.output / "build.json").read_text())["commands"]
        self.assertIn("--clean-first", commands[-1])

    def test_output_inside_source_is_rejected_without_deleting_source(self):
        self.output = self.source / "subdir"
        self.output.mkdir()
        flash = self.output / "flash.bin"
        flash.write_bytes(b"tracked source file")
        subprocess.run(["git", "-C", str(self.source), "add", "."], check=True)
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(flash.exists(), "a rejected build deleted source content")
        self.assertEqual(flash.read_bytes(), b"tracked source file")

    def test_rebuild_does_not_reuse_undeclared_cmake_cache(self):
        first = self.build()
        self.assertEqual(first.returncode, 0, first.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        command = manifest["commands"][0]
        work = Path(command[command.index("-B") + 1])
        (work / "CMakeCache.txt").write_text("CMAKE_C_FLAGS=EVIL")
        second = self.build()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(json.loads((self.output / "build.json").read_text())["flash_sha256"],
                         manifest["flash_sha256"])


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="xemu test ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.flash = self.root / "flash.bin"
        self.flash.write_bytes(b"X" * 262144)
        self.hdd = self.root / "disk 'quoted'.qcow2"
        self.hdd.write_bytes(b"disk fixture")
        self.dvd = self.root / "game.iso"
        self.dvd.write_bytes(b"open fixture")
        self.output = self.root / "capture"
        self.xemu = self.root / "fake xemu"
        self.xemu.write_text("#!" + sys.executable + "\n" + '''
import os, pathlib, sys, time, tomllib
if '--version' in sys.argv:
    print('fixture xemu')
    sys.exit(0)
pathlib.Path(os.environ['ARGS_FILE']).write_text(__import__('json').dumps(sys.argv[1:]))
if os.environ.get('WRITE_DISK'):
    config = tomllib.loads(pathlib.Path(sys.argv[sys.argv.index('-config_path') + 1]).read_text())
    pathlib.Path(config['sys']['files']['hdd_path']).write_bytes(b'guest result')
if os.environ.get('SLEEP'):
    time.sleep(60)
serial = sys.argv[sys.argv.index('-serial') + 1]
pathlib.Path(serial.removeprefix('file:')).write_text(os.environ.get('TAP', 'SpiritBoot fixture entry'))
print('emulator diagnostic')
sys.exit(int(os.environ.get('EXIT', '0')))
''')
        self.xemu.chmod(0o755)
        self.args_file = self.root / "args.json"
        self.converter = self.root / "qemu-img"
        self.converter.write_text("#!" + sys.executable + "\n" + '''
import os, pathlib, shutil, sys
if os.environ.get('FAIL_CONVERT'):
    print('broken disk chain', file=sys.stderr)
    sys.exit(1)
shutil.copyfile(sys.argv[-2], sys.argv[-1])
''')
        self.converter.chmod(0o755)

    def launch(self, tap=False, preserve_hdd=False, **env):
        args = [sys.executable, str(ROOT / "scripts/run-firmware.py"),
                "--xemu", str(self.xemu), "--flash", str(self.flash),
                "--hdd", str(self.hdd), "--dvd", str(self.dvd),
                "--output", str(self.output), "--timeout", "0.2"]
        if tap:
            args.append("--expect-tap")
        if preserve_hdd:
            args.append("--preserve-hdd")
        return subprocess.run(args, capture_output=True, text=True,
                              env=dict(os.environ, ARGS_FILE=str(self.args_file),
                                       PATH=str(self.root) + os.pathsep + os.environ['PATH'], **env))

    def test_capture_preserves_arguments_disk_and_hashes(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        import tomllib
        config = tomllib.loads((self.output / "xemu.toml").read_text())
        self.assertEqual(config["sys"]["files"]["hdd_path"], str(self.hdd))
        self.assertEqual(config["sys"]["files"]["bootrom_path"], "")
        self.assertEqual(config["sys"]["mem_limit"], "128")
        self.assertIn("-snapshot", json.loads(self.args_file.read_text()))
        self.assertEqual(self.hdd.read_bytes(), b"disk fixture")
        manifest = json.loads((self.output / "run.json").read_text())
        self.assertEqual(manifest["status"], "captured")
        self.assertEqual(manifest["assets"]["dvd"]["sha256"], hashlib.sha256(b"open fixture").hexdigest())
        self.assertIn("emulator diagnostic", (self.output / "emulator.log").read_text())

    def test_missing_media_does_not_launch(self):
        self.dvd.unlink()
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr.lower())
        self.assertFalse(self.args_file.exists())

    def test_preserved_guest_writes_use_private_copy(self):
        result = self.launch(preserve_hdd=True, WRITE_DISK="1")
        self.assertEqual(result.returncode, 0, result.stderr)
        import tomllib
        config = tomllib.loads((self.output / "xemu.toml").read_text())
        private = Path(config['sys']['files']['hdd_path'])
        self.assertEqual(private.parent, self.output)
        self.assertEqual(private.read_bytes(), b'guest result')
        self.assertEqual(self.hdd.read_bytes(), b'disk fixture')
        self.assertNotIn('-snapshot', json.loads(self.args_file.read_text()))
        manifest = json.loads((self.output / 'run.json').read_text())
        self.assertFalse(manifest['snapshot'])
        self.assertEqual(manifest['runtime_hdd']['initial_sha256'], hashlib.sha256(b'disk fixture').hexdigest())
        self.assertEqual(manifest['runtime_hdd']['sha256'], hashlib.sha256(b'guest result').hexdigest())

    def test_failed_private_conversion_never_launches_or_modifies_seed(self):
        result = self.launch(preserve_hdd=True, FAIL_CONVERT='1')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('private HDD conversion failed', result.stderr)
        self.assertFalse(self.args_file.exists())
        self.assertEqual(self.hdd.read_bytes(), b'disk fixture')

    def test_existing_capture_is_never_overwritten(self):
        self.output.mkdir()
        marker = self.output / "run.json"
        marker.write_text("previous")
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(marker.read_text(), "previous")

    def test_emulator_failure_keeps_diagnostics(self):
        result = self.launch(EXIT="7")
        self.assertNotEqual(result.returncode, 0)
        manifest = json.loads((self.output / "run.json").read_text())
        self.assertEqual(manifest["status"], "emulator_failed")
        self.assertEqual(manifest["returncode"], 7)

    def test_timeout_is_a_failure_with_retained_manifest(self):
        result = self.launch(SLEEP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads((self.output / "run.json").read_text())["status"], "timeout")

    def test_complete_tap_passes(self):
        result = self.launch(tap=True, TAP="TAP version 13\n1..2\nok 1 - entry\nnot ok 2 - gap # TODO pending\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "run.json").read_text())
        self.assertEqual(manifest["status"], "passed")
        self.assertEqual(manifest["tap"]["todo"], 1)

    def test_missing_tap_cannot_pass(self):
        result = self.launch(tap=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads((self.output / "run.json").read_text())["status"], "test_failed")


class TapTests(unittest.TestCase):
    def grade(self, text):
        from tools.firmware import grade_tap
        return grade_tap(text)

    def test_incomplete_plan_fails(self):
        self.assertFalse(self.grade("TAP version 13\n1..2\nok 1 - one\n")["passed"])

    def test_upstream_tap_version_14_passes(self):
        self.assertTrue(self.grade("TAP version 14\n1..1\nok 1 - entry\n")["passed"])

    def test_bare_failure_record_cannot_be_ignored(self):
        self.assertFalse(self.grade("TAP version 14\n1..1\nok 1\nnot ok\n")["passed"])

    def test_tab_separated_failure_cannot_be_ignored(self):
        self.assertFalse(self.grade("TAP version 14\n1..1\nok 1\nnot ok\t2\n")["passed"])

    def test_plan_between_results_is_rejected(self):
        self.assertFalse(self.grade("TAP version 14\nok 1\n1..2\nok 2\n")["passed"])

    def test_version_after_results_is_rejected(self):
        self.assertFalse(self.grade("ok 1\nTAP version 14\n1..1\n")["passed"])

    def test_multiple_boots_fail(self):
        self.assertFalse(self.grade("TAP version 13\n1..1\nok 1\nTAP version 13\n")["passed"])

    def test_duplicate_numbers_fail(self):
        self.assertFalse(self.grade("TAP version 13\n1..2\nok 1\nok 1\n")["passed"])

    def test_failure_fails(self):
        self.assertFalse(self.grade("TAP version 13\n1..1\nnot ok 1 - failure\n")["passed"])

    def test_bailout_fails(self):
        self.assertFalse(self.grade("TAP version 13\n1..1\nok 1\nBail out! crashed\n")["passed"])

    def test_skipped_tests_are_reported(self):
        result = self.grade("TAP version 13\n1..2\nok 1 - real\nok 2 - unavailable # SKIP hardware\n")
        self.assertTrue(result["passed"])
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["ok"], 1)


if __name__ == "__main__":
    unittest.main()
