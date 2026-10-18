#!/usr/bin/env python3
"""Recompute historical 0181 evidence for the rejected direct-read stack."""

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SYNTHETIC = ROOT / "synthetic"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(value, message):
    if not value:
        raise SystemExit(message)


def close(actual, expected, label):
    require(math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-12),
            f"{label}: recomputed {actual!r}, archived {expected!r}")


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_case(case):
    count = case["operations"]
    require(count > 0 and case["elapsed_seconds"] >= 10.0, "empty or short case")
    require(case["before"] == case["target"] == case["after"], "page target changed")
    require(case["failures"] == 0, "fixture reported a failure")
    require(case["verified"] == case["callbacks"] == case["pending"] == count,
            "payload/callback/pending oracle changed")
    require(case["high_water"] <= 8, "fixture exceeded its eight-slot contract")
    require(sum(row["count"] for row in case["sizes"]) == count, "size counts differ")


def weighted(summary, case):
    return (sum(row["submit_sum"] for row in case["sizes"]) * 1_000_000.0
            / summary["frequency"] / case["operations"])


def size_mean(summary, case, size):
    row = next(row for row in case["sizes"] if row["bytes"] == size)
    return row["submit_sum"] * 1_000_000.0 / summary["frequency"] / row["count"]


def validate_raw_run(label, receipt):
    run_dir = SYNTHETIC / "runs" / label
    for name, expected in receipt["files"].items():
        path = run_dir / name
        require(path.stat().st_size == expected["bytes"], f"{label} {name} size changed")
        require(file_hash(path) == expected["sha256"], f"{label} {name} hash changed")
    result = load(run_dir / "result.json")
    submitted = load(run_dir / "submitted.json")
    require((result["jobId"], result["runId"]) == (receipt["job_id"], receipt["run_id"]),
            f"{label} result binding changed")
    require(result["outcome"]["execution"] == "completed", f"{label} did not complete")
    require(submitted["id"] == receipt["submitted_job_id"], f"{label} submit binding changed")
    serial = (run_dir / "serial.log").read_text(encoding="utf-8")
    require(serial.startswith("TAP version 13\n1..10\n"), f"{label} TAP header changed")
    require("ok 10 - bounded submission bursts preserve callback and byte contracts" in serial,
            f"{label} final oracle missing")
    require("# FORZA-PUMP-END failures=0" in serial, f"{label} terminal result changed")
    require(serial.count("# FORZA-PUMP-CASE ") == 8, f"{label} case count changed")
    return load(run_dir / "summary.json")


def compare_rows(actual, archived, label):
    require(len(actual) == len(archived), f"{label} row count changed")
    for index, (found, expected) in enumerate(zip(actual, archived)):
        require(found.keys() == expected.keys(), f"{label}[{index}] fields changed")
        for field, value in found.items():
            if isinstance(value, float):
                close(value, expected[field], f"{label}[{index}] {field}")
            else:
                require(value == expected[field], f"{label}[{index}] {field} changed")


