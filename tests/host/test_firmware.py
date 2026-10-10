import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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
        (self.source / "fixture.txt").write_text("base\n")
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
import json, os, pathlib, sys
if '--version' in sys.argv:
    print('cmake fixture 1.0')
elif '-B' in sys.argv:
    p = pathlib.Path(sys.argv[sys.argv.index('-B') + 1]); p.mkdir(parents=True, exist_ok=True)
    source = pathlib.Path(sys.argv[sys.argv.index('-S') + 1])
    (p / 'configured-source.json').write_text(json.dumps({
        'path': str(source), 'fixture': (source / 'fixture.txt').read_text(),
        'new_guest': (source / 'tests/xbe/probe.c').exists()}))
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
        self.assertEqual(manifest["source_directory"], str(self.source))
        self.assertEqual(manifest["patches"], [])
        self.assertTrue((self.output / "build.log").exists())

    def test_metadata_diagnostic_is_explicit_and_recorded(self):
        default = self.build()
        self.assertEqual(default.returncode, 0, default.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertFalse(manifest["metadata_counters"])
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DNXK_METADATA_COUNTERS=OFF", configure)
        enabled = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-firmware.py"),
             "--source", str(self.source), "--output", str(self.output),
             "--lock", str(self.lock), "--metadata-counters"],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(enabled.returncode, 0, enabled.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertTrue(manifest["metadata_counters"])
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DNXK_METADATA_COUNTERS=ON", configure)

    def test_default_build_records_file_media_policy(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertEqual(manifest["media_policy"], "emulator-file-media")
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DXBOX_EMULATOR_FILE_MEDIA=ON", configure)

    def test_64_mib_build_pins_capacity_in_configure_and_receipt(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-firmware.py"),
             "--source", str(self.source), "--output", str(self.output),
             "--lock", str(self.lock), "--memory-mib", "64"],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertEqual(manifest["memory_mib"], 64)
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DXBOX_RAM_MIB=64", configure)

    def test_default_build_preserves_128_mib_capacity(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertEqual(manifest["memory_mib"], 128)
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DXBOX_RAM_MIB=128", configure)

    def test_upper_reservation_is_explicit_and_recorded(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertFalse(manifest["reserve_upper_ram"])
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DXBOX_RESERVE_UPPER_RAM=OFF", configure)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-firmware.py"),
             "--source", str(self.source), "--output", str(self.output),
             "--lock", str(self.lock), "--reserve-upper-ram"],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertTrue(manifest["reserve_upper_ram"])
        self.assertEqual(manifest["memory_mib"], 128)
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DXBOX_RESERVE_UPPER_RAM=ON", configure)

    def test_upper_reservation_rejects_64_mib_before_output_changes(self):
        from tools.firmware import build_firmware
        self.output.mkdir()
        image = self.output / "flash.bin"
        image.write_bytes(b"previous image")
        with self.assertRaisesRegex(ValueError, "128"):
            build_firmware(self.source, self.output, lock_path=self.lock,
                           memory_mib=64, reserve_upper_ram=True)
        self.assertEqual(image.read_bytes(), b"previous image")

    def test_unsupported_capacity_is_rejected_before_output_changes(self):
        from tools.firmware import build_firmware
        self.output.mkdir()
        image = self.output / "flash.bin"
        image.write_bytes(b"previous image")
        with self.assertRaisesRegex(ValueError, "memory"):
            build_firmware(self.source, self.output, lock_path=self.lock,
                           memory_mib=96)
        self.assertEqual(image.read_bytes(), b"previous image")

    def test_strict_build_records_disabled_media_policy(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/build-firmware.py"),
             "--source", str(self.source), "--output", str(self.output),
             "--lock", str(self.lock), "--media-policy", "strict"],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.output / "build.json").read_text())
        self.assertEqual(manifest["media_policy"], "strict")
        configure = next(c for c in manifest["commands"] if "-G" in c)
        self.assertIn("-DXBOX_EMULATOR_FILE_MEDIA=OFF", configure)

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

    def fixture_patch(self, name="first.patch", before="base", after="patched", new_guest=False):
        content = (f"diff --git a/fixture.txt b/fixture.txt\n"
                   f"--- a/fixture.txt\n+++ b/fixture.txt\n@@ -1 +1 @@\n-{before}\n+{after}\n")
        if new_guest:
            content += ("diff --git a/tests/xbe/probe.c b/tests/xbe/probe.c\n"
                        "new file mode 100644\n--- /dev/null\n+++ b/tests/xbe/probe.c\n"
                        "@@ -0,0 +1 @@\n+/* Licensed fixture guest */\n")
        path = self.root / "patches" / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(content)
        return {"path": "patches/" + name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}

    def set_patches(self, patches):
        lock = json.loads(self.lock.read_text())
        lock["repositories"]["roswell"]["patches"] = patches
        self.lock.write_text(json.dumps(lock))

    def build_direct(self):
        from tools.firmware import build_firmware
        with mock.patch("tools.firmware.ROOT", self.root), mock.patch.dict(os.environ, self.env):
            return build_firmware(self.source, self.output, lock_path=self.lock)

    def assert_patch_failure(self, pattern):
        self.output.mkdir(exist_ok=True)
        (self.output / "flash.bin").write_bytes(b"stale")
        with self.assertRaisesRegex((ValueError, subprocess.SubprocessError), pattern):
            self.build_direct()
        self.assertFalse((self.output / "flash.bin").exists())
        self.assertEqual(json.loads((self.output / "build.json").read_text())["status"], "failed")
        self.assertFalse(list(self.output.glob("work-*/build/configured-source.json")))
        self.assertEqual((self.source / "fixture.txt").read_text(), "base\n")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(self.source), "status", "--porcelain"], text=True), "")

    def test_patched_source_reaches_cmake_and_preserves_pristine_checkout(self):
        patch = self.fixture_patch(new_guest=True)
        self.set_patches([patch])
        manifest = self.build_direct()
        source = Path(manifest["source_directory"])
        self.assertNotEqual(source, self.source)
        self.assertTrue(source.is_relative_to(self.output))
        self.assertTrue((source / ".git").is_dir())
        self.assertFalse((source / ".git/objects/info/alternates").exists())
        configured = json.loads((Path(manifest["build_directory"]) / "configured-source.json").read_text())
        self.assertEqual(configured, {"path": str(source), "fixture": "patched\n", "new_guest": True})
        self.assertEqual(manifest["patches"], [patch])
        tree = subprocess.check_output(["git", "-C", str(source), "write-tree"], text=True).strip()
        self.assertEqual(manifest["source_tree"], tree)
        tracked = subprocess.check_output(["git", "-C", str(source), "ls-files"], text=True)
        self.assertIn("tests/xbe/probe.c", tracked)
        self.assertEqual((self.source / "fixture.txt").read_text(), "base\n")
        self.assertFalse((self.source / "tests").exists())
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(self.source), "status", "--porcelain"], text=True), "")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD"], text=True).strip(), self.revision)
        epoch = subprocess.check_output(
            ["git", "-C", str(self.source), "show", "-s", "--format=%ct", "HEAD"], text=True).strip()
        self.assertEqual(manifest["source_date_epoch"], epoch)
        base_objects = {p.name: p for p in (self.source / ".git/objects").glob("*/*") if p.is_file()}
        for obj in (source / ".git/objects").glob("*/*"):
            if obj.is_file() and obj.name in base_objects:
                self.assertNotEqual(obj.stat().st_ino, base_objects[obj.name].stat().st_ino)

    def test_ordered_patches_and_rebuild_use_fresh_reproducible_source(self):
        first = self.fixture_patch()
        second = self.fixture_patch("second.patch", "patched", "second")
        self.set_patches([first, second])
        a = self.build_direct()
        source = Path(a["source_directory"])
        self.assertEqual((source / "fixture.txt").read_text(), "second\n")
        (source / "fixture.txt").write_text("stale modified source\n")
        b = self.build_direct()
        self.assertNotEqual(a["source_directory"], b["source_directory"])
        self.assertEqual((Path(b["source_directory"]) / "fixture.txt").read_text(), "second\n")
        self.assertEqual(a["source_tree"], b["source_tree"])
        self.assertEqual(b["patches"], [first, second])

    def test_reverse_patch_order_fails_before_configuring(self):
        first = self.fixture_patch()
        second = self.fixture_patch("second.patch", "patched", "second")
        self.set_patches([second, first])
        self.assert_patch_failure("patch")

    def test_patch_hash_mismatch_invalidates_stale_image(self):
        patch = self.fixture_patch()
        patch["sha256"] = "0" * 64
        self.set_patches([patch])
        self.assert_patch_failure("checksum")

    def test_missing_patch_fails(self):
        self.set_patches([{"path": "patches/missing.patch", "sha256": "0" * 64}])
        self.assert_patch_failure("patch")

    def test_failed_patch_application_preserves_base(self):
        self.set_patches([self.fixture_patch(before="wrong base")])
        self.assert_patch_failure("patch")

    def test_patch_schema_rejects_malformed_entries(self):
        for patches in (None, {}, "bad", [None], [{}], [{"path": 2, "sha256": "0" * 64}],
                        [{"path": "patches/x", "sha256": "A" * 64}],
                        [{"path": "patches/x", "sha256": "0" * 63}],
                        [{"path": "patches/x", "sha256": 0}],
                        [{"path": "patches/x", "sha256": "0" * 64, "extra": True}]):
            with self.subTest(patches=patches):
                self.set_patches(patches)
                self.assert_patch_failure("lock")

    def test_patch_paths_reject_absolute_traversal_and_symlink_escape(self):
        for path in ("../outside.patch", "/tmp/outside.patch", "patches/../../outside.patch", "", "."):
            with self.subTest(path=path):
                self.set_patches([{"path": path, "sha256": "0" * 64}])
                self.assert_patch_failure("path")
        external = self.root.parent / (self.root.name + "-outside.patch")
        external.write_text("outside")
        self.addCleanup(external.unlink)
        link = self.root / "escape.patch"
        link.symlink_to(external)
        self.set_patches([{"path": link.name, "sha256": hashlib.sha256(b"outside").hexdigest()}])
        self.assert_patch_failure("path")

    def test_empty_patches_keep_original_source_and_tree(self):
        self.set_patches([])
        manifest = self.build_direct()
        self.assertEqual(manifest["source_directory"], str(self.source))
        self.assertEqual(manifest["patches"], [])
        tree = subprocess.check_output(
            ["git", "-C", str(self.source), "rev-parse", "HEAD^{tree}"], text=True).strip()
        self.assertEqual(manifest["source_tree"], tree)

    def test_clone_dissociates_existing_source_object_alternates(self):
        original = self.root / "object donor"
        self.source.rename(original)
        subprocess.run(["git", "clone", "-q", "--shared", str(original), str(self.source)], check=True)
        self.assertTrue((self.source / ".git/objects/info/alternates").exists())
        self.set_patches([self.fixture_patch()])
        manifest = self.build_direct()
        patched = Path(manifest["source_directory"])
        self.assertFalse((patched / ".git/objects/info/alternates").exists())
        original.rename(self.root / "donor moved")
        objects = subprocess.check_output(["git", "-C", str(patched), "fsck", "--full"],
                                          text=True, stderr=subprocess.STDOUT)
        self.assertNotIn("missing", objects)

    def test_patched_build_under_broken_ancestor_worktree_git_link(self):
        # Docker may mount a host worktree without the external Git metadata
        # named by its .git file. The explicit Roswell source has its own .git.
        (self.root / ".git").write_text("gitdir: /absent-spiritboot-worktree/git/worktrees/fixture\n")
        config = (self.source / ".git/config").read_bytes()
        self.set_patches([self.fixture_patch(new_guest=True)])
        manifest = self.build_direct()
        self.assertEqual(manifest["status"], "built")
        self.assertEqual((self.source / ".git/config").read_bytes(), config)
        self.assertEqual((self.source / "fixture.txt").read_text(), "base\n")
        self.assertEqual((Path(manifest["source_directory"]) / "fixture.txt").read_text(), "patched\n")
        self.assertTrue((Path(manifest["source_directory"]) / "tests/xbe/probe.c").is_file())
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(self.source), "status", "--porcelain"], text=True), "")

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() == 0, "requires root CI ownership fixture")
    def test_root_build_accepts_foreign_owned_pristine_checkout(self):
        for path in self.source.rglob("*"):
            os.chown(path, 65534, 65534)
        os.chown(self.source, 65534, 65534)
        self.set_patches([self.fixture_patch()])
        manifest = self.build_direct()
        self.assertEqual(manifest["status"], "built")
        self.assertEqual((self.source / "fixture.txt").read_text(), "base\n")


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

    def launch(self, tap=False, preserve_hdd=False, tb_plugin=None,
               memory_mib=128, timeout_seconds=2, **env):
        args = [sys.executable, str(ROOT / "scripts/run-firmware.py"),
                "--xemu", str(self.xemu), "--flash", str(self.flash),
                "--hdd", str(self.hdd), "--dvd", str(self.dvd),
                "--output", str(self.output), "--timeout", str(timeout_seconds)]
        if tap:
            args.append("--expect-tap")
        if preserve_hdd:
            args.append("--preserve-hdd")
        if tb_plugin is not None:
            args.extend(["--tb-plugin", str(tb_plugin)])
        if memory_mib != 128:
            args.extend(["--memory-mib", str(memory_mib)])
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

    def test_capture_allows_delayed_stub_startup(self):
        # Model scheduler/import delay in the identity fixture. This is not
        # the intentional timeout test below.
        stub = self.xemu.read_text()
        self.xemu.write_text(stub.replace(
            "if '--version' in sys.argv:",
            "time.sleep(0.3)\nif '--version' in sys.argv:"))
        result = self.launch(memory_mib=64)
        manifest = json.loads((self.output / "run.json").read_text())
        self.assertEqual(result.returncode, 0, manifest)
        self.assertEqual(manifest["status"], "captured")
        self.assertEqual(manifest["memory_mib"], 64)

    def test_missing_media_does_not_launch(self):
        self.dvd.unlink()
        result = self.launch()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr.lower())
        self.assertFalse(self.args_file.exists())

    def test_64_mib_launch_pins_actual_config_and_receipt(self):
        result = self.launch(memory_mib=64)
        self.assertEqual(result.returncode, 0, result.stderr)
        import tomllib
        config = tomllib.loads((self.output / "xemu.toml").read_text())
        self.assertEqual(config["sys"]["mem_limit"], "64")
        manifest = json.loads((self.output / "run.json").read_text())
        self.assertEqual(manifest["memory_mib"], 64)

    def test_unsupported_launch_capacity_creates_no_capture(self):
        from tools.firmware import run_firmware
        with self.assertRaisesRegex(ValueError, "memory"):
            run_firmware(self.xemu, self.flash, self.hdd, self.dvd,
                         self.output, memory_mib=96)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.args_file.exists())

    def test_optional_profiler_is_explicit_and_hash_pinned(self):
        plugin = self.root / "tb_frequency.so"
        plugin.write_bytes(b"plugin fixture")
        result = self.launch(tb_plugin=plugin)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads(self.args_file.read_text())
        self.assertEqual(args[args.index("-plugin") + 1],
                         f"{plugin},output={self.output}/tb-frequency.ndjson")
        manifest = json.loads((self.output / "run.json").read_text())
        self.assertEqual(manifest["assets"]["tb_plugin"]["sha256"],
                         hashlib.sha256(b"plugin fixture").hexdigest())

    def test_missing_plugin_never_launches(self):
        result = self.launch(tb_plugin=self.root / "missing.so")
        self.assertNotEqual(result.returncode, 0)
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
        result = self.launch(timeout_seconds=0.2, SLEEP="1")
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
