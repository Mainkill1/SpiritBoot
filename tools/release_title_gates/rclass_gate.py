#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Release-only automated title route and evidence scoring for SpiritBoot."""
from __future__ import annotations

from datetime import datetime
import json
import math
import re
from pathlib import Path
from typing import Any
from PIL import Image, ImageFilter, ImageStat

ERROR_PATTERNS = re.compile(
    r"(?i)(?:blk_update_request.*i/o error|input/output error|guest.*(?:read|disk).*error|"
    r"ata.*(?:error|failed)|fatx.*(?:corrupt|error)|unhandled.*exception|assertion.*failed)"
)


def step(kind: str, **kwargs: Any) -> dict[str, Any]:
    row = {"type": kind, "delayMs": 0, "button": None, "durationMs": 100,
           "name": None, "diagnosticId": None, "condition": None,
           "timeoutMs": 10000, "pollIntervalMs": 100}
    row.update(kwargs)
    return row


def build_forza_plan() -> list[dict[str, Any]]:
    """Cold-boot the established profile, select default track and R class, then drive."""
    p = [step("wait", delayMs=60000), step("diagnostic", diagnosticId="forza-context")]
    # Boot/profile/main/default-event traversal. Each delay is bounded and every
    # important state is retained for objective post-run classification.
    for wait, name in [(0, "boot-continue"), (12000, "profile-open"),
                       (20000, "profile-confirm"), (15000, "main-confirm"),
                       (7000, "event-confirm")]:
        if wait: p.append(step("wait", delayMs=wait))
        p.append(step("screenshot", name=name))
        p.append(step("diagnostic", diagnosticId="forza-A"))
    p += [step("wait", delayMs=7000), step("screenshot", name="class-start"),
          step("diagnostic", diagnosticId="forza-class-start")]
    # Forza's class strip is D, C, B, A, S, R. Five right presses from the
    # default D tile deterministically select R without depending on saved state.
    for i in range(1, 6):
        p += [step("diagnostic", diagnosticId="forza-DPadRight"),
              step("wait", delayMs=400), step("screenshot", name=f"class-{i}")]
    p += [step("screenshot", name="class-r"),
          step("diagnostic", diagnosticId="forza-A-class-confirm"),
          step("wait", delayMs=7000), step("screenshot", name="r-car"),
          step("diagnostic", diagnosticId="forza-A-car-confirm"),
          step("wait", delayMs=7000), step("screenshot", name="assists"),
          step("diagnostic", diagnosticId="forza-A-assists-confirm"),
          step("diagnostic", diagnosticId="forza-blockstats-load-start")]
    for i in range(0, 41, 2):
        if i:
            p.append(step("wait", delayMs=2000))
        p.append(step("screenshot", name=f"load-{i:02}"))
    p += [step("diagnostic", diagnosticId="forza-blockstats-race-ready"),
          step("diagnostic", diagnosticId="forza-A-race-confirm"),
          step("wait", delayMs=5000), step("screenshot", name="route-00"),
          step("diagnostic", diagnosticId="forza-blockstats-route-start")]
    # Hold full throttle continuously while a deterministic image-feedback
    # loop applies short digital steering pulses toward Forza's suggested line.
    # It retains its own two-second route frames without releasing throttle.
    p += [step("diagnostic", diagnosticId="forza-guided-route"),
          step("diagnostic", diagnosticId="forza-blockstats-route-end"),
          step("wait", delayMs=1000), step("screenshot", name="route-post"),
          step("quit")]
    return p


def build_input_probe_plan() -> list[dict[str, Any]]:
    """Use the qualified menu path, then independently probe A and RT acceleration."""
    p = build_forza_plan()
    route_start = next(i for i, row in enumerate(p)
                       if row.get("diagnosticId") == "forza-blockstats-route-start")
    p = p[:route_start + 1]
    p += [
        step("diagnostic", diagnosticId="forza-probe-A-hold"),
        step("screenshot", name="input-probe-after-A"),
        step("diagnostic", diagnosticId="forza-probe-RT-hold"),
        step("screenshot", name="input-probe-after-RT"),
        step("quit"),
    ]
    return p


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _frame_score(path: Path) -> dict[str, float | bool]:
    with Image.open(path) as source:
        im = source.convert("RGB")
        # Exclude host chrome and HUD edges while retaining sky, scenery and road.
        w, h = im.size
        roi = im.crop((int(w * .08), int(h * .14), int(w * .92), int(h * .88)))
        gray = roi.convert("L")
        hist = gray.histogram()
        count = sum(hist)
        entropy = -sum((n / count) * math.log2(n / count) for n in hist if n)
        dark = sum(hist[:18]) / count
        bright = sum(hist[238:]) / count
        edge = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
        quantized = roi.quantize(colors=64)
        colors = len(quantized.getcolors(maxcolors=64) or [])
        # A rendered Forza scene has broad tonal and edge variation. Missing-world
        # frames collapse into a dark/flat field even though the HUD remains.
        ok = entropy >= 1.80 and edge >= 5.0 and colors >= 24 and dark < .72 and bright < .72
        return {"pass": ok, "entropy": entropy, "edge_mean": edge,
                "quantized_colors": colors, "dark_ratio": dark, "bright_ratio": bright}


