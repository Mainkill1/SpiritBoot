#!/usr/bin/env python3
"""Prevent the rejected zero-time ATA settle optimization from returning."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AtaStallCandidateTests(unittest.TestCase):
    @staticmethod
    def _valid_gated_header():
        return (
            "#define ATA_IO_WAIT() KeStallExecutionProcessor(1)\n"
            "PataDeviceSelectWait() {\n"
            " if (NXK_EXPERIMENT_ATA_FORCE_SAFE ||\n"
            "     !NxkQemuAtaDiskTargets ||\n"
            "     (!NXK_EXPERIMENT_ATA_FORCE_ALL &&\n"
            "      !(NxkQemuAtaDiskTargets & 1))) { ATA_IO_WAIT(); return; }\n"
            + " READ_PORT_UCHAR(ChanData->Regs.Control);\n" * 4
            + "}\n#else\n")

    def _run_settle_check(self, header_text, identify_text=None):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            header = source / "drivers/storage/ide/pciidex/pata.h"
            identify = source / "drivers/storage/ide/atapi/dev_identify.c"
            header.parent.mkdir(parents=True)
            identify.parent.mkdir(parents=True)
            header.write_text(header_text)
            identify.write_text(identify_text or (
                "AtaDetectQemuDisk\n"
                "if (DeviceType != DEV_ATA) return;\n"
                "strstr(ModelNumber, \"QEMU\");\n"
                "NxkQemuAtaDiskTargets |= 1;\n"))
            return subprocess.run(
                [sys.executable, str(ROOT / "tools/check_ata_settle.py"),
                 "--source-root", str(source)],
                text=True, capture_output=True)

    def test_rejected_patch_is_not_in_the_firmware_lock(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        paths = [entry["path"] for entry in entries]
        self.assertNotIn("patches/roswell/0152-ata-400ns-status-reads.patch",
                         paths)

    def test_replacement_is_qemu_disk_gated_and_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        path = "patches/roswell/0152-qemu-ata-advanced-controls.patch"
        paths = [entry["path"] for entry in entries]
        self.assertIn(path, paths)
        patch = (ROOT / path).read_text()
        for token in ("AtaDetectQemuDisk", "DeviceType != DEV_ATA",
                      "NxkQemuAtaDiskTargets", "NXK_EXPERIMENT_ATA_FORCE_SAFE",
                      "NXK_EXPERIMENT_ATA_FORCE_ALL", "SB_MENU_ADVANCED",
                      "if (r[7]) out |= SB_Y"):
            self.assertIn(token, patch)
        self.assertIn("!NxkQemuAtaDiskTargets", patch)
        self.assertNotIn(
            '+    "  D-pad: move/edit  A: select  B: back  X: save  '
            'BACK: credits',
            patch)

    def test_rejected_patch_is_preserved_as_non_product_evidence(self):
        rejected = (ROOT / "docs/performance/evidence/forza-map-hotpath-20261015/"
                    "ata-stall/rejected-0152-ata-400ns-status-reads.patch")
        self.assertTrue(rejected.is_file())
        patch = rejected.read_text()
        self.assertIn("READ_PORT_UCHAR((Ctx)->Regs.Control)", patch)
        self.assertIn("ATA_IO_WAIT(ChanData)", patch)

    def test_report_records_emulator_timing_failure_and_rejection(self):
        report = (ROOT / "docs/performance/evidence/forza-map-hotpath-20261015/"
                  "ata-stall/STALL-DELAY-ATTRIBUTION.md").read_text()
        for token in ("REJECTED", "Forza", "zero elapsed", "KeStallExecutionProcessor(1)"):
            self.assertIn(token, report)

    def test_assembled_source_check_requires_a_real_guest_delay(self):
        result = self._run_settle_check(self._valid_gated_header())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_assembled_source_check_rejects_zero_time_status_reads(self):
        result = self._run_settle_check(
            "#define ATA_IO_WAIT(Ctx) do { \\\n"
            " READ_PORT_UCHAR((Ctx)->Regs.Control); \\\n"
            " READ_PORT_UCHAR((Ctx)->Regs.Control); \\\n"
            " READ_PORT_UCHAR((Ctx)->Regs.Control); \\\n"
            " READ_PORT_UCHAR((Ctx)->Regs.Control); \\\n"
            "} while (0)\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("elapsed guest delay", result.stdout + result.stderr)

    def test_assembled_source_check_rejects_atapi_qemu_detection(self):
        result = self._run_settle_check(
            self._valid_gated_header(),
            "AtaDetectQemuDisk\nstrstr(ModelNumber, \"QEMU\");\n"
            "NxkQemuAtaDiskTargets |= 1;\n")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DeviceType != DEV_ATA", result.stdout + result.stderr)

    def test_release_ci_checks_the_assembled_ata_settle_path(self):
        workflow = (ROOT / ".github/workflows/firmware.yml").read_text()
        self.assertIn("tools/check_ata_settle.py --source-root", workflow)


if __name__ == "__main__":
    unittest.main()