def recompute():
    archived = load(SYNTHETIC / "comparison.json")
    receipts = load(SYNTHETIC / "receipts.json")["runs"]
    require([row["label"] for row in receipts] == archived["order"], "run order changed")
    summaries = {row["label"]: validate_raw_run(row["label"], row) for row in receipts}
    rows, sizes, positions = [], [], []
    for pair in (1, 2):
        control, candidate = summaries[f"control{pair}"], summaries[f"candidate{pair}"]
        before = {(x["target"], x["budget_us"]): x for x in control["cases"]}
        after = {(x["target"], x["budget_us"]): x for x in candidate["cases"]}
        require(before.keys() == after.keys(), "case matrix changed")
        for key in sorted(before, key=lambda item: (item[0], item[1] or 10**9)):
            old, new = before[key], after[key]
            validate_case(old)
            validate_case(new)
            old_cost, new_cost = weighted(control, old), weighted(candidate, new)
            rows.append({
                "pair": pair, "target_free_pages": key[0], "budget_us": key[1],
                "control_weighted_submit_us": old_cost, "candidate_weighted_submit_us": new_cost,
                "submit_change_percent": 100.0 * (new_cost / old_cost - 1.0),
                "control_verified_reads_per_second": old["operations_per_second"],
                "candidate_verified_reads_per_second": new["operations_per_second"],
                "rate_change_percent": 100.0 * (new["operations_per_second"] / old["operations_per_second"] - 1.0),
                "control_operations": old["operations"], "candidate_operations": new["operations"],
                "control_failures": old["failures"], "candidate_failures": new["failures"],
            })
            for length in (512, 65536):
                a, b = size_mean(control, old, length), size_mean(candidate, new, length)
                sizes.append({
                    "pair": pair, "target_free_pages": key[0], "budget_us": key[1], "bytes": length,
                    "control_submit_us": a, "candidate_submit_us": b,
                    "submit_change_percent": 100.0 * (b / a - 1.0),
                })
            for role, case in (("control", old), ("candidate", new)):
                first_512 = case["pair_split"]
                positions.append({
                    "pair": pair, "role": role, "target_free_pages": key[0], "budget_us": key[1],
                    "frames": case["frames"], "zero_issue_frames": case["zero_issue_frames"],
                    "first_512_byte_requests": first_512,
                    "first_65536_byte_requests": case["frames"] - case["zero_issue_frames"] - first_512,
                    "derivation": "pair_split; frames - zero_issue_frames - pair_split",
                })

    means, size_means = [], []
    for target in (783, 900):
        for budget in (250, 450, 1000, 0):
            selected = [x for x in rows if x["target_free_pages"] == target and x["budget_us"] == budget]
            ca = sum(x["control_weighted_submit_us"] for x in selected) / 2
            da = sum(x["candidate_weighted_submit_us"] for x in selected) / 2
            cr = sum(x["control_verified_reads_per_second"] for x in selected) / 2
            dr = sum(x["candidate_verified_reads_per_second"] for x in selected) / 2
            means.append({
                "target_free_pages": target, "budget_us": budget,
                "control_mean_weighted_submit_us": ca, "candidate_mean_weighted_submit_us": da,
                "submit_change_percent": 100.0 * (da / ca - 1.0),
                "control_mean_verified_reads_per_second": cr,
                "candidate_mean_verified_reads_per_second": dr,
                "rate_change_percent": 100.0 * (dr / cr - 1.0),
            })
            for length in (512, 65536):
                selected = [x for x in sizes if x["target_free_pages"] == target
                            and x["budget_us"] == budget and x["bytes"] == length]
                ca = sum(x["control_submit_us"] for x in selected) / 2
                da = sum(x["candidate_submit_us"] for x in selected) / 2
                size_means.append({
                    "target_free_pages": target, "budget_us": budget, "bytes": length,
                    "control_mean_submit_us": ca, "candidate_mean_submit_us": da,
                    "submit_change_percent": 100.0 * (da / ca - 1.0),
                })

    compare_rows(rows, archived["comparisons"], "comparisons")
    compare_rows(sizes, archived["per_size_pair_comparisons"], "per-size")
    compare_rows(positions, archived["first_request_position_counts"], "first-position")
    compare_rows(means, archived["two_run_role_means"], "role means")
    compare_rows(size_means, archived["two_run_per_size_role_means"], "per-size means")
    require(all(x["submit_change_percent"] < 0 for x in means), "a mean whole-case cost did not improve")
    require(max(x["submit_change_percent"] for x in rows) < 20.0, "whole-case regression over 20%")
    require(max(x["submit_change_percent"] for x in size_means) < 20.0, "mean per-size regression over 20%")
    require(any(x["submit_change_percent"] > 20.0 for x in sizes),
            "disclosed ordinal-confounded individual regression disappeared")
    require(archived["all_payload_callback_status_lifetime_oracles_passed"], "oracle gate is false")
    require(archived["two_run_mean_submit_improved_cases"] == archived["two_run_mean_submit_case_count"] == 8,
            "mean improvement count changed")


def validate_titles():
    title, build = load(ROOT / "title-acceptance.json"), load(ROOT / "build-identity.json")
    comparison = load(SYNTHETIC / "comparison.json")
    require(title["memory_mib"] == 64 and title["fresh_process_each_attempt"] and not title["snapshot_used"],
            "title isolation contract changed")
    require(title["candidate_firmware_sha256"] == build["flash_sha256"] == comparison["candidate_firmware_sha256"],
            "candidate identity mismatch")
    require([run["variant"] for run in title["forza"]] ==
            ["0168-control", "0181-candidate", "0168-control", "0181-candidate"], "Forza order changed")
    require([run["first_grid_sample_index"] for run in title["forza"]] == [4, 3, 4, 3],
            "grid classification changed")
    good = {"execution": "completed", "correctness": "passed", "evidence": "complete", "comparison": "eligible"}
    for run in title["forza"]:
        require(run["outcome"] == good and run["driven_race_segment_completed"], "Forza route failed")
        require(len(run["samples_0_through_7"]) == 8, "Forza scalar samples changed")
    require(len(title["pgr2"]) == 3, "PGR2 repeat count changed")
    for run in title["pgr2"]:
        require(run["variant"] == "0181-candidate" and run["outcome"] == good and run["route_completed"],
                "PGR2 route failed")
        require(29.99 <= run["cadence_fps"] <= 30.01 and run["frame_interval_p99_ms"] < 35.0,
                "PGR2 cadence gate failed")
    require(len(title["excluded_setup_attempts"]) == 2, "excluded setup set changed")
    require(not title["conclusion"]["manual_test_requested"], "manual test was requested")
    require(title["evidence_retention"]["repository"].startswith("scalar"), "retention limitation missing")


if __name__ == "__main__":
    recompute()
    validate_titles()
    print("Historical 0181 archive verifies; the direct-read stack remains rejected by the later operator title result")
