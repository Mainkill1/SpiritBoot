# SPDX-License-Identifier: GPL-2.0-or-later
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rclass_gate import build_forza_plan, build_input_probe_plan, score_evidence


def image(path: Path, *, world=True, menu=None):
    im = Image.new("RGB", (640, 480), (6, 6, 6))
    d = ImageDraw.Draw(im)
    if menu:
        d.rectangle((50, 50, 590, 430), fill=(230, 230, 220))
        d.text((80, 80), menu, fill=(10, 10, 10))
    if world:
        d.rectangle((25, 40, 615, 220), fill=(100, 150, 210))
        d.polygon([(0, 480), (215, 230), (425, 230), (640, 480)], fill=(85, 75, 65))
        for x in range(20, 620, 25):
            d.line((x, 220, x // 2 + 160, 470), fill=(20 + x % 180, 90, 30), width=3)
        d.rectangle((30, 35, 140, 105), outline=(255, 255, 255), width=3)
    im.save(path)


class RouteContractTests(unittest.TestCase):
    def test_short_input_probe_compares_face_a_and_right_trigger(self):
        plan = build_input_probe_plan()
        diagnostics = [s.get("diagnosticId") for s in plan if s["type"] == "diagnostic"]
        self.assertIn("forza-probe-A-hold", diagnostics)
        self.assertIn("forza-probe-RT-hold", diagnostics)
        self.assertLess(diagnostics.index("forza-probe-A-hold"), diagnostics.index("forza-probe-RT-hold"))
        shots = [s.get("name") for s in plan if s["type"] == "screenshot"]
        self.assertIn("input-probe-after-A", shots)
        self.assertIn("input-probe-after-RT", shots)
        self.assertEqual(plan[-1]["type"], "quit")

    def test_r_class_route_is_fresh_bounded_and_drives_continuously(self):
        plan = build_forza_plan()
        diagnostics = [s.get("diagnosticId") for s in plan if s["type"] == "diagnostic"]
        class_select = diagnostics.index("forza-class-start")
        confirm = diagnostics.index("forza-A-class-confirm")
        self.assertEqual(diagnostics[class_select + 1:confirm], ["forza-DPadRight"] * 5)
        self.assertEqual(sum(x == "forza-guided-route" for x in diagnostics), 1)
        self.assertLess(diagnostics.index("forza-blockstats-load-start"),
                        diagnostics.index("forza-guided-route"))
        self.assertLess(diagnostics.index("forza-guided-route"),
                        diagnostics.index("forza-blockstats-route-end"))
        self.assertNotIn("forza-A-race-confirm", diagnostics)
        self.assertNotIn("forza-blockstats-race-ready", diagnostics)
        self.assertNotIn("forza-blockstats-route-start", diagnostics)
        self.assertFalse(any((row.get("name") or "").startswith("load-")
                             and row.get("name") != "load-start" for row in plan))
        self.assertEqual(plan[-1]["type"], "quit")
        self.assertFalse(any(s["type"] == "wait" and s.get("delayMs", 0) <= 0 for s in plan))
        self.assertLessEqual(sum(s.get("delayMs", 0) for s in plan), 240_000)


class EvidenceScoreTests(unittest.TestCase):
    def make(self):
        td = tempfile.TemporaryDirectory()
        root = Path(td.name)
        (root / "screenshots").mkdir()
        return td, root

    def write_common(self, root, *, status="completed", exit_code=0, qemu="", failed=0, invalid=0):
        (root / "result.json").write_text(json.dumps({
            "status": status, "durationMs": 180000, "exitCode": exit_code,
            "crash": {"Crashed": status != "completed"},
        }))
        (root / "qemu.log").write_text(qemu)
        (root / "blockstats-summary.json").write_text(json.dumps({
            "deltas": [{"from": "race-start", "to": "route-end", "devices": {
                "ide0-hd0": {"rd_operations": 200, "rd_bytes": 8_000_000,
                    "failed_rd_operations": failed, "invalid_rd_operations": invalid},
                "ide0-cd1": {"rd_operations": 10, "rd_bytes": 500_000,
                    "failed_rd_operations": 0, "invalid_rd_operations": 0},
            }}]
        }))
        actions = [
            {"action": "guided_route", "label": "route-end",
             "started_utc": "2026-10-18T00:00:00Z",
             "finished_utc": "2026-10-18T00:00:35Z"},
        ]
        (root / "actions.json").write_text(json.dumps(actions))
        (root / "ocr.json").write_text(json.dumps({"menu-main": "MAIN MENU ARCADE RACE", "class-r": "SELECT CAR CLASS CLASS R"}))
        (root / "route-metrics.json").write_text(json.dumps({
            "max_speed_mph": 96,
            "minimap_displacement_pixels": 28.5,
            "observations": 8,
            "readiness_wait_ms": 4800,
            "ready_guide_pixels": 42,
            "ready_guide_observations": 2,
        }))

    def test_complete_release_run_passes_all_dimensions(self):
        td, root = self.make()
        try:
            self.write_common(root)
            image(root / "screenshots" / "menu-main.png", menu="MAIN MENU")
            image(root / "screenshots" / "class-r.png", menu="SELECT CAR CLASS R")
            for i in range(8): image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertTrue(report["pass"])
            self.assertTrue(report["checks"]["world_completeness"]["pass"])
            self.assertEqual(report["checks"]["read_errors"]["failed_or_invalid"], 0)
            self.assertEqual(report["timing"]["route_seconds"], 35.0)
            self.assertTrue(report["checks"]["route_readiness"]["pass"])
        finally:
            td.cleanup()

    def test_joined_main_menu_ocr_token_is_accepted(self):
        td, root = self.make()
        try:
            self.write_common(root)
            (root / "ocr.json").write_text(json.dumps({
                "menu-main": "MAINMENU ARCADE RACE",
                "class-r": "SELECT CAR CLASS CLASS R",
            }))
            image(root / "screenshots" / "menu-main.png", menu="MAIN MENU")
            image(root / "screenshots" / "class-r.png", menu="SELECT CAR CLASS R")
            for i in range(8): image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertTrue(report["checks"]["menu_and_route_identity"]["main_menu_seen"])
            self.assertTrue(report["checks"]["menu_and_route_identity"]["pass"])
            self.assertTrue(report["pass"])
        finally:
            td.cleanup()

    def test_missing_world_is_rejected_even_when_process_and_reads_succeed(self):
        td, root = self.make()
        try:
            self.write_common(root)
            image(root / "screenshots" / "menu-main.png", menu="MAIN MENU")
            image(root / "screenshots" / "class-r.png", menu="SELECT CAR CLASS R")
            for i in range(8): image(root / "screenshots" / f"route-{i:02}.png", world=i not in (3, 4))
            report = score_evidence(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["checks"]["world_completeness"]["pass"])
            self.assertGreaterEqual(report["checks"]["world_completeness"]["bad_frames"], 2)
        finally:
            td.cleanup()

    def test_wrong_car_class_is_rejected(self):
        td, root = self.make()
        try:
            self.write_common(root)
            (root / "ocr.json").write_text(json.dumps({"menu-main": "MAIN MENU", "class-r": "SELECT CAR CLASS CLASS D"}))
            image(root / "screenshots" / "menu-main.png", menu="MAIN MENU")
            image(root / "screenshots" / "class-r.png", menu="SELECT CAR CLASS D")
            for i in range(8): image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["checks"]["menu_and_route_identity"]["pass"])
        finally:
            td.cleanup()

    def test_stalled_route_is_rejected_even_when_frames_are_rendered(self):
        td, root = self.make()
        try:
            self.write_common(root)
            (root / "route-metrics.json").write_text(json.dumps({
                "max_speed_mph": 47,
                "minimap_displacement_pixels": 1.4,
                "observations": 8,
                "readiness_wait_ms": 4000,
                "ready_guide_pixels": 30,
            }))
            for i in range(8): image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["checks"]["route_progress"]["pass"])
        finally:
            td.cleanup()

    def test_route_never_reaching_streaming_speed_is_rejected(self):
        td, root = self.make()
        try:
            self.write_common(root)
            (root / "route-metrics.json").write_text(json.dumps({
                "max_speed_mph": 39,
                "minimap_displacement_pixels": 30,
                "observations": 8,
                "readiness_wait_ms": 4000,
                "ready_guide_pixels": 30,
            }))
            for i in range(8): image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["checks"]["route_progress"]["pass"])
        finally:
            td.cleanup()

    def test_route_without_strong_consecutive_readiness_evidence_is_rejected(self):
        td, root = self.make()
        try:
            self.write_common(root)
            metrics = json.loads((root / "route-metrics.json").read_text())
            metrics["ready_guide_pixels"] = 31
            (root / "route-metrics.json").write_text(json.dumps(metrics))
            for i in range(8):
                image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertFalse(report["pass"])
            self.assertFalse(report["checks"]["route_readiness"]["pass"])
        finally:
            td.cleanup()

    def test_route_with_missing_or_late_readiness_evidence_is_rejected(self):
        for readiness in (None, 60001):
            with self.subTest(readiness=readiness):
                td, root = self.make()
                try:
                    self.write_common(root)
                    metrics = json.loads((root / "route-metrics.json").read_text())
                    metrics["readiness_wait_ms"] = readiness
                    (root / "route-metrics.json").write_text(json.dumps(metrics))
                    for i in range(8):
                        image(root / "screenshots" / f"route-{i:02}.png")
                    report = score_evidence(root)
                    self.assertFalse(report["checks"]["route_readiness"]["pass"])
                    self.assertFalse(report["pass"])
                finally:
                    td.cleanup()

    def test_short_drive_cannot_be_hidden_by_a_long_readiness_wait(self):
        td, root = self.make()
        try:
            self.write_common(root)
            metrics = json.loads((root / "route-metrics.json").read_text())
            metrics["readiness_wait_ms"] = 40000
            (root / "route-metrics.json").write_text(json.dumps(metrics))
            actions = json.loads((root / "actions.json").read_text())
            actions[0]["finished_utc"] = "2026-10-18T00:00:50Z"
            (root / "actions.json").write_text(json.dumps(actions))
            for i in range(8):
                image(root / "screenshots" / f"route-{i:02}.png")
            report = score_evidence(root)
            self.assertFalse(report["checks"]["route_timing"]["pass"])
            self.assertEqual(report["timing"]["drive_seconds"], 10.0)
        finally:
            td.cleanup()

    def test_crash_corruption_and_read_errors_each_fail(self):
        for kwargs in [
            {"status": "completed", "exit_code": -1073741819},
            {"qemu": "blk_update_request: I/O error"},
            {"failed": 1},
        ]:
            with self.subTest(kwargs=kwargs):
                td, root = self.make()
                try:
                    self.write_common(root, **kwargs)
                    image(root / "screenshots" / "menu-main.png", menu="MAIN MENU")
                    image(root / "screenshots" / "class-r.png", menu="SELECT CAR CLASS R")
                    for i in range(8): image(root / "screenshots" / f"route-{i:02}.png")
                    self.assertFalse(score_evidence(root)["pass"])
                finally:
                    td.cleanup()


