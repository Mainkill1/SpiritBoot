"""Compile and exercise the independent complete-candidate optical profile."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
PATCH = "0139-independent-nxcdrom-profile.patch"
PREREQUISITES = ("0127-independent-storage-primitives.patch",)


@unittest.skipUnless(shutil.which("clang") or shutil.which("gcc"),
                     "requires host C compiler")
class NxCdromCandidateTests(unittest.TestCase):
    def test_locked_profile_passes_host_and_freestanding_checks(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = {
            Path(item["path"]).name: item
            for item in lock["repositories"]["roswell"]["patches"]
        }
        self.assertIn(PATCH, entries, "0139 independent optical profile is not locked")
        patch_data = []
        for name in PREREQUISITES + (PATCH,):
            patch_path = ROOT / entries[name]["path"]
            data = patch_path.read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entries[name]["sha256"])
            patch_data.append(data)

        with tempfile.TemporaryDirectory(prefix="owned-nxcdrom-") as temporary:
            source = Path(temporary) / "source"
            source.mkdir()
            subprocess.run(["git", "init", "-q", str(source)], check=True)
            for data in patch_data:
                subprocess.run([
                    "git", "-C", str(source), "apply", "--index",
                    "--include=drivers/storage/class/nxstorage/*",
                    "--include=tests/host/nxstorage-optical/*", "-",
                ], input=data, check=True)
            result = subprocess.run([
                sys.executable,
                str(source / "tests/host/nxstorage-optical/check.py"),
                str(Path(temporary) / "output"),
            ], text=True, capture_output=True, timeout=120,
               env=dict(os.environ, CC=shutil.which("clang") or shutil.which("gcc")))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("optical-profile-plain: 4 groups, 0 failures", result.stdout)
            self.assertIn("optical-profile-sanitized: 4 groups, 0 failures", result.stdout)
            self.assertIn("optical-profile-i386: clean", result.stdout)


if __name__ == "__main__":
    unittest.main()
