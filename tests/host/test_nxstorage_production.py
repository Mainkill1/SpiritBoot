"""Run new production code from its exact locked patch, never old body extraction."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


@unittest.skipUnless(shutil.which('clang') or shutil.which('gcc'), 'requires host C compiler')
class NxStorageProductionTests(unittest.TestCase):
    def test_locked_independent_production_sources_pass_owned_checks(self):
        lock = json.loads((ROOT / 'sources/firmware-lock.json').read_text())
        patches = []
        for name in ("0127-independent-storage-primitives.patch", "0129-independent-cache-query-primitive.patch"):
            entry = next(item for item in lock['repositories']['roswell']['patches']
                         if item['path'] == 'patches/roswell/' + name)
            data = (ROOT / entry['path']).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
            patches.append(data)
        with tempfile.TemporaryDirectory(prefix='owned-nxstorage-') as temporary:
            source = Path(temporary) / 'source'
            source.mkdir()
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            for data in patches:
                subprocess.run(['git', '-C', str(source), 'apply', '--index', '-'], input=data, check=True)
            result = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage/check.py'),
                                     str(Path(temporary) / 'output')], text=True,
                                    capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('tests, 0 failures', result.stdout)
            self.assertIn('13 scenarios, 6001 checks', result.stdout)
            self.assertIn('20 passed; 0 failed', result.stdout)
            self.assertIn('production checks passed', result.stdout)
