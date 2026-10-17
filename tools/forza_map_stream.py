#!/usr/bin/env python3
"""Validate and compare sustained Forza-shaped public storage replays."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path


def _fields(line: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for token in line.split():
        if "=" in token:
            key, value = token.split("=", 1)
            if key in fields:
                raise ValueError(f"duplicate field: {key}")
            fields[key] = value
    return fields


def parse_serial(text: str) -> dict[str, object]:
    cases: list[dict[str, int | str]] = []
    ends: list[dict[str, int | str]] = []
    pass_rows: list[dict[str, str]] = []
    metadata_rows: list[dict[str, str]] = []
    io_metadata_rows: list[dict[str, str]] = []
    events: list[str] = []
    tap_passes = 0
    tap_failures = 0
    error_stages: list[str] = []
    warmup_oracle_failures = 0
    oracle_failure_records = 0
    malformed_records: list[str] = []
    for line in text.splitlines():
        payload = line.strip()
        try:
            if payload.startswith("# STORAGE-FORZA-MAP-META "):
                metadata_rows.append(_fields(payload))
            elif payload.startswith("# STORAGE-FORZA-MAP-PASS "):
                pass_rows.append(_fields(payload))
                events.append("pass")
            elif payload.startswith("# STORAGE-IO-V6-META "):
                io_metadata_rows.append(_fields(payload))
                events.append("io_meta")
            elif payload.startswith("# STORAGE-IO-V6-CASE "):
                row: dict[str, int | str] = {}
                for key, value in _fields(payload).items():
                    try:
                        row[key] = int(value, 0)
                    except ValueError:
                        row[key] = value
                cases.append(row)
                events.append("case")
            elif payload.startswith("# STORAGE-IO-V6-END "):
                row = {}
                for key, value in _fields(payload).items():
                    try:
                        row[key] = int(value, 0)
                    except ValueError:
                        row[key] = value
                ends.append(row)
                events.append("end")
            elif payload.startswith("# STORAGE-IO-V6-SETUP "):
                value = _fields(payload).get("warmup_oracle_failures")
                if value is not None:
                    warmup_oracle_failures = max(warmup_oracle_failures, int(value, 0))
            elif payload.startswith("# STORAGE-IO-V6-ORACLE-FAIL "):
                _fields(payload)
                oracle_failure_records += 1
            elif payload.startswith("# STORAGE-IO-V6-ERROR "):
                stage = _fields(payload).get("stage")
                if stage:
                    error_stages.append(stage)
            elif payload == "ok 1 - Forza map streaming public request replay":
                tap_passes += 1
            elif payload == "not ok 1 - Forza map streaming public request replay":
                tap_failures += 1
        except (TypeError, ValueError) as error:
            malformed_records.append(str(error))

    reasons: list[str] = []
    expected_metadata = {
        "version": "1",
        "source": "public-api-metadata",
        "requests": "1024",
        "observed_title_high_water": "10",
        "reference_high_water": "12",
        "measured_qd": "12",
        "pressure_pages": "900",
        "passes": "16",
    }
    if metadata_rows != [expected_metadata]:
        reasons.append("dedicated fixture metadata identity mismatch")
    expected_passes = [
        {"index": str(index), "count": "16"} for index in range(1, 17)
    ]
    if pass_rows != expected_passes:
        reasons.append("pass identity or order mismatch")
    expected_events = [event for _ in range(16) for event in ("pass", "io_meta", "case", "end")]
    if events != expected_events:
        reasons.append("fixture record count or order mismatch")
    if len(cases) != 16:
        reasons.append("requires exactly 16 complete measured passes")
    if len(io_metadata_rows) != 16:
        reasons.append("requires one I/O identity record per pass")
    for index, row in enumerate(io_metadata_rows):
        required = {
            "version": "6",
            "fixture_generation": "6",
            "route": "fatx-file",
            "dataset": "0",
            "qd_requested": "12",
            "pressure_target": "900",
            "cache": "warm",
        }
        if any(row.get(key) != value for key, value in required.items()):
            reasons.append(f"pass {index + 1} I/O identity mismatch")
    if len(ends) != len(cases):
        reasons.append("missing per-pass cleanup record")
    if tap_passes != 1 or tap_failures:
        reasons.append("fixture TAP result did not pass")
    if error_stages:
        reasons.append("fixture emitted an explicit error record")
    if warmup_oracle_failures:
        reasons.append("fixture warmup oracle failed")
    if oracle_failure_records:
        reasons.append("fixture emitted oracle failure records")
    if malformed_records:
        reasons.append("fixture emitted malformed records")
    for index, row in enumerate(cases):
        if row.get("operations_expected") != 1024 or row.get("operations_completed") != 1024:
            reasons.append(f"pass {index + 1} did not complete 1024 operations")
        if row.get("failures") != 0:
            reasons.append(f"pass {index + 1} reported failures")
        if row.get("qd_requested") != 12 or row.get("max_active_slots") != 12:
            reasons.append(f"pass {index + 1} did not exercise captured Forza concurrency")
        if row.get("measured_pages_before") != 900:
            reasons.append(f"pass {index + 1} did not start at 900 available pages")
        if row.get("route") != "fatx-file":
            reasons.append(f"pass {index + 1} used the wrong storage route")
        if row.get("bytes_completed") != 10871296:
            reasons.append(f"pass {index + 1} byte count mismatch")
        if row.get("oracle") != "post_batch_full_bytes":
            reasons.append(f"pass {index + 1} oracle identity mismatch")
        if row.get("caller_occupancy") != "issue_to_apc_entry":
            reasons.append(f"pass {index + 1} caller occupancy identity mismatch")
        for field in (
            "apc_batch_ticks",
            "caller_batch_ticks",
            "submit_sum_ticks",
            "post_return_to_apc_sum_ticks",
        ):
            if field not in row:
                reasons.append(f"pass {index + 1} is missing {field}")
            elif int(row[field]) <= 0:
                reasons.append(f"pass {index + 1} has nonpositive {field}")
    for index, row in enumerate(ends):
        if (row.get("operations_submitted") != 1024 or row.get("failures") != 0
                or row.get("cleanup_complete") != 1
                or row.get("callback_buffers_retained") != 0):
            reasons.append(f"pass {index + 1} cleanup or submission record failed")

    timing_fields = {
        "apc_batch": "apc_batch_ticks",
        "caller_batch": "caller_batch_ticks",
        "submit_sum": "submit_sum_ticks",
        "post_return_to_apc_sum": "post_return_to_apc_sum_ticks",
        "return_after_apc_sum": "return_after_apc_sum_ticks",
    }
    timing_median_ticks = {
        name: statistics.median(
            int(row[field]) for row in cases if field in row
        )
        for name, field in timing_fields.items()
        if any(field in row for row in cases)
    }
    ticks = [int(row["apc_batch_ticks"]) for row in cases if "apc_batch_ticks" in row]
    reported_failures = max(
        [warmup_oracle_failures]
        + [int(row.get("failures", 0)) for row in cases + ends]
    )
    return {
        "status": "qualified" if not reasons else "rejected",
        "reasons": reasons,
        "passes": len(cases),
        "operations": sum(int(row.get("operations_completed", 0)) for row in cases),
        "queue_high_water_min": min((int(row.get("max_active_slots", 0)) for row in cases), default=0),
        "pressure_pages": min((int(row.get("measured_pages_before", 0)) for row in cases), default=0),
        "reported_failures": reported_failures,
        "warmup_oracle_failures": warmup_oracle_failures,
        "oracle_failure_records": oracle_failure_records,
        "malformed_records": malformed_records,
        "error_stages": sorted(set(error_stages)),
        "apc_batch_ticks": ticks,
        "apc_batch_median_ticks": statistics.median(ticks) if ticks else None,
        "timing_median_ticks": timing_median_ticks,
    }


def compare(reference: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    if reference.get("status") != "qualified" or candidate.get("status") != "qualified":
        raise ValueError("both captures must qualify before comparison")
    baseline = float(reference["apc_batch_median_ticks"])
    measured = float(candidate["apc_batch_median_ticks"])
    ratio = measured / baseline
    reference_timing = reference.get("timing_median_ticks", {})
    candidate_timing = candidate.get("timing_median_ticks", {})
    timing_change_percent = {}
    for name in sorted(set(reference_timing) & set(candidate_timing)):
        reference_value = float(reference_timing[name])
        candidate_value = float(candidate_timing[name])
        timing_change_percent[name] = (
            ((candidate_value / reference_value) - 1.0) * 100.0
            if reference_value
            else None
        )
    return {
        "status": "regressed" if ratio > 1.10 else "qualified",
        "candidate_over_reference": ratio,
        "candidate_change_percent": (ratio - 1.0) * 100.0,
        "reference_median_ticks": baseline,
        "candidate_median_ticks": measured,
        "timing_change_percent": timing_change_percent,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path, nargs="?")
    args = parser.parse_args()
    reference = parse_serial(args.reference.read_text(errors="replace"))
    result: object = reference
    exit_code = 0 if reference["status"] == "qualified" else 2
    if args.candidate:
        candidate = parse_serial(args.candidate.read_text(errors="replace"))
        result = {"reference": reference, "candidate": candidate}
        if reference["status"] == "qualified" and candidate["status"] == "qualified":
            result["comparison"] = compare(reference, candidate)
            exit_code = 0 if result["comparison"]["status"] == "qualified" else 2
        else:
            result["comparison"] = {
                "status": "rejected",
                "reason": "both captures must qualify before comparison",
            }
            exit_code = 2
    print(json.dumps(result, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
