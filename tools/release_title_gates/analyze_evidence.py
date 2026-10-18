#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Derive the complete, local-only Forza title-gate evidence bundle."""
from __future__ import annotations

from pathlib import Path
import argparse
import json
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageOps

try:
    from rapidocr_onnxruntime import RapidOCR
except ImportError:
    # An offline dependency bundle may be selected explicitly. Never embed a
    # developer-machine path in the redistributable analyzer.
    dependency_dir = os.environ.get("FORZA_GATE_OCR_DEPS")
    if not dependency_dir:
        raise SystemExit(
            "rapidocr_onnxruntime is unavailable; install requirements.txt or "
            "set FORZA_GATE_OCR_DEPS to an offline dependency directory"
        )
    sys.path.insert(0, str(Path(dependency_dir).resolve()))
    from rapidocr_onnxruntime import RapidOCR

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from rclass_gate import score_evidence


def ocr_text(engine: RapidOCR, path: Path) -> str:
    result, _ = engine(str(path))
    return " ".join(row[1] for row in (result or []))


def speed_mph(engine: RapidOCR, path: Path) -> int | None:
    with Image.open(path) as source:
        im = source.convert("RGB")
        w, h = im.size
        gauge = im.crop((int(w * .65), int(h * .54), int(w * .88), int(h * .94)))
    result, _ = engine(np.array(gauge))
    rows = result or []
    mph = next((row for row in rows if row[1].strip().upper() == "MPH"), None)
    if mph is None:
        return None
    mph_y = sum(point[1] for point in mph[0]) / 4
    candidates = []
    for box, text, confidence in rows:
        match = re.fullmatch(r"\D*(\d{1,3})\D*", text.strip())
        if not match:
            continue
        y = sum(point[1] for point in box) / 4
        value = int(match.group(1))
        if 0 <= value <= 260 and 0 < mph_y - y < gauge.height * .22:
            candidates.append((mph_y - y, -float(confidence), value))
    return min(candidates)[2] if candidates else None


def map_marker(path: Path) -> tuple[float, float] | None:
    with Image.open(path) as source:
        im = source.convert("RGB")
        w, h = im.size
        points = []
        for y in range(int(h * .07), int(h * .37), 2):
            for x in range(int(w * .20), int(w * .34), 2):
                r, g, b = im.getpixel((x, y))
                if g >= 80 and g > r * 1.35 and g > b * 1.15:
                    points.append((x, y))
    if len(points) < 8:
        return None
    return (sum(x for x, _ in points) / len(points),
            sum(y for _, y in points) / len(points))


def qmp_checkpoints(root: Path) -> dict[str, dict]:
    found = {}
    for path in root.glob("diagnostics/*blockstats*/qmp-result.json"):
        for label in ("load-start", "race-ready", "route-start", "route-end"):
            if label in path.parent.name:
                found[label] = {row["device"]: row["stats"] for row in json.loads(path.read_text())}
    return found


def blockstats_summary(root: Path) -> dict:
    checkpoints = qmp_checkpoints(root)
    fields = ("rd_operations", "rd_bytes", "rd_total_time_ns", "failed_rd_operations",
              "invalid_rd_operations", "wr_operations", "wr_bytes")
    deltas = []
    for start, end in (("load-start", "race-ready"), ("race-ready", "route-start"),
                       ("route-start", "route-end")):
        devices = {}
        if start in checkpoints and end in checkpoints:
            for device in sorted(set(checkpoints[start]) & set(checkpoints[end])):
                devices[device] = {field: int(checkpoints[end][device].get(field, 0) or 0) -
                                   int(checkpoints[start][device].get(field, 0) or 0)
                                   for field in fields}
        deltas.append({"from": start, "to": end, "devices": devices})
    return {"schema_version": 1, "checkpoints": sorted(checkpoints), "deltas": deltas}


def contact_sheet(paths: list[Path], target: Path) -> None:
    if not paths:
        return
    columns = 4
    thumb_w, thumb_h = 320, 200
    rows = math.ceil(len(paths) / columns)
    sheet = Image.new("RGB", (columns * thumb_w, rows * (thumb_h + 22)), "black")
    draw = ImageDraw.Draw(sheet)
    for i, path in enumerate(paths):
        with Image.open(path) as source:
            thumb = ImageOps.contain(source.convert("RGB"), (thumb_w, thumb_h))
        x, y = i % columns * thumb_w, i // columns * (thumb_h + 22)
        sheet.paste(thumb, (x + (thumb_w - thumb.width) // 2, y))
        draw.text((x + 4, y + thumb_h + 3), path.stem, fill="white")
    sheet.save(target)


def main(root: Path) -> int:
    engine = RapidOCR()
    screenshots = root / "screenshots"
    route = sorted(screenshots.glob("route-*.png"))
    identity_names = ["main-confirm", "class-r", "r-car"]
    ocr = {}
    for name in identity_names:
        path = screenshots / f"{name}.png"
        if path.exists():
            ocr[name] = ocr_text(engine, path)
    speeds = []
    markers = []
    for path in route:
        text = ocr_text(engine, path)
        ocr[path.stem] = text
        speed = speed_mph(engine, path)
        marker = map_marker(path)
        speeds.append({"frame": path.name, "mph": speed})
        markers.append({"frame": path.name, "point": marker})
    valid_markers = [row for row in markers if row["point"] is not None]
    displacement = 0.0
    if valid_markers:
        origin = valid_markers[0]["point"]
        displacement = max(math.dist(origin, row["point"]) for row in valid_markers)
    metrics = {
        "schema_version": 1,
        "max_speed_mph": max((row["mph"] for row in speeds if row["mph"] is not None), default=0),
        "minimap_displacement_pixels": displacement,
        "observations": len(route),
        "speeds": speeds,
        "markers": markers,
    }
    actions = sorted((json.loads(path.read_text()) for path in root.glob("forza-action-*.json")),
                     key=lambda row: row.get("started_utc", ""))
    (root / "ocr.json").write_text(json.dumps(ocr, indent=2) + "\n")
    (root / "route-metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (root / "actions.json").write_text(json.dumps(actions, indent=2) + "\n")
    (root / "blockstats-summary.json").write_text(json.dumps(blockstats_summary(root), indent=2) + "\n")
    contact_sheet(route, root / "route-contact.png")
    report = score_evidence(root)
    (root / "qualification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    raise SystemExit(main(args.evidence))
