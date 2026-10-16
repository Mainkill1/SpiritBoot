#!/usr/bin/env python3
"""Lock the protocol-equivalent Xbox ATA 400 ns settle path."""
import hashlib
import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class AtaStallCandidateTests(unittest.TestCase):
    def test_patch_follows_cache_capture_and_is_locked(self):
        lock = json.loads((ROOT / "sources/firmware-lock.json").read_text())
        entries = lock["repositories"]["roswell"]["patches"]
        paths = [entry["path"] for entry in entries]
        index = paths.index("patches/roswell/0152-ata-400ns-status-reads.patch")
        self.assertEqual(paths[index - 1],
                         "patches/roswell/0151-ata-cache-capture-hotpath.patch")
        data = (ROOT / entries[index]["path"]).read_bytes()
        self.assertEqual(hashlib.sha256(data).hexdigest(),
                         entries[index]["sha256"])

    def test_xbox_uses_four_alternate_status_reads(self):
        patch = (ROOT / "patches/roswell/0152-ata-400ns-status-reads.patch").read_text()
        macro = patch[patch.index("#if defined(SARCH_XBOX)"):
                      patch.index("#else", patch.index("#if defined(SARCH_XBOX)"))]
        self.assertEqual(macro.count("READ_PORT_UCHAR((Ctx)->Regs.Control)"), 4)
        self.assertIn("#define ATA_IO_WAIT(Ctx) KeStallExecutionProcessor(1)", patch)
        self.assertEqual(patch.count("ATA_IO_WAIT(ChanData)"), 4)

    def test_native_report_records_protocol_and_adjacent_control(self):
        report = (ROOT / "docs/performance/evidence/forza-map-hotpath-20261015/"
                  "ata-stall/STALL-DELAY-ATTRIBUTION.md").read_text()
        for token in ("Alternate Status", "without acknowledging", "B3",
                      "S3", "zero reported failures"):
            self.assertIn(token, report)


if __name__ == "__main__":
    unittest.main()
