#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 SpiritBoot contributors
"""Independent paired storage experiment scheduling and recorded-result analysis."""
import argparse
import datetime
import hashlib
import functools
import json
import math
import random
import re
import sys
import statistics
from pathlib import Path

METRICS = ("latency", "throughput", "p95", "p99")
METHOD = "exact-binomial-order-statistic-median-paired-run-ratio"
ENVIRONMENT_FIELDS = ("xemu_config", "host_ssd", "cpu_governor", "power_policy",
                      "thermal_policy", "memory_profile", "cpu_gpu_config")
MANIFEST_HASHES = ("pe_sha256", "flash_sha256", "xemu_sha256", "fixture_sha256",
                   "eeprom_sha256", "hdd_seed_sha256", "iso_sha256")
FIXED_MANIFEST_FIELDS = ("roswell_base", "toolchain_revision", "xemu_sha256", "fixture_sha256",
                         "eeprom_sha256", "hdd_seed_sha256", "iso_sha256")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def hash_string(value, lengths=(64,)):
    return isinstance(value, str) and len(value) in lengths and bool(re.fullmatch("[0-9a-f]+", value))


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def number(value, minimum=0, inclusive=False):
    return (type(value) in (int, float) and math.isfinite(value)
            and (value >= minimum if inclusive else value > minimum))


def validate_manifest(value):
    require(isinstance(value, dict), "manifest must be an object")
    for field in MANIFEST_HASHES:
        require(hash_string(value.get(field)), f"manifest needs pinned {field}")
    for field in ("product_commit", "roswell_base", "source_tree"):
        require(hash_string(value.get(field), (40, 64)), f"manifest needs pinned {field}")
    require(isinstance(value.get("patch_sha256s"), list)
            and all(hash_string(item) for item in value["patch_sha256s"]), "pin ordered patch_sha256s")
    require(isinstance(value.get("toolchain_revision"), str) and value["toolchain_revision"].strip(),
            "pin toolchain_revision")


