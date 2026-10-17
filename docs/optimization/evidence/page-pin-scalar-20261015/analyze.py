#!/usr/bin/env python3
"""Validate and summarize the page-pin release benchmark captures."""

import argparse
import csv
import json
import re
import statistics
from pathlib import Path


META_RE = re.compile(r"^# PIN-PERF-META .* frequency=(\d+) samples=(\d+)$")
SAMPLE_RE = re.compile(
    r"^# PIN-PERF workload=(\S+) sample=(\d+) iterations=(\d+) "
    r"ticks=(\d+) correct=(\d+) checksum=([0-9a-fA-F]+)$"
)
WORKLOADS = (
    "physical-valid",
    "physical-reject-device",
    "scatter-accepted-sustained",
    "scatter-rejected-32",
    "scatter-rejected-64",
)
ARMS = ("baseline", "candidate")
PAIRS = range(1, 11)


def parse_run(capture_root: Path, pair: int, arm: str) -> dict:
    run_dir = capture_root / f"pair-{pair}-{arm}"
    manifest = json.loads((run_dir / "run.json").read_text())
    tap = manifest["tap"]
    assert manifest["status"] == "passed"
    assert tap == {
        "errors": [],
        "failed": 0,
        "ok": 7,
        "passed": True,
        "plan": 7,
        "ran": 7,
        "skipped": 0,
        "todo": 0,
    }

    frequency = None
    samples = {}
    for raw in (run_dir / "serial.log").read_text().splitlines():
        match = META_RE.match(raw)
        if match:
            frequency = int(match.group(1))
            assert int(match.group(2)) == 7
        match = SAMPLE_RE.match(raw)
        if match:
            name, sample, iterations, ticks, correct, checksum = match.groups()
            assert name in WORKLOADS
            assert correct == "1"
            samples.setdefault(name, []).append(
                (int(sample), int(iterations), int(ticks), checksum.lower())
            )

    assert frequency
    assert set(samples) == set(WORKLOADS)
    assert all(len(values) == 7 for values in samples.values())
    medians = {}
    for name in WORKLOADS:
        values = samples[name]
        assert [value[0] for value in values] == list(range(7))
        assert len({value[1] for value in values}) == 1
        assert len({value[3] for value in values}) == 1
        medians[name] = statistics.median(
            value[2] / value[1] * 1_000_000 / frequency for value in values
        )

    return {
        "pair": pair,
        "arm": arm,
        "frequency": frequency,
        "started_utc": manifest["started_utc"],
        "assets": {
            name: manifest["assets"][name]["sha256"]
            for name in ("dvd", "flash", "hdd", "xemu")
        },
        "workloads": medians,
    }


def analyze(capture_root: Path) -> dict:
    runs = [parse_run(capture_root, pair, arm) for pair in PAIRS for arm in ARMS]

    # Pair order alternates AB then BA. The same XISO, HDD, and xemu are used in
    # every run; each arm uses one immutable firmware image.
    for pair in PAIRS:
        pair_runs = [run for run in runs if run["pair"] == pair]
        actual_order = [run["arm"] for run in sorted(pair_runs, key=lambda run: run["started_utc"])]
        expected_order = list(ARMS if pair % 2 else reversed(ARMS))
        assert actual_order == expected_order
    for asset in ("dvd", "hdd", "xemu"):
        assert len({run["assets"][asset] for run in runs}) == 1
    for arm in ARMS:
        assert len({run["assets"]["flash"] for run in runs if run["arm"] == arm}) == 1

    report = {
        "schema": 1,
        "method": (
            "ten matched pairs, AB/BA order alternates; each run is median of "
            "seven release samples; microseconds per iteration; no control subtraction"
        ),
        "runs": [
            {
                "pair": run["pair"],
                "arm": run["arm"],
                "frequency": run["frequency"],
                "workloads": run["workloads"],
            }
            for run in runs
        ],
        "workloads": {},
    }
    for name in WORKLOADS:
        baseline = [run["workloads"][name] for run in runs if run["arm"] == "baseline"]
        candidate = [run["workloads"][name] for run in runs if run["arm"] == "candidate"]
        paired = []
        for pair in PAIRS:
            baseline_value = next(
                run["workloads"][name]
                for run in runs
                if run["pair"] == pair and run["arm"] == "baseline"
            )
            candidate_value = next(
                run["workloads"][name]
                for run in runs
                if run["pair"] == pair and run["arm"] == "candidate"
            )
            paired.append((candidate_value / baseline_value - 1) * 100)
        baseline_median = statistics.median(baseline)
        candidate_median = statistics.median(candidate)
        report["workloads"][name] = {
            "baseline_median_us": baseline_median,
            "candidate_median_us": candidate_median,
            "change_percent": (candidate_median / baseline_median - 1) * 100,
            "baseline_min_us": min(baseline),
            "baseline_max_us": max(baseline),
            "candidate_min_us": min(candidate),
            "candidate_max_us": max(candidate),
            "candidate_faster_pairs": sum(change < 0 for change in paired),
            "paired_change_percent": paired,
            "paired_median_percent": statistics.median(paired),
            "ranges": (
                "candidate_lower"
                if max(candidate) < min(baseline)
                else "candidate_higher"
                if min(candidate) > max(baseline)
                else "overlap"
            ),
        }
    return report


def write_report(report: dict, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    with (output / "analysis.csv").open("w", newline="") as csv_file:
        writer = csv.writer(csv_file, lineterminator="\n")
        writer.writerow(
            (
                "workload",
                "baseline_median_us",
                "candidate_median_us",
                "change_percent",
                "paired_median_percent",
                "candidate_faster_pairs",
                "ranges",
            )
        )
        for name, values in report["workloads"].items():
            writer.writerow(
                (
                    name,
                    values["baseline_median_us"],
                    values["candidate_median_us"],
                    values["change_percent"],
                    values["paired_median_percent"],
                    values["candidate_faster_pairs"],
                    values["ranges"],
                )
            )
    lines = []
    for name, values in report["workloads"].items():
        lines.append(
            f"{name:28s} {values['baseline_median_us']:.6f} -> "
            f"{values['candidate_median_us']:.6f} us "
            f"{values['change_percent']:+.2f}% "
            f"paired_med={values['paired_median_percent']:+.2f}% "
            f"faster={values['candidate_faster_pairs']}/10 "
            f"ranges={values['ranges']}"
        )
    (output / "summary.txt").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("capture_root", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = analyze(args.capture_root)
    write_report(report, args.output)
    print((args.output / "summary.txt").read_text(), end="")


if __name__ == "__main__":
    main()
