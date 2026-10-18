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
                     "0140-independent-native-storage-adapter.patch",
                     "0141-lower-cache-integration.patch",
                     "0143-native-storage-submit-hotpath.patch",
                     "0146-forza-map-queue-depth.patch",
                     "0147-retained-pata-sg-workspace.patch",
                     "0148-native-storage-qd12-hotpath.patch",
                     "0150-native-packet-prepare-hotpath.patch",
                     "0151-ata-cache-capture-hotpath.patch",
                     "0157-forza-payload-association-qualification.patch",
                     "0158-reset-media-lifetime.patch",
                     "0160-optical-qd12-admission.patch",
                     "0161-defer-native-child-completion.patch",
                     "0162-transient-native-envelope-growth.patch",
                     "0163-queue-saturated-native-admission.patch",
                     "0164-compact-data-overflow-envelopes.patch",
                     "0165-cancel-before-native-admission.patch",
                     "0166-sealed-rundown-notifications.patch",
                     "0167-skip-inactive-native-slots.patch",
                     "0168-coalesce-native-adapter-bookkeeping.patch"):
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
            self.assertIn('34 passed; 0 failed', result.stdout)
            self.assertIn('production checks passed', result.stdout)
            self.assertIn('differential observations; 8 lifecycle capacities passed', result.stdout)
            packet = subprocess.run([sys.executable, str(source / 'tests/host/nxstorage/check_packet.py'),
                                     str(Path(temporary) / 'packet-output')], text=True,
                                    capture_output=True, timeout=120,
                                    env=dict(os.environ, CC=shutil.which('clang') or shutil.which('gcc')))
            self.assertEqual(packet.returncode, 0, packet.stdout + packet.stderr)
            self.assertIn('packet-plain: 10 groups, 0 failures', packet.stdout)
            self.assertIn('packet-sanitized: 10 groups, 0 failures', packet.stdout)
            if 'packet-msan:' in packet.stdout and 'SKIP' not in packet.stdout:
                self.assertIn('packet-msan: 10 groups, 0 failures', packet.stdout)
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
            self.assertIn('adapter-plain: 42 adapter groups, 0 failures', adapter.stdout)
            self.assertIn('adapter-sanitized: 42 adapter groups, 0 failures', adapter.stdout)

            driver = (source / 'drivers/storage/class/nxstorage/driver.c').read_text()
            self.assertIn('ZwCreateDirectoryObject(&context->object_directory', driver)
            self.assertIn('ZwMakeTemporaryObject(context->object_directory)', driver)
            self.assertLess(driver.index('ZwCreateDirectoryObject(&context->object_directory'),
                            driver.index('NxNativeCreateClassDevice(context->driver'))
            self.assertIn('driver->MajorFunction[IRP_MJ_PNP]=NxNativeDispatchPnp', driver)
            self.assertIn('NX_NATIVE_DISK_SLOTS = 16, NX_NATIVE_CDROM_SLOTS = 16', driver)
            self.assertIn('init.SlotCount=NX_NATIVE_DISK_SLOTS;', driver)
            self.assertIn('NX_NATIVE_CDROM_SLOTS);', driver)

    def test_locked_lower_cache_route_uses_real_transaction_facts(self):
        lock = json.loads((ROOT / 'sources/firmware-lock.json').read_text())
        entry = next(item for item in lock['repositories']['roswell']['patches']
                     if item['path'] == 'patches/roswell/0141-lower-cache-integration.patch')
        data = (ROOT / entry['path']).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(), entry['sha256'])
        patch = data.decode()
        added = '\n'.join(line[1:] for line in patch.splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        self.assertIn('#include "native_hook.inc"', patch)
        self.assertIn('case StorageDeviceWriteCacheProperty:', patch)
        self.assertIn('NxAtapiWriteCachePropertyEndpoint(DevExt, Irp, IoStack)', patch)
        self.assertIn('*ForwardToFdo = FALSE; /* This PDO owns local endpoint completion. */', patch)
        self.assertIn('Irp->IoStatus.Information = 0;', patch)
        self.assertIn('PDO dispatch remains the sole completion owner', patch)
        self.assertIn('IoCompleteRequest(Irp, IO_NO_INCREMENT);', patch)
        self.assertIn('IoReleaseRemoveLock(&DevExt->Common.RemoveLock, Irp); /* Common epilogue. */', patch)
        self.assertIn('NxAtapiCacheTrack(DevExt, Request)', patch)
        self.assertIn('NxAtapiCacheStart(', patch)
        self.assertIn('NxAtapiCacheStoreResult(Request, NxAtapiCacheRawResult(Request))', patch)
        self.assertIn('NxAtapiCachePublish(DevExt, IdentityResult)', patch)
        self.assertIn('NxAtapiCachePublish(DevExt, NxAtapiCacheLoadResult(Request))', patch)
        self.assertIn('AtaPortRevokeCachePublication(PortData, MAXULONG)', patch)
        self.assertIn('C_ASSERT(sizeof(((PATA_DEVICE_REQUEST)0)->NxCacheWriter) == 12)', patch)
        self.assertIn('actual_pdo_write_cache_endpoint', patch)
        self.assertNotIn('NxAtapiCachePublishIdentity', added)
        self.assertNotIn('nx_lcq_result_copy(&w,SRB_STATUS_SUCCESS', added)
        self.assertNotIn('refresh_cache_qualification', added)
        self.assertNotIn('cache_epoch', added)
        self.assertNotIn('core.config.cache=', added)