def validate_spec(spec):
    require(isinstance(spec, dict) and spec.get("schema_version") == 1, "spec schema_version must be 1")
    require(not any(key.startswith("candidate") for key in spec), "calibration cannot include candidate inputs")
    require(isinstance(spec.get("machine_id"), str) and spec["machine_id"].strip(), "pin machine_id")
    require(spec.get("machine_role") in ("primary", "secondary"), "set machine_role")
    validate_manifest(spec.get("baseline"))
    env = spec.get("environment", {})
    require(isinstance(env, dict) and all(env.get(key) for key in ENVIRONMENT_FIELDS),
            "pin emulator, storage, power, thermal, memory and CPU/GPU controls")
    require(hash_string(spec.get("runner_sha256")), "pin runner_sha256")
    require(isinstance(spec.get("seeds"), dict)
            and all(integer(spec["seeds"].get(key)) for key in ("workload", "schedule")), "pin seeds")
    require(spec.get("order") in ("alternate", "random"), "order must be alternate or random")
    require(integer(spec.get("pilot_pairs"), 5), "A/A requires at least five pairs")
    require(integer(spec.get("minimum_confirmatory_pairs"), 30), "confirmation requires at least 30 pairs")
    require(integer(spec.get("maximum_confirmatory_pairs"), spec["minimum_confirmatory_pairs"]),
            "set a confirmatory sample-size cap")
    for field in ("planning_power", "planning_confidence"):
        require(number(spec.get(field), 0.5) and spec[field] < 1, f"{field} must be between .5 and 1")
    limits = spec.get("limits", {})
    require(isinstance(limits, dict) and set(limits) == set(METRICS), "predeclare all four metric limits")
    require(all(number(value) for value in limits.values()), "limits must be positive and finite")
    require(limits["throughput"] <= 1 and all(limits[key] >= 1 for key in ("latency", "p95", "p99")),
            "limits must allow baseline equivalence")
    policies = spec.get("cache_policies", {})
    require(isinstance(policies, dict) and all(isinstance(policies.get(key), str) and policies[key].strip()
                                             for key in ("warm", "cold-ish")), "pin warm and cold-ish cache preparation")
    cases = spec.get("cases")
    require(isinstance(cases, list) and cases, "predeclare workload cases")
    ids = set()
    sequences = {}
    for case in cases:
        require(isinstance(case, dict) and isinstance(case.get("id"), str) and case["id"], "case needs id")
        require(case["id"] not in ids, "duplicate case id")
        ids.add(case["id"])
        require(case.get("cache_policy") in policies, "case references unknown cache policy")
        require(integer(case.get("operations"), 1000), "each case requires >=1000 operations for p99")
        require(integer(case.get("bytes_per_operation"), 1) and integer(case.get("assertions"), 1),
                "pin byte and correctness assertion counts")
        require(hash_string(case.get("expected_sha256")), "pin expected checksum")
        kind = case.get("kind")
        require(kind in ("small-hdd-read", "fatx-read", "write-flush", "dvd-xiso", "boundary-sg"),
                "unknown workload kind")
        if kind == "small-hdd-read":
            require(case.get("queue_depth") == 1 and integer(case.get("request_bytes"), 512)
                    and case["request_bytes"] <= 4096 and case["request_bytes"] % 512 == 0
                    and integer(case.get("alignment_bytes"), 512) and case["alignment_bytes"] % 512 == 0,
                    "small HDD path must be aligned QD1")
        elif kind == "fatx-read":
            require(case["operations"] == 1024 and case.get("queue_depth") in (1, 4, 12)
                    and case.get("pressure_pages") in (0, 900), "FATX sequences require 1024 reads/QD1,4,12/0,900 pages")
            require(isinstance(case.get("sequence"), str) and case["sequence"]
                    and hash_string(case.get("sequence_sha256")), "pin FATX sequence identities")
            previous = sequences.setdefault(case["sequence"], case["sequence_sha256"])
            require(previous == case["sequence_sha256"], "sequence hash changed between cases")
        elif kind == "write-flush":
            require(integer(case.get("real_flushes"), 1), "write case requires actual device flushes")
        else:
            require(isinstance(case.get("variant"), str) and case["variant"], "pin workload variant")
            if kind == "dvd-xiso":
                require(hash_string(case.get("iso_sha256")), "pin each optical variant ISO hash")
    require(len(sequences) == 2 and len(set(sequences.values())) == 2, "pin both distinct FATX sequences")
    for policy in ("warm", "cold-ish"):
        selected = [case for case in cases if case["cache_policy"] == policy]
        require(any(case["kind"] == "small-hdd-read" for case in selected), "missing QD1 small HDD case")
        for sequence in sequences:
            for depth in (1, 4, 12):
                for pressure in (0, 900):
                    require(any(case["kind"] == "fatx-read" and case["sequence"] == sequence
                                and case["queue_depth"] == depth and case["pressure_pages"] == pressure
                                for case in selected), "incomplete FATX/cache/pressure matrix")
        require(any(case["kind"] == "write-flush" for case in selected), "missing write+realflush case")
        require(len({case["variant"] for case in selected if case["kind"] == "dvd-xiso"}) >= 2,
                "both XISO variants required")
        require({"split", "fragmented"}.issubset({case["variant"] for case in selected
                                                  if case["kind"] == "boundary-sg"}), "missing boundary/fragmented SG cases")


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def seal(value):
    value["sha256"] = digest(value)
    return value


def verify_seal(value):
    require(isinstance(value, dict) and hash_string(value.get("sha256")), "artifact lacks hash")
    require(digest({key: item for key, item in value.items() if key != "sha256"}) == value["sha256"],
            "artifact hash mismatch")


def utc(value):
    require(isinstance(value, str), "timestamp must be ISO 8601 UTC")
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.utcoffset() == datetime.timedelta(0), "timestamp must include UTC offset")
    return parsed


