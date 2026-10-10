"""Exercise offline page attribution; overlapping symbols must not create RAM."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest


TOOL = Path(__file__).resolve().parents[2] / "tools/kernel_page_atlas.py"
BASE = 0x84000000


class PageAtlasTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # A real PE32 section table, with two mapped sections and a header page.
        pe = bytearray(1024)
        pe[:2] = b"MZ"
        struct.pack_into("<I", pe, 60, 128)
        pe[128:132] = b"PE\0\0"
        struct.pack_into("<HH", pe, 132, 0x14c, 2)
        struct.pack_into("<H", pe, 148, 224)
        struct.pack_into("<H", pe, 152, 0x10b)
        struct.pack_into("<I", pe, 180, BASE)
        struct.pack_into("<I", pe, 184, 4096)
        struct.pack_into("<II", pe, 208, 16384, 512)
        self.sections = []
        for index, (name, rva, size, flags) in enumerate([
                (".text", 4096, 6000, 0x60000020),
                (".data", 12288, 200, 0xc0000040)]):
            offset = 376 + index * 40
            pe[offset:offset+8] = name.encode().ljust(8, b"\0")
            struct.pack_into("<II", pe, offset+8, size, rva)
            struct.pack_into("<I", pe, offset+36, flags)
            self.sections.append(dict(name=name, start=BASE+rva,
                                      virtual_bytes=size, flags=flags,
                                      executable=name == ".text",
                                      discardable=False))
        (self.root / "kernel.exe").write_bytes(pe)
        (self.root / "shipped.exe").write_bytes(pe)
        (self.root / "flash.bin").write_bytes(b"fixture ROM")
        self.identity = dict(source_tree="a"*40,
                             pe_sha256=hashlib.sha256(pe).hexdigest(),
                             flash_sha256=hashlib.sha256(b"fixture ROM").hexdigest())
        self.inventory = dict(schema=2, **self.identity,
                              shipped_pe_sha256=self.identity["pe_sha256"], sections=self.sections,
                              functions_and_input_extents=[
                                  self.extent("foo", 8176, 48),
                                  self.extent("foo.clone", 8176, 48),
                                  self.extent("bar", 4352, 128),
                                  self.extent("zero_alias", 8176, 0)],
                              sizeof_proved_tables=[])
        self.manifest = dict(status="complete", source_tree="a"*40,
                             flash_sha256=self.identity["flash_sha256"])
        self.capture = "\n".join(json.dumps(row) for row in [
            dict(type="header", schema=1, max_records=8),
            dict(type="tb", pc=hex(BASE+8208), code_sha256="b"*64,
                 instructions=4, translations=1, executions=3),
            dict(type="tb", pc="0x1234", code_sha256="c"*64,
                 instructions=5, translations=1, executions=2),
            dict(type="complete", dropped_translations=0,
                 untracked_executions=0, untracked_weight=0)])
        self.meta = dict(schema=1, **self.identity, phase="whole-process",
                         window=dict(kind="whole-process"), xemu_sha256="d"*64)

    @staticmethod
    def extent(name, rva, size):
        return dict(name=name, symbols=[name], section=".text", va=BASE+rva,
                    extent_end=BASE+rva+size, bytes=size,
                    compiler_extent_bytes=size,
                    length_kind="COFF compiler input-section extent",
                    source_attribution_confidence="fixture",
                    source_definition_candidates=["owned.c"])

    def run_tool(self):
        for name, data in [("inventory.json", self.inventory),
                           ("build.json", self.manifest)]:
            (self.root/name).write_text(json.dumps(data))
        (self.root/"capture.ndjson").write_text(self.capture)
        self.meta["capture"] = "capture.ndjson"
        self.meta["capture_sha256"] = hashlib.sha256(self.capture.encode()).hexdigest()
        (self.root/"capture.json").write_text(json.dumps(self.meta))
        return subprocess.run([sys.executable, str(TOOL),
                               "--inventory", str(self.root/"inventory.json"),
                               "--build", str(self.root/"build.json"),
                               "--kernel", str(self.root/"kernel.exe"),
                               "--shipped-kernel", str(self.root/"shipped.exe"),
                               "--flash", str(self.root/"flash.bin"),
                               "--capture", str(self.root/"capture.json"),
                               "--output", str(self.root/"report.json")],
                              text=True, capture_output=True)

    def report(self):
        result = self.run_tool()
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((self.root/"report.json").read_text())

    def test_cross_page_aliases_and_padding_conserve_bytes(self):
        report = self.report()
        pages = {p["rva"]: p for p in report["pages"]}
        self.assertEqual(len(pages), 4)
        self.assertEqual(pages[4096]["known_union_bytes"], 144)
        self.assertEqual(pages[8192]["known_union_bytes"], 32)
        self.assertEqual(pages[8192]["tail_padding_bytes"], 2192)
        self.assertEqual(pages[8192]["owners"][0]["symbols"],
                         ["foo", "foo.clone", "zero_alias"])
        for page in pages.values():
            self.assertEqual(page["known_union_bytes"] + page["unknown_bytes"]
                             + page["tail_padding_bytes"], 4096)
            self.assertEqual(page["physical_backing"], "unknown")
        self.assertEqual(pages[12288]["placement"], "ineligible-mutable")

    def test_tb_entry_weight_and_outside_image_are_not_cpu_time(self):
        report = self.report()
        page = next(p for p in report["pages"] if p["rva"] == 8192)
        self.assertEqual(page["phase_weights"], {"whole-process": 12})
        self.assertEqual(report["coverage"][0]["outside_image_weight"], 10)
        self.assertEqual(report["coverage"][0]["total_weight"], 22)
        self.assertIsNone(report["candidate_cold_page"])
        self.assertIsNone(report["candidate_hot_page"])
        self.assertIn("phase", report["confidence_limits"])

    def test_mismatched_tree_pe_and_flash_are_rejected(self):
        for field, value in [("source_tree", "e"*40),
                             ("pe_sha256", "e"*64),
                             ("flash_sha256", "e"*64)]:
            with self.subTest(field=field):
                self.meta[field] = value
                result = self.run_tool()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.root/"report.json").exists())
                self.meta[field] = self.identity[field]

    def test_truncated_capture_is_rejected(self):
        self.capture = self.capture.rsplit("\n", 1)[0]
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/"report.json").exists())

    def test_unattested_title_phase_is_rejected(self):
        self.meta["phase"] = "title"
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/"report.json").exists())

    def test_extent_outside_its_section_is_rejected(self):
        self.inventory["functions_and_input_extents"][0]["extent_end"] = BASE+20000
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root/"report.json").exists())

    def test_sidecar_cannot_relabel_whole_process_as_title(self):
        self.meta.update(phase="title", window=dict(kind="bounded-recording",
                                                  start="armed", end="disarmed",
                                                  evidence_sha256="f"*64))
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("producer", result.stderr)

    def test_declared_bounded_title_capture_selects_observed_hot_page_only(self):
        window = dict(kind="bounded-recording", start="armed", end="disarmed",
                      evidence_sha256="f"*64)
        rows = [json.loads(line) for line in self.capture.splitlines()]
        rows[0].update(phase="title", window=window)
        self.capture = "\n".join(json.dumps(row) for row in rows)
        self.meta.update(phase="title", window=window)
        report = self.report()
        self.assertEqual(report["candidate_hot_page"], 8192)
        self.assertIsNone(report["candidate_cold_page"])

    def test_overlapping_extents_count_union_not_sum(self):
        self.inventory["functions_and_input_extents"].append(self.extent("shared", 8192, 64))
        report = self.report()
        page = next(p for p in report["pages"] if p["rva"] == 8192)
        self.assertEqual(page["known_union_bytes"], 64)
        self.assertEqual(sum(p["overlap_bytes"] for p in page["owners"]), 96)

    def test_overflow_weight_remains_visible_and_incomplete(self):
        rows = [json.loads(line) for line in self.capture.splitlines()]
        rows[0]["max_records"] = 2
        rows[-1].update(dropped_translations=1, untracked_executions=4,
                        untracked_weight=20)
        self.capture = "\n".join(json.dumps(row) for row in rows)
        coverage = self.report()["coverage"][0]
        self.assertEqual(coverage["total_weight"], 42)
        self.assertEqual(coverage["untracked_weight"], 20)
        self.assertFalse(coverage["complete_coverage"])

    def test_forged_section_size_and_inferred_symbol_span_are_rejected(self):
        self.sections[0]["virtual_bytes"] = 7000
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("section ledger", result.stderr)
        self.sections[0]["virtual_bytes"] = 6000
        self.inventory["functions_and_input_extents"][0]["length_kind"] = "next named symbol"
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("certified compiler extent", result.stderr)

    def test_runtime_section_cannot_be_omitted_or_reclassified(self):
        self.sections.pop()
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shipped", result.stderr)

    def test_shipped_flags_cannot_be_replaced_with_consistent_booleans(self):
        self.sections[1].update(flags=0x40000040)
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shipped", result.stderr)

    def test_shipped_pe_identity_is_required(self):
        (self.root/"shipped.exe").write_bytes(b"wrong image")
        result = self.run_tool()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("shipped", result.stderr)

    def test_crlf_capture_verifies_original_bytes(self):
        self.capture = self.capture.replace("\n", "\r\n")
        report = self.report()
        self.assertEqual(report["coverage"][0]["total_weight"], 22)


if __name__ == "__main__":
    unittest.main()
