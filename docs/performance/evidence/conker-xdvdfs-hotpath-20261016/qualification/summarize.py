#!/usr/bin/env python3
"""Summarize the three uninstrumented Conker release64 A/B pairs."""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path


ROOT = Path(__file__).resolve().parent
LABELS = ("off-a", "on-a", "on-b", "off-b", "off-c", "on-c")
FRAME = re.compile(r"timestamp_us=(\d+) frame=(\d+) delta_us=(\d+)")
FLIP = re.compile(r"elapsed_us=(\d+) frames=(\d+) fps=([\d.]+)")


def one(label: str) -> dict[str, object]:
    run_dirs = list((ROOT / label / "evidence").iterdir())
    if len(run_dirs) != 1:
        raise RuntimeError(f"{label}: expected one evidence directory")
    run = run_dirs[0]
    result = json.loads((run / "result.json").read_text())
    performance = json.loads((run / "performance.json").read_text())
    frames = [tuple(map(int, match.groups())) for line in
              (run / "guest-frames.log").read_text().splitlines()
              if (match := FRAME.fullmatch(line.rstrip("\r")))]
    flips = [(int(match.group(1)), int(match.group(2)), float(match.group(3)))
             for line in (run / "guest-flips.log").read_text().splitlines()
             if (match := FLIP.fullmatch(line.rstrip("\r")))]
    if result.get("status") != "completed" or result.get("evidenceStatus") != "complete":
        raise RuntimeError(f"{label}: incomplete run")
    if not frames or not flips:
        raise RuntimeError(f"{label}: missing frame evidence")
    return {
        "label": label,
        "arm": label.split("-", 1)[0],
        "runId": result["runId"],
        "processCpuSeconds": performance["sampleProcessCpuSeconds"],
        "sampleWallSeconds": performance["sampleWallSeconds"],
        "frameCount": len(frames),
        "frameSpanSeconds": (frames[-1][0] - frames[0][0]) / 1_000_000,
        "maximumFrameDeltaUs": max(frame[2] for frame in frames),
        "firstFlipWindowFrames": flips[0][1],
        "flipWindowFrames": sum(flip[1] for flip in flips),
        "flipWindowCount": len(flips),
    }


def main() -> int:
    runs = [one(label) for label in LABELS]
    arms: dict[str, object] = {}
    for arm in ("off", "on"):
        selected = [run for run in runs if run["arm"] == arm]
        arms[arm] = {
            "runs": len(selected),
            "meanProcessCpuSeconds": statistics.fmean(
                float(run["processCpuSeconds"]) for run in selected),
            "meanMaximumFrameDeltaUs": statistics.fmean(
                int(run["maximumFrameDeltaUs"]) for run in selected),
            "meanFirstFlipWindowFrames": statistics.fmean(
                int(run["firstFlipWindowFrames"]) for run in selected),
            "meanFlipWindowFrames": statistics.fmean(
                int(run["flipWindowFrames"]) for run in selected),
        }
    off = arms["off"]
    on = arms["on"]
    comparison = {
        "processCpuPercent":
            (on["meanProcessCpuSeconds"] / off["meanProcessCpuSeconds"] - 1) * 100,
        "maximumFrameDeltaPercent":
            (on["meanMaximumFrameDeltaUs"] / off["meanMaximumFrameDeltaUs"] - 1) * 100,
        "firstFlipWindowFramesPercent":
            (on["meanFirstFlipWindowFrames"] / off["meanFirstFlipWindowFrames"] - 1) * 100,
        "flipWindowFramesPercent":
            (on["meanFlipWindowFrames"] / off["meanFlipWindowFrames"] - 1) * 100,
    }
    output = {"schema": 1, "runs": runs, "arms": arms, "onRelativeToOff": comparison}
    (ROOT / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
