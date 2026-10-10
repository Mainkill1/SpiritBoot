"""Architectural memory-type checks; no firmware payload is a fixture."""
import unittest


def capture():
    records = [
        "== rom-memory-types BEGIN schema=1 ==",
        "# CPU phys_bits=36 edx=00011030",
        "# CONTROL cr0=80000000 cr3=0000f000 cr4=00000010",
        "# MSR index=000000fe value=0000000000000002",
        "# MSR index=000002ff value=0000000000000800",
        "# MSR index=00000277 value=0007040600070406",
        "# MSR index=00000200 value=0000000000000006",
        "# MSR index=00000201 value=0000000ffc000800",
        "# MSR index=00000202 value=00000000fff80005",
        "# MSR index=00000203 value=0000000ffff80800",
        "# PAGE label=kernel va=8403d5e4 pa=ff0205e4 entry=ff020101 large=0",
        "# PAGE label=ram va=83fde000 pa=03fde000 entry=03c000e3 large=1",
        "# PAGE label=ram-cross va=83fdeffe pa=03fdeffe entry=03c000e3 large=1",
        "# PAGE label=ram-cross-next va=83fdf000 pa=03fdf000 entry=03c000e3 large=1",
    ]
    for round in range(17):
        records.append(f"# SAMPLE round={round} calls=32768 overhead=100 kernel=100 ram=100 cross=100 table_kernel=100 table_ram=100 checksum=da090000")
    return "\n".join(records + ["== rom-memory-types END schema=1 status=PASS =="])


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
        text = capture()
        result = parse_capture(text)
        self.assertEqual(result["pages"][0]["effective_type"], "UC")
        with self.assertRaises(ValueError):
            parse_capture(text.replace("# MSR index=00000203 value=0000000ffff80800", ""))

    def test_missing_or_duplicate_samples_and_pages_rejected(self):
        from tools.rom_memory_types import parse_capture
        original = capture()
        page = next(line for line in original.splitlines() if "PAGE label=ram " in line)
        sample = next(line for line in original.splitlines() if "SAMPLE round=0 " in line)
        for index, malformed in enumerate((original.replace(page, ""), original.replace(page, page + "\n" + page),
                          original.replace(sample, ""), original.replace(sample, sample + "\n" + sample),
                          original.replace("calls=32768", "calls=1"))):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    parse_capture(malformed)

    def test_contradictory_mapping_and_paging_mode_rejected(self):
        from tools.rom_memory_types import parse_capture
        original = capture()
        for index, malformed in enumerate((original.replace("pa=ff0205e4", "pa=03fde000"),
                          original.replace("large=1", "large=0"),
                          original.replace("cr0=80000000", "cr0=00000000"),
                          original.replace("cr4=00000010", "cr4=00000030"),
                          original.replace("va=8403d5e4", "va=18403d5e4"))):
            with self.subTest(case=index):
                with self.assertRaises(ValueError):
                    parse_capture(malformed)


if __name__ == "__main__":
    unittest.main()
