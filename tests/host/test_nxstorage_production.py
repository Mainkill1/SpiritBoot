"""Run new production code from its exact locked patch, never old body extraction."""
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


@unittest.skipUnless(shutil.which('clang') or shutil.which('gcc'), 'requires host C compiler')
class NxStorageProductionTests(unittest.TestCase):
    def test_locked_independent_production_sources_pass_owned_checks(self):
        lock = json.loads((ROOT / 'sources/firmware-lock.json').read_text())
        patches = []
        for name in ("0127-independent-storage-primitives.patch", "0129-independent-cache-query-primitive.patch",
                     "0130-independent-geometry-owner-adapter.patch",
                     "0131-independent-cache-publication-primitive.patch",
                     "0132-nxstorage-freestanding-gcc-checks.patch",
                     "0133-independent-zero-domain-mdl.patch",
                     "0134-independent-native-packet-primitive.patch",
                     "0135-independent-sense-header-primitive.patch",
                     "0138-independent-nxdisk-owner.patch",
                     "0139-independent-nxcdrom-profile.patch",
                     "0140-independent-native-storage-adapter.patch"):
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
                subprocess.run(['git', '-C', str(source), 'apply', '--index',
                                '--include=drivers/storage/class/nxstorage/*',
                                '--include=tests/host/nxstorage/*',
                                '--include=tests/host/nxstorage-sense/*', '-'], input=data, check=True)
            result = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage/check.py'),
                                     str(Path(temporary) / 'output')], text=True,
                                    capture_output=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('tests, 0 failures', result.stdout)
            self.assertIn('13 scenarios, 6001 checks', result.stdout)
            self.assertIn('20 passed; 0 failed', result.stdout)
            self.assertIn('16 adapter scenarios, 61973 checks', result.stdout)
            self.assertIn('32 passed; 0 failed', result.stdout)
            self.assertIn('production checks passed', result.stdout)
            packet = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage/check_packet.py'),
                                     str(Path(temporary) / 'packet-output')], text=True,
                                    capture_output=True, timeout=120,
                                    env=dict(os.environ, CC=shutil.which('clang') or shutil.which('gcc')))
            self.assertEqual(packet.returncode, 0, packet.stdout + packet.stderr)
            self.assertIn('packet-plain: ', packet.stdout)
            self.assertIn('packet-sanitized: ', packet.stdout)
            sense = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage-sense/check.py')],
                                   text=True, capture_output=True, timeout=120,
                                   env=dict(os.environ, CC=shutil.which('clang') or shutil.which('gcc')))
            self.assertEqual(sense.returncode, 0, sense.stdout + sense.stderr)
            self.assertEqual(sense.stdout.count('sense_header: all tests passed'), 2)
            owner = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage/check_owner.py'),
                                    str(Path(temporary) / 'owner-output')], text=True,
                                   capture_output=True, timeout=120,
                                   env=dict(os.environ, CC=shutil.which('clang') or shutil.which('gcc')))
            self.assertEqual(owner.returncode, 0, owner.stdout + owner.stderr)
            self.assertIn('nxdisk-owner-plain: 9 groups, 0 failures', owner.stdout)
            self.assertIn('nxdisk-owner-sanitized: 9 groups, 0 failures', owner.stdout)
            adapter = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage/check_adapter.py'),
                                      str(Path(temporary) / 'adapter-output')], text=True,
                                     capture_output=True, timeout=120,
                                     env=dict(os.environ, CC=shutil.which('clang') or shutil.which('gcc')))
            self.assertEqual(adapter.returncode, 0, adapter.stdout + adapter.stderr)
            self.assertIn('adapter-plain: 25 adapter groups, 0 failures', adapter.stdout)
            self.assertIn('adapter-sanitized: 25 adapter groups, 0 failures', adapter.stdout)

            driver = (source / 'drivers/storage/class/nxstorage/driver.c').read_text()
            self.assertIn('ZwCreateDirectoryObject(&context->object_directory', driver)
            self.assertIn('ZwMakeTemporaryObject(context->object_directory)', driver)
            self.assertLess(driver.index('ZwCreateDirectoryObject(&context->object_directory'),
                            driver.index('NxNativeCreateClassDevice(context->driver'))
            self.assertIn('driver->MajorFunction[IRP_MJ_PNP]=NxNativeDispatchPnp', driver)