@functools.lru_cache(maxsize=20000)
def order_rank(count, alpha):
    """Largest k for which P[Binomial(n,.5) <= k-1] <= alpha."""
    total = 0.0
    rank = 0
    for successes in range(count // 2 + 1):
        total += math.exp(math.lgamma(count + 1) - math.lgamma(successes + 1)
                          - math.lgamma(count - successes + 1) - count * math.log(2))
        if total > alpha:
            break
        rank = successes + 1
    return rank


def median_bounds(values, alpha):
    """Exact conservative one-sided bounds for the population median of run ratios."""
    require(values and 0 < alpha < 0.5 and all(number(value) for value in values), "invalid ratio samples")
    ordered = sorted(values)
    rank = order_rank(len(values), alpha)
    if not rank:
        return None, None  # Unbounded; encode without nonstandard JSON infinity.
    return ordered[rank - 1], ordered[len(values) - rank]


def binomial_upper_tail(count, probability, successes):
    if successes <= 0:
        return 1.0
    if successes > count or probability == 0:
        return 0.0
    if probability == 1:
        return 1.0
    terms = [math.lgamma(count + 1) - math.lgamma(value + 1) - math.lgamma(count - value + 1)
             + value * math.log(probability) + (count - value) * math.log1p(-probability)
             for value in range(successes, count + 1)]
    maximum = max(terms)
    return min(1.0, math.exp(maximum) * math.fsum(math.exp(term - maximum) for term in terms))


def probability_lower_bound(successes, count, confidence):
    if successes == 0:
        return 0.0
    left, right = 0.0, 1.0
    for _ in range(60):
        middle = (left + right) / 2
        if binomial_upper_tail(count, middle, successes) < 1 - confidence:
            left = middle
        else:
            right = middle
    return left


@functools.lru_cache(maxsize=1024)
def planned_pairs(successes, pilot_count, confidence, power, alpha, minimum, maximum):
    probability = probability_lower_bound(successes, pilot_count, confidence)
    require(probability > 0.5, "A/A does not support sample-size planning; collect a larger A/A before freezing")
    for count in range(minimum, maximum + 1):
        rank = order_rank(count, alpha)
        if rank and binomial_upper_tail(count, probability, count - rank + 1) >= power:
            return count, probability
    raise ValueError("planned confirmatory sample exceeds predeclared cap; improve controls or extend A/A")


def validate_schedule(schedule):
    verify_seal(schedule)
    validate_spec(schedule["spec"])
    require(schedule["machine_id"] == schedule["spec"]["machine_id"], "schedule machine mismatch")
    require(schedule["phase"] in ("AA", "AB"), "unknown phase")
    require(integer(schedule["pairs"], 5), "invalid pair count")
    require(len(schedule["jobs"]) == 2 * schedule["pairs"] * len(schedule["spec"]["cases"]), "incomplete schedule")
    utc(schedule["created_utc"])
    cases = {case["id"]: case for case in schedule["spec"]["cases"]}
    seen, overlays = set(), set()
    candidate_manifest = None
    for ordinal, job in enumerate(schedule["jobs"]):
        require(job["ordinal"] == ordinal and job["arm"] in ("A", "B")
                and integer(job["pair_index"]) and job["pair_index"] < schedule["pairs"], "invalid scheduled job")
        require(job["case"] == cases[job["case_id"]], "job changed frozen case")
        key = job["pair_index"], job["case_id"], job["arm"]
        require(key not in seen and job["overlay_id"] not in overlays, "duplicate job or overlay")
        seen.add(key)
        overlays.add(job["overlay_id"])
        validate_manifest(job["manifest"])
        require(job["manifest_sha256"] == digest(job["manifest"]), "job manifest hash mismatch")
        if job["arm"] == "A" or schedule["phase"] == "AA":
            require(job["manifest"] == schedule["spec"]["baseline"], "A/A must use exact baseline only")
        else:
            if candidate_manifest is None:
                candidate_manifest = job["manifest"]
            require(job["manifest"] == candidate_manifest, "candidate manifest changed across scheduled jobs")
            for field in FIXED_MANIFEST_FIELDS:
                require(job["manifest"][field] == schedule["spec"]["baseline"][field],
                        f"candidate manifest changed pinned {field}")
    if schedule["phase"] == "AA":
        require(schedule["pairs"] == schedule["spec"]["pilot_pairs"], "A/A pair count changed")
    rebuilt = make_schedule(schedule["spec"], schedule["phase"], schedule["pairs"], candidate_manifest,
                            schedule.get("calibration_sha256"))
    require(schedule["jobs"] == rebuilt["jobs"], "jobs changed deterministic paired schedule")


def inspect_records(schedule, records):
    """Return valid run metrics and explicit issues; never drop a failed attempt."""
    validate_schedule(schedule)
    expected = {job["attempt_id"]: job for job in schedule["jobs"]}
    actual, issues, failures, metrics = {}, [], [], {}
    inspected_utc = datetime.datetime.now(datetime.timezone.utc)
    for record in records:
        require(isinstance(record, dict), "result must be an object")
        attempt = record.get("attempt_id")
        require(attempt in expected, "unscheduled attempt; no post-hoc extra runs allowed")
        require(attempt not in actual, "duplicate attempt; retries cannot replace failures")
        actual[attempt] = record
    previous_end = None
    for job in schedule["jobs"]:
        attempt = job["attempt_id"]
        record = actual.get(attempt)
        if record is None:
            issues.append(f"{attempt}: missing attempt")
            continue
        try:
            require(record.get("schema_version") == 1, "result schema_version must be 1")
            for field, wanted in {"schedule_sha256": schedule["sha256"], "machine_id": schedule["machine_id"],
                                  "environment_sha256": digest(schedule["spec"]["environment"]),
                                  "runner_sha256": schedule["spec"]["runner_sha256"],
                                  **{key: job[key] for key in ("ordinal", "pair_index", "arm", "case_id",
                                                               "manifest_sha256", "workload_seed", "overlay_id")}}.items():
                require(record.get(field) == wanted, f"{field} mismatch")
            start, end = utc(record.get("started_utc")), utc(record.get("finished_utc"))
            require(end > start and start >= utc(schedule["created_utc"]), "invalid attempt time range")
            require(end <= inspected_utc, "attempt finish timestamp is in the future")
            require(previous_end is None or start >= previous_end, "attempts overlapped or ignored scheduled order")
            previous_end = end
            require(record.get("fresh_process") is True and record.get("fresh_overlay") is True,
                    "requires independent fresh process and overlay")
            require(record.get("tracing") is False and record.get("expensive_guest_clocks") is False,
                    "traced/expensive-clock runs are diagnostic only")
            prep = record.get("cache_preparation", {})
            require(isinstance(prep, dict) and prep.get("success") is True
                    and isinstance(prep.get("details"), str) and prep["details"]
                    and prep.get("policy_sha256") == digest(schedule["spec"]["cache_policies"][job["cache_policy"]]),
                    "cache preparation missing or changed")
            require(record.get("status") in ("ok", "timeout", "error", "aborted"), "unknown attempt status")
            if record["status"] != "ok":
                failures.append(f"{attempt}: {record['status']}: {record.get('error')}")
                continue
            require("error" in record, "successful attempt must explicitly record error=null")
            if record["error"] is not None:
                failures.append(f"{attempt}: successful status contradicts recorded error: {record['error']}")
                continue
            case = job["case"]
            if case["kind"] == "dvd-xiso":
                require(record.get("media_sha256") == case["iso_sha256"], "optical variant media hash mismatch")
            require(record.get("timing_scope") == "caller-issue-to-consumer-ready", "shorter timing scope")
            require(integer(record.get("operations_completed")), "missing completed operation count")
            if (record["operations_completed"] != case["operations"]
                    or record.get("bytes_completed") != case["operations"] * case["bytes_per_operation"]
                    or record.get("assertions_executed") != case["assertions"]
                    or record.get("assertions_failed") != 0 or record.get("integrity_sha256") != case["expected_sha256"]):
                failures.append(f"{attempt}: incomplete operations/assertions, failed assertion or checksum")
                continue
            if case["kind"] == "write-flush" and (record.get("flushes_completed") != case["real_flushes"]
                                                   or record.get("durability_verified") is not True):
                failures.append(f"{attempt}: real flush or persistence verification missing")
                continue
            require(number(record.get("elapsed_ms")), "invalid end-to-end batch latency")
            require(record["elapsed_ms"] <= (end - start).total_seconds() * 1000,
                    "batch latency exceeds attempt wall time")
            samples = record.get("latencies_ms")
            require(isinstance(samples, list) and len(samples) == case["operations"]
                    and all(number(value) and value <= record["elapsed_ms"] for value in samples),
                    "missing/invalid operation latency evidence")
            counters = record.get("counters", {})
            if case["kind"] == "small-hdd-read":
                require(isinstance(counters, dict) and all(integer(counters.get(key)) for key in
                        ("upper_worker_hops", "allocations", "bounce_copies", "lower_commands", "interrupts")),
                        "missing healthy-path structural counters")
            ordered = sorted(samples)
            metrics[attempt] = {"latency": record["elapsed_ms"],
                                "throughput": record["bytes_completed"] / record["elapsed_ms"],
                                "p50": ordered[math.ceil(len(samples) * .5) - 1],
                                "p95": ordered[math.ceil(len(samples) * .95) - 1],
                                "p99": ordered[math.ceil(len(samples) * .99) - 1]}
        except (ValueError, KeyError, TypeError) as error:
            issues.append(f"{attempt}: {error}")
    return metrics, issues, failures, actual


def pair_metrics(schedule, run_metrics):
    result = {case["id"]: {metric: [] for metric in METRICS} for case in schedule["spec"]["cases"]}
    grouped = {}
    for job in schedule["jobs"]:
        if job["attempt_id"] in run_metrics:
            grouped.setdefault((job["case_id"], job["pair_index"]), {})[job["arm"]] = run_metrics[job["attempt_id"]]
    for (case_id, _), arms in sorted(grouped.items()):
        if set(arms) == {"A", "B"}:
            for metric in METRICS:
                result[case_id][metric].append(arms["B"][metric] / arms["A"][metric])
    return result


def derive_planning(spec, ratios):
    """Rebuild every planning gate exclusively from complete baseline A/A facts."""
    require(isinstance(ratios, dict) and set(ratios) == {case["id"] for case in spec["cases"]},
            "A/A planning facts must cover every case")
    tests = len(spec["cases"]) * len(METRICS)
    alpha = 0.05 / (2 * tests)
    gate_power = 1 - (1 - spec["planning_power"]) / tests
    count = spec["minimum_confirmatory_pairs"]
    planning = []
    for case in spec["cases"]:
        case_ratios = ratios[case["id"]]
        require(isinstance(case_ratios, dict) and set(case_ratios) == set(METRICS),
                "A/A planning facts must cover every metric")
        for metric in METRICS:
            values = case_ratios[metric]
            require(isinstance(values, list) and len(values) == spec["pilot_pairs"]
                    and all(number(value) for value in values), "A/A planning ratio count/values invalid")
            limit = spec["limits"][metric]
            successes = sum(value >= limit if metric == "throughput" else value <= limit for value in values)
            needed, probability = planned_pairs(successes, len(values), spec["planning_confidence"], gate_power,
                                                 alpha, spec["minimum_confirmatory_pairs"],
                                                 spec["maximum_confirmatory_pairs"])
            count = max(count, needed)
            planning.append({"case_id": case["id"], "metric": metric, "pilot_pairs": len(values),
                             "ratios": list(values), "inside_margin": successes, "planning_probability_lower": probability,
                             "recommended_pairs": needed})
    return count, planning


def calibrate(schedule, records, results_sha256):
    require(schedule.get("phase") == "AA", "calibration requires A/A only")
    require(hash_string(results_sha256), "pin raw pilot results hash")
    run_metrics, issues, failures, _ = inspect_records(schedule, records)
    require(not issues and not failures, "A/A invalid: " + "; ".join((issues + failures)[:10]))
    require(max(utc(record["finished_utc"]) for record in records)
            <= datetime.datetime.now(datetime.timezone.utc), "A/A timestamps extend beyond calibration time")
    spec = schedule["spec"]
    ratios = pair_metrics(schedule, run_metrics)
    count, planning = derive_planning(spec, ratios)
    return seal({"schema_version": 1, "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "machine_id": spec["machine_id"], "spec": spec,
                 "pilot_schedule_sha256": schedule["sha256"], "pilot_results_sha256": results_sha256,
                 "confirmatory_pairs": count, "family_confidence": 0.95,
                 "one_sided_alpha": .05 / (2 * len(spec["cases"]) * len(METRICS)),
                 "method": METHOD,
                 "pilot_ratios": ratios, "planning": planning,
                 "planning_warning": "Exploratory per-gate pilot probability bounds; projected power is not guaranteed."})


def validate_calibration(calibration):
    verify_seal(calibration)
    validate_spec(calibration["spec"])
    spec = calibration["spec"]
    require(calibration.get("machine_id") == spec["machine_id"], "calibration machine mismatch")
    require(integer(calibration.get("confirmatory_pairs"), spec["minimum_confirmatory_pairs"])
            and calibration["confirmatory_pairs"] <= spec["maximum_confirmatory_pairs"],
            "calibration count violates predeclared minimum/cap")
    require(calibration.get("family_confidence") == .95 and calibration.get("method") == METHOD
            and calibration.get("one_sided_alpha") == .05 / (2 * len(spec["cases"]) * len(METRICS)),
            "calibration confidence method changed")
    require(hash_string(calibration.get("pilot_schedule_sha256"))
            and hash_string(calibration.get("pilot_results_sha256")), "calibration lacks pilot identities")
    try:
        count, planning = derive_planning(spec, calibration.get("pilot_ratios"))
    except ValueError as error:
        raise ValueError(f"calibration pilot facts invalid: {error}") from error
    require(calibration.get("planning") == planning, "calibration planning derivation missing or inconsistent")
    require(calibration["confirmatory_pairs"] == count, "calibration count differs from A/A planning derivation")
    utc(calibration["created_utc"])


def make_confirmatory(calibration, candidate):
    validate_calibration(calibration)
    validate_manifest(candidate)
    baseline = calibration["spec"]["baseline"]
    for field in FIXED_MANIFEST_FIELDS:
        require(candidate[field] == baseline[field], f"candidate changed pinned {field}")
    return make_schedule(calibration["spec"], "AB", calibration["confirmatory_pairs"], candidate, calibration["sha256"])


def compare(calibration, schedule, records, results_sha256):
    validate_calibration(calibration)
    require(schedule.get("phase") == "AB" and schedule.get("calibration_sha256") == calibration["sha256"],
            "A/B schedule must bind frozen calibration")
    require(schedule["spec"] == calibration["spec"] and schedule["pairs"] == calibration["confirmatory_pairs"],
            "A/B rules/count changed after calibration")
    require(utc(schedule["created_utc"]) >= utc(calibration["created_utc"]), "A/B precedes frozen calibration")
    require(hash_string(results_sha256), "pin raw candidate results hash")
    run_metrics, issues, failures, actual = inspect_records(schedule, records)
    ratios = pair_metrics(schedule, run_metrics)
    cases = []
    for case in schedule["spec"]["cases"]:
        metrics, verdicts = {}, []
        jobs = [job for job in schedule["jobs"] if job["case_id"] == case["id"]]
        for metric in METRICS:
            values = ratios[case["id"]][metric]
            lower, upper = median_bounds(values, calibration["one_sided_alpha"]) if values else (None, None)
            limit = calibration["spec"]["limits"][metric]
            if len(values) != calibration["confirmatory_pairs"] or lower is None:
                verdict = "INCONCLUSIVE"
            elif metric == "throughput":
                verdict = "PASS" if lower >= limit else "REGRESSION" if upper < limit else "INCONCLUSIVE"
            else:
                verdict = "PASS" if upper <= limit else "REGRESSION" if lower > limit else "INCONCLUSIVE"
            verdicts.append(verdict)
            raw = {arm: [run_metrics[job["attempt_id"]][metric] for job in jobs
                         if job["arm"] == arm and job["attempt_id"] in run_metrics] for arm in ("A", "B")}
            metrics[metric] = {"verdict": verdict, "pairs": len(values), "limit": limit, "lower": lower,
                               "upper": upper, "median_ratio": statistics.median(values) if values else None,
                               "ratios": values, "baseline_runs": raw["A"], "candidate_runs": raw["B"],
                               "baseline_median": statistics.median(raw["A"]) if raw["A"] else None,
                               "candidate_median": statistics.median(raw["B"]) if raw["B"] else None}
        if case["kind"] == "small-hdd-read":
            paired = {}
            for job in jobs:
                if job["attempt_id"] in run_metrics:
                    paired.setdefault(job["pair_index"], {})[job["arm"]] = actual[job["attempt_id"]]["counters"]
            for pair, arms in paired.items():
                if set(arms) == {"A", "B"}:
                    for counter in ("upper_worker_hops", "allocations", "bounce_copies", "lower_commands", "interrupts"):
                        if arms["B"][counter] > arms["A"][counter]:
                            failures.append(f"{case['id']}/pair-{pair}: increased {counter}")
                            verdicts.append("REGRESSION")
        prefixes = tuple(job["attempt_id"] + ":" for job in jobs)
        case_failures = [failure for failure in failures
                         if failure.startswith(prefixes) or failure.startswith(case["id"] + "/pair-")]
        case_issues = [issue for issue in issues if issue.startswith(prefixes)]
        if case_failures:
            verdicts.append("REGRESSION")
        if case_issues:
            verdicts.append("INCONCLUSIVE")
        case_verdict = "REGRESSION" if "REGRESSION" in verdicts else "INCONCLUSIVE" if "INCONCLUSIVE" in verdicts else "PASS"
        cases.append({"case_id": case["id"], "cache_policy": case["cache_policy"],
                      "verdict": case_verdict, "metrics": metrics, "failures": case_failures, "issues": case_issues})
    verdicts = [case["verdict"] for case in cases]
    verdict = "REGRESSION" if failures or "REGRESSION" in verdicts else "INCONCLUSIVE" if issues or "INCONCLUSIVE" in verdicts else "PASS"
    return {"schema_version": 1, "verdict": verdict, "machine_id": schedule["machine_id"],
            "machine_role": schedule["spec"]["machine_role"], "method": calibration["method"],
            "family_confidence": calibration["family_confidence"], "one_sided_alpha": calibration["one_sided_alpha"],
            "calibration_sha256": calibration["sha256"], "schedule_sha256": schedule["sha256"],
            "results_sha256": results_sha256, "attempts_planned": len(schedule["jobs"]),
            "attempts_recorded": len(records), "valid_runs": len(run_metrics),
            "attempts": [{key: record.get(key) for key in
                          ("attempt_id", "ordinal", "pair_index", "arm", "case_id", "started_utc", "finished_utc",
                           "status", "error", "operations_completed", "bytes_completed", "assertions_executed",
                           "assertions_failed", "flushes_completed", "integrity_sha256")}
                         for record in (actual[job["attempt_id"]] for job in schedule["jobs"]
                                        if job["attempt_id"] in actual)],
            "issues": issues, "failures": failures, "cases": cases,
            "units": {"latency": "ms per batch", "throughput": "bytes/ms", "p95": "ms per request", "p99": "ms per request"}}


def make_schedule(spec, phase="AA", pairs=None, candidate=None, calibration=None):
    validate_spec(spec)
    rng = random.Random(spec["seeds"]["schedule"])
    manifests = {"A": spec["baseline"], "B": candidate or spec["baseline"]}
    jobs = []
    for pair in range(pairs or spec["pilot_pairs"]):
        cases = list(spec["cases"])
        rng.shuffle(cases)
        arms = ["A", "B"] if pair % 2 == 0 else ["B", "A"]
        if spec["order"] == "random":
            rng.shuffle(arms)
        for case in cases:
            for arm in arms:
                ordinal = len(jobs)
                jobs.append({"attempt_id": f"{phase}-{pair}-{case['id']}-{arm}",
                             "ordinal": ordinal, "pair_index": pair, "arm": arm,
                             "case_id": case["id"], "case": case,
                             "manifest": manifests[arm], "manifest_sha256": digest(manifests[arm]),
                             "cache_policy": case["cache_policy"],
                             "workload_seed": spec["seeds"]["workload"] + pair,
                             "overlay_id": f"{phase}-{ordinal:06d}",
                             "fresh_process_required": True})
    return seal({"schema_version": 1, "phase": phase, "machine_id": spec["machine_id"],
                 "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 "spec": spec, "pairs": pairs or spec["pilot_pairs"],
                 "calibration_sha256": calibration, "jobs": jobs})


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def unique_json_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, f"duplicate JSON key: {key}")
        value[key] = item
    return value


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=unique_json_object)


