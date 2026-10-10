"""Architectural memory-type checks; no firmware payload is a fixture."""
import unittest


class MemoryTypes(unittest.TestCase):
    def test_first_mirror_is_uc_and_upper_is_wp(self):
        from tools.rom_memory_types import mtrr_type, effective_type
        ranges = [(6, 0xFFC000800), (0xFFF80005, 0xFFFF80800)]
        self.assertEqual(mtrr_type(0xFF020000, 0x800, ranges, 36), "UC")
        self.assertEqual(mtrr_type(0xFFFA0000, 0x800, ranges, 36), "WP")
        self.assertEqual(effective_type("WP", "WB", 0), "WP")
        self.assertEqual(effective_type("UC", "WB", 0), "UC")

    def test_disabled_and_ambiguous_mtrrs(self):
        from tools.rom_memory_types import mtrr_type, effective_type
        self.assertEqual(mtrr_type(0xFFFA0000, 0, [], 36), "UC")
        ranges = [(0xFFF80005, 0xFFFF80800), (0xFFF80006, 0xFFFF80800)]
        self.assertEqual(mtrr_type(0xFFFA0000, 0x800, ranges, 36), "UNKNOWN")
        self.assertEqual(effective_type("WP", "WB", 1 << 30), "UNKNOWN")

    def test_pat_index_and_combination(self):
        from tools.rom_memory_types import pat_type, effective_type
        pat = 0x0007040600070406
        self.assertEqual(pat_type(pat, 1), "WB")
        self.assertEqual(pat_type(pat, 1 | 8), "WT")
        self.assertEqual(pat_type(pat, 1 | 16), "UC-")
        self.assertEqual(pat_type(pat, 1 | 16 | 8), "UC")
        self.assertEqual(pat_type(pat, 1 | 128, large=True), "WB")
        self.assertEqual(pat_type(pat, 1 | 4096, large=True), "WB")
        self.assertEqual(effective_type("WB", "WT", 0), "WT")
        self.assertEqual(effective_type("WP", "UC-", 0), "WC")
        self.assertEqual(effective_type("WT", "WP", 0), "WP")
        self.assertEqual(effective_type("WC", "WB", 0), "WC")

    def test_no_fixed_range_inference(self):
        from tools.rom_memory_types import mtrr_type
        self.assertEqual(mtrr_type(0x80000, 0xC00, [], 36), "UNKNOWN")

    def test_incomplete_capture_rejected(self):
        from tools.rom_memory_types import parse_capture
        with self.assertRaises(ValueError):
            parse_capture("== rom-memory-types BEGIN schema=1 ==\n")

    def test_full_capture_joins_actual_page(self):
        from tools.rom_memory_types import parse_capture
        text = "\n".join([
            "== rom-memory-types BEGIN schema=1 ==",
            "# CPU phys_bits=36 edx=00011030",
            "# CONTROL cr0=00000000 cr3=0000f000 cr4=00000010",
            "# MSR index=000000fe value=0000000000000002",
            "# MSR index=000002ff value=0000000000000800",
            "# MSR index=00000277 value=0007040600070406",
            "# MSR index=00000200 value=0000000000000006",
            "# MSR index=00000201 value=0000000ffc000800",
            "# MSR index=00000202 value=00000000fff80005",
            "# MSR index=00000203 value=0000000ffff80800",
            "# PAGE label=kernel va=8403d5e4 pa=ff0205e4 entry=ff020101 large=0",
            "== rom-memory-types END schema=1 status=PASS ==",
        ])
        result = parse_capture(text)
        self.assertEqual(result["pages"][0]["effective_type"], "UC")
        with self.assertRaises(ValueError):
            parse_capture(text.replace("# MSR index=00000203 value=0000000ffff80800", ""))


if __name__ == "__main__":
    unittest.main()