def score_evidence(root: Path) -> dict[str, Any]:
    root = Path(root)
    result = json.loads((root / "result.json").read_text())
    qemu = (root / "qemu.log").read_text(errors="replace") if (root / "qemu.log").exists() else ""
    block = json.loads((root / "blockstats-summary.json").read_text())
    ocr = json.loads((root / "ocr.json").read_text()) if (root / "ocr.json").exists() else {}
    actions = json.loads((root / "actions.json").read_text())
    route_metrics = json.loads((root / "route-metrics.json").read_text())

    process_ok = (result.get("status") == "completed" and result.get("exitCode") == 0
                  and not (result.get("crash") or {}).get("Crashed", False))
    errors = ERROR_PATTERNS.findall(qemu)
    failed = invalid = read_ops = read_bytes = 0
    for delta in block.get("deltas", []):
        for values in delta.get("devices", {}).values():
            failed += int(values.get("failed_rd_operations", 0) or 0)
            invalid += int(values.get("invalid_rd_operations", 0) or 0)
            read_ops += int(values.get("rd_operations", 0) or 0)
            read_bytes += int(values.get("rd_bytes", 0) or 0)
    menu_text = " ".join(str(v) for v in ocr.values()).upper()
    class_text = str(ocr.get("class-r", "")).upper()
    # Tesseract may join adjacent menu words although the rendered title is
    # intact. Normalize OCR whitespace so identity does not depend on tokenizing
    # "MAIN MENU" versus "MAINMENU".
    main_menu_seen = "MAINMENU" in re.sub(r"\s+", "", menu_text)
    identity_ok = main_menu_seen and "SELECT CAR CLASS" in class_text and bool(
        re.search(r"(?:CLASS\s+R|\bR\s+CLASS\b)", class_text))

    frames = []
    for path in sorted((root / "screenshots").glob("route-*.png")):
        row = _frame_score(path); row["path"] = path.relative_to(root).as_posix(); frames.append(row)
    bad = sum(not bool(x["pass"]) for x in frames)
    world_ok = len(frames) >= 8 and bad <= 1
    max_speed = float(route_metrics.get("max_speed_mph", 0) or 0)
    map_displacement = float(route_metrics.get("minimap_displacement_pixels", 0) or 0)
    progress_observations = int(route_metrics.get("observations", 0) or 0)
    # A rendered but stationary car does not pressure the world streamer. The
    # threshold catches the invalid bring-up run (47 MPH peak, 1.4 px travel)
    # while accepting a conservative R-class pass through the opening sector.
    progress_ok = max_speed >= 40 and map_displacement >= 12 and progress_observations >= 8

    first = next((x for x in actions if x.get("label") == "race-confirm"), None)
    last = next((x for x in reversed(actions) if x.get("label") == "route-end"), None)
    route_seconds = None
    if first and last:
        route_seconds = (_parse_time(last["finished_utc"]) - _parse_time(first["finished_utc"])).total_seconds()
    timing_ok = route_seconds is not None and 10 <= route_seconds <= 90

    checks = {
        "process_and_crash": {"pass": process_ok, "status": result.get("status"),
                              "exit_code": result.get("exitCode")},
        "menu_and_route_identity": {"pass": identity_ok, "class_text": class_text,
                                    "main_menu_seen": main_menu_seen},
        "world_completeness": {"pass": world_ok, "frames": len(frames),
                               "bad_frames": bad, "frame_scores": frames},
        "route_progress": {"pass": progress_ok, "max_speed_mph": max_speed,
                           "minimap_displacement_pixels": map_displacement,
                           "observations": progress_observations},
        "corruption_and_log_errors": {"pass": not errors, "matches": errors},
        "read_errors": {"pass": failed + invalid == 0 and read_ops > 0,
                        "failed_or_invalid": failed + invalid, "read_operations": read_ops,
                        "read_bytes": read_bytes},
        "route_timing": {"pass": timing_ok},
    }
    passed = all(v["pass"] for v in checks.values())
    return {"schema_version": 1, "pass": passed, "checks": checks,
            "timing": {"route_seconds": route_seconds,
                       "process_duration_seconds": result.get("durationMs", 0) / 1000}}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    report = score_evidence(args.evidence)
    text = json.dumps(report, indent=2) + "\n"
    if args.out: args.out.write_text(text)
    print(text, end="")
    raise SystemExit(0 if report["pass"] else 1)