def read_results(path):
    raw = Path(path).read_bytes()
    records = []
    for line_number, line in enumerate(raw.decode("utf-8-sig").splitlines(), 1):
        require(line.strip(), f"blank JSONL line {line_number}")
        try:
            records.append(json.loads(line, object_pairs_hook=unique_json_object))
        except ValueError as error:
            raise ValueError(f"invalid JSONL line {line_number}: {error}") from error
    return records, hashlib.sha256(raw).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    pilot = commands.add_parser("pilot", help="schedule baseline against itself")
    pilot.add_argument("--spec", required=True)
    pilot.add_argument("--output", required=True)
    freeze = commands.add_parser("calibrate", help="freeze rules and count from complete baseline-only A/A")
    freeze.add_argument("--schedule", required=True)
    freeze.add_argument("--results", required=True)
    freeze.add_argument("--output", required=True)
    confirm = commands.add_parser("confirmatory", help="bind candidate identity after calibration")
    confirm.add_argument("--calibration", required=True)
    confirm.add_argument("--candidate", required=True)
    confirm.add_argument("--output", required=True)
    analyze = commands.add_parser("compare", help="decide every case from the frozen paired A/B")
    analyze.add_argument("--calibration", required=True)
    analyze.add_argument("--schedule", required=True)
    analyze.add_argument("--results", required=True)
    analyze.add_argument("--output", help="exclusive output file; default stdout")
    args = parser.parse_args(argv)
    try:
        if args.command == "pilot":
            write_json(args.output, make_schedule(read_json(args.spec)))
        elif args.command == "calibrate":
            records, raw_hash = read_results(args.results)
            write_json(args.output, calibrate(read_json(args.schedule), records, raw_hash))
        elif args.command == "confirmatory":
            write_json(args.output, make_confirmatory(read_json(args.calibration), read_json(args.candidate)))
        else:
            records, raw_hash = read_results(args.results)
            report = compare(read_json(args.calibration), read_json(args.schedule), records, raw_hash)
            if args.output:
                write_json(args.output, report)
            else:
                print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))
            return {"PASS": 0, "REGRESSION": 1, "INCONCLUSIVE": 2}[report["verdict"]]
        return 0
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps({"verdict": "INCONCLUSIVE", "error": str(error)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