class InputAdapterContractTests(unittest.TestCase):
    def test_owned_adapter_has_bounded_chord_with_reverse_release(self):
        cs = (ROOT / "route_input.cs").read_text()
        ps = (ROOT / "route_actions.ps1").read_text()
        self.assertIn("PressChord", cs)
        self.assertIn("holdMs>30000", cs)
        self.assertIn("for(int i=down-1;i>=0;i--)", cs)
        self.assertIn("action -ceq 'chord'", ps)
        self.assertIn("[DoaOwnedInput]::PressChord", ps)

    def test_guided_route_holds_accelerator_and_retains_frames(self):
        cs = (ROOT / "route_input.cs").read_text()
        ps = (ROOT / "route_actions.ps1").read_text()
        self.assertIn("DriveGuided", cs)
        self.assertIn("RTrigger=0x18", cs)
        self.assertIn("finally { if(steerDown)", cs)
        self.assertIn("if(throttleDown) Send(RTrigger,false,false)", cs)
        self.assertIn("route-live-", cs)
        self.assertIn("route-telemetry.jsonl", cs)
        self.assertIn("ReadyTimeoutMs=60000", cs)
        self.assertIn("readyConsecutive>=2", cs)
        self.assertIn("if(count>=32)", cs)
        self.assertIn("StartMenuPixels", cs)
        self.assertIn("menuConsecutive>=2", cs)
        self.assertIn("elapsed>ReadyTimeoutMs", cs)
        self.assertIn("readiness_wait_ms", cs)
        self.assertLess(cs.index("readyConsecutive>=2"),
                        cs.index("Send(RTrigger,false,true)"))
        self.assertIn("'guided_route'", ps)
        self.assertIn("[DoaOwnedInput]::DriveGuided", ps)


if __name__ == "__main__":
    unittest.main()
