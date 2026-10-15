# SPDX-License-Identifier: GPL-2.0-only
"""Host checks for the Xbox public kernel contract adapter patch."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/check_kernel_public_contracts.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("kernel_public_contracts", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class KernelPublicContractTests(unittest.TestCase):
    def test_patch_postimage_executes_pci_contract_matrix(self):
        run = subprocess.run(
            [sys.executable, "-B", str(TOOL)],
            check=True,
            capture_output=True,
            text=True,
        )
        result = json.loads(run.stdout)
        self.assertEqual(result["source_mode"], "patch-postimage")
        self.assertEqual(result["pci_transfer_cells"], 16)
        self.assertGreaterEqual(result["behavior_checks"], 50)
        self.assertIn("PciCfgAddress", result["function_sha256"])
        self.assertFalse(result["native_execution_qualified"])

    def test_clock_level_export_contract_rejects_dispatch_level_substitution(self):
        tool = load_tool()
        sources = tool.production_sources()
        sources["interrupt.c"] = sources["interrupt.c"].replace(
            "KeRaiseIrql(CLOCK_LEVEL, &OldIrql)",
            "KeRaiseIrql(DISPATCH_LEVEL, &OldIrql)",
        )
        with self.assertRaisesRegex(ValueError, "CLOCK_LEVEL"):
            tool.validate_static_contracts(sources)

    def test_io_invalid_contract_rejects_double_completion(self):
        tool = load_tool()
        sources = tool.production_sources()
        needle = "IofCompleteRequest(Request, IO_NO_INCREMENT);"
        sources["xbe.c"] = sources["xbe.c"].replace(needle, needle + "\n    " + needle)
        with self.assertRaisesRegex(ValueError, "exactly once"):
            tool.validate_static_contracts(sources)

    def test_io_invalid_contract_preserves_information(self):
        tool = load_tool()
        sources = tool.production_sources()
        needle = "Request->IoStatus.Status = STATUS_INVALID_DEVICE_REQUEST;"
        sources["xbe.c"] = sources["xbe.c"].replace(
            needle, needle + "\n    Request->IoStatus.Information = 0;"
        )
        with self.assertRaisesRegex(ValueError, "preserve IoStatus.Information"):
            tool.validate_static_contracts(sources)

    def test_pci_contract_rejects_allocation_or_private_lock(self):
        tool = load_tool()
        for forbidden in ("ExAllocatePool(4)", "static KSPIN_LOCK PrivateLock;"):
            with self.subTest(forbidden=forbidden):
                sources = tool.production_sources()
                sources["pci.c"] += "\n" + forbidden + "\n"
                with self.assertRaisesRegex(ValueError, "allocation|persistent lock"):
                    tool.validate_static_contracts(sources)

    def test_pci_export_rejects_generic_bus_handler_fallback(self):
        tool = load_tool()
        sources = tool.production_sources()
        sources["xbe.c"] = sources["xbe.c"].replace(
            "PciCfgReadWriteBuffer(BusNumber, SlotNumber, RegisterNumber,\n"
            "                          Buffer, Length, WritePCISpace);",
            "HalGetBusDataByOffset(PCIConfiguration, BusNumber, SlotNumber,\n"
            "                          Buffer, RegisterNumber, Length);",
        )
        with self.assertRaisesRegex(ValueError, "direct PCI adapter"):
            tool.validate_static_contracts(sources)

    def test_pci_adapter_preserves_native_eight_bit_wrapping(self):
        tool = load_tool()
        sources = tool.production_sources()
        sources["pci.c"] = sources["pci.c"].replace(
            "return (BusNumber == 0", "return Slot.u.bits.Reserved ||\n           (BusNumber == 0"
        )
        with self.assertRaisesRegex(ValueError, "8-bit wrapping"):
            tool.validate_static_contracts(sources)


if __name__ == "__main__":
    unittest.main()
