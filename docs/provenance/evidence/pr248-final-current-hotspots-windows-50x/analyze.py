#!/usr/bin/env python3
"""Recompute per-leaf SpiritBoot/Complex ratios from collected runner evidence."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    receipt = json.loads((args.evidence / "execution-receipt.json").read_text(encoding="utf-8"))
    runs = []
    summary = {"schema": 1, "order": receipt["order"], "runs": [], "leaves": {}}

    for run in receipt["runs"]:
        slot = next((args.evidence / "runs").glob(f"{run['index']:02d}-*"))
        root = slot / "evidence" / run["runId"]
        result = json.loads((root / "result.json").read_text(encoding="utf-8"))
        records = json.loads((root / "guest" / "results.txt").read_text(encoding="utf-8"))
        leaves = {record["id"]: record for record in records if record["kind"] == "leaf"}
        runs.append((run["arm"], leaves))
        summary["runs"].append(
            {
                "index": run["index"],
                "arm": run["arm"],
                "run_id": run["runId"],
                "duration_seconds": result["durationMs"] / 1000,
                "outcome": run["summary"]["outcome"],
            }
        )

    for leaf_id in runs[0][1]:
        candidate = [rows[leaf_id]["total_us"] / rows[leaf_id]["iterations"] for arm, rows in runs if arm == "candidate"]
        complex_values = [rows[leaf_id]["total_us"] / rows[leaf_id]["iterations"] for arm, rows in runs if arm == "complex"]
        candidate_mean = statistics.mean(candidate)
        complex_mean = statistics.mean(complex_values)
        summary["leaves"][leaf_id] = {
            "candidate_run_mean_us": candidate,
            "complex_run_mean_us": complex_values,
            "candidate_mean_us": candidate_mean,
            "complex_mean_us": complex_mean,
            "ratio": candidate_mean / complex_mean,
            "delta_percent": (candidate_mean / complex_mean - 1) * 100,
        }

    summary["threshold"] = {
        "investigate_above_percent": 20,
        "triggered": sorted(
            leaf_id for leaf_id, value in summary["leaves"].items() if value["delta_percent"] > 20
        ),
    }
    encoded = json.dumps(summary, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
