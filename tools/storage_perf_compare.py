#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
# Copyright (C) 2026 SpiritBoot contributors
"""Independent paired storage experiment scheduling and recorded-result analysis."""
import argparse
import bisect
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
STRUCTURAL_UNITS = {
    "upper_worker_hops": "upper-request-worker-executions",
    "allocations": "successful-new-storage-pool-allocations",
    "bounce_copies": "bounce-copy-operations",
    "lower_commands": "physical-command-issue-attempts",
    "interrupts": "storage-isr-entries",
}
WORKLOAD_FIELDS = ("workload_seed_semantics", "workload_policy_sha256", "workload_identity_sha256")
PUBLIC_TIMING_REL_TOL = 8 * sys.float_info.epsilon


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
    if "structural_policy" in spec:
        policy = spec["structural_policy"]
        require(isinstance(policy, dict) and policy.get("schema_version") == 1
                and policy.get("mode") == "diagnostic-companion", "unknown structural policy")
        require(isinstance(policy.get("method"), str) and policy["method"].strip(),
                "pin structural capture method")
        require(isinstance(policy.get("route_id"), str) and policy["route_id"].strip(),
                "pin structural route_id")
        for field in ("coverage_plan_sha256", "correspondence_rules_sha256"):
            require(hash_string(policy.get(field)), f"pin structural {field}")
        if "collector_sha256" in policy:
            require(hash_string(policy["collector_sha256"]), "invalid optional structural collector pin")
        require(policy.get("counter_units") == STRUCTURAL_UNITS,
                "structural counter units must preserve all five healthy-path gates")
    if "durability_policy" in spec:
        policy = spec["durability_policy"]
        require(isinstance(policy, dict) and policy.get("schema_version") == 1
                and policy.get("mode") == "diagnostic-companion"
                and policy.get("timing_workload") == "public-api-flush-reopen"
                and policy.get("persistence_scope") == "device-cache-sync-and-persistence",
                "unknown separated durability policy")
        require(isinstance(policy.get("method"), str) and policy["method"].strip(), "pin physical method")
        for field in ("coverage_plan_sha256", "correspondence_rules_sha256"):
            require(hash_string(policy.get(field)), f"pin durability {field}")
        if "collector_sha256" in policy:
            require(hash_string(policy["collector_sha256"]), "invalid optional physical collector pin")
        validate_descriptor(policy.get("timing_contract"))
    if "workload_policy" in spec:
        policy = spec["workload_policy"]
        require(isinstance(policy, dict) and policy.get("schema_version") == 1
                and policy.get("mode") == "fixture-fixed" and policy.get("seed_semantics") == "METADATA_ONLY"
                and policy.get("fixture_sha256") == spec["baseline"]["fixture_sha256"],
                "fixed workload requires exact fixture and METADATA_ONLY semantics")
        validate_descriptor(policy.get("fixture_contract"))
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
        require(("bytes_per_operation" in case) != ("operation_bytes" in case),
                "pin exactly one of bytes_per_operation or operation_bytes")
        if "operation_bytes" in case:
            lengths = case["operation_bytes"]
            require(isinstance(lengths, list) and len(lengths) == case["operations"]
                    and all(integer(length, 1) for length in lengths),
                    "pin every operation byte count in issue order")
        else:
            require(integer(case["bytes_per_operation"], 1), "pin positive operation byte count")
        require(integer(case.get("assertions"), 1), "pin correctness assertion count")
        require(hash_string(case.get("expected_sha256")), "pin expected checksum")
        kind = case.get("kind")
        require(kind in ("small-hdd-read", "fatx-read", "write-flush", "dvd-xiso", "boundary-sg"),
                "unknown workload kind")
        if kind == "small-hdd-read":
            require(case.get("queue_depth") == 1 and integer(case.get("request_bytes"), 512)
                    and case["request_bytes"] <= 4096 and case["request_bytes"] % 512 == 0
                    and integer(case.get("alignment_bytes"), 512) and case["alignment_bytes"] % 512 == 0,
                    "small HDD path must be aligned QD1")
            require((all(length == case["request_bytes"] for length in case["operation_bytes"])
                     if "operation_bytes" in case else case["bytes_per_operation"] == case["request_bytes"]),
                    "small HDD byte counts must match its declared request size")
        elif kind == "fatx-read":
            require(case["operations"] == 1024 and case.get("queue_depth") in (1, 4, 12)
                    and case.get("pressure_pages") in (0, 900), "FATX sequences require 1024 reads/QD1,4,12/0,900 pages")
            require(isinstance(case.get("sequence"), str) and case["sequence"]
                    and hash_string(case.get("sequence_sha256")), "pin FATX sequence identities")
            previous = sequences.setdefault(case["sequence"], case["sequence_sha256"])
            require(previous == case["sequence_sha256"], "sequence hash changed between cases")
        elif kind == "write-flush":
            require(integer(case.get("real_flushes"), 1), "write case requires actual device flushes")
            if "durability_policy" in spec:
                require(integer(case.get("api_flush_calls"), 1) and case["api_flush_calls"] == case["operations"]
                        and case["assertions"] == 11 * case["operations"],
                        "generation2 public timing requires every API flush and all eleven checks per operation")
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


def validate_descriptor(value):
    require(isinstance(value, dict) and hash_string(value.get("sha256"))
            and isinstance(value.get("path"), str) and value["path"].strip()
            and not Path(value["path"]).is_absolute(), "policy artifact needs relative path and hash")


def fixed_workload_fields(spec, case):
    policy = spec["workload_policy"]
    return {"workload_seed_semantics": "METADATA_ONLY", "workload_policy_sha256": digest(policy),
            "workload_identity_sha256": digest({"policy_sha256": digest(policy),
                                               "fixture_sha256": policy["fixture_sha256"], "case": case})}


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


def inspect_records(schedule, records, *, evidence_root=None):
    """Return valid run metrics and explicit issues; never drop a failed attempt."""
    validate_schedule(schedule)
    expected = {job["attempt_id"]: job for job in schedule["jobs"]}
    actual, issues, failures, metrics, evidence_cache = {}, [], [], {}, {}
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
            for field in WORKLOAD_FIELDS:
                if field in job:
                    require(record.get(field) == job[field], f"{field} mismatch")
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
            if "workload_policy" in schedule["spec"]:
                validate_public_contract(schedule, job, "workload_policy", record, evidence_root, evidence_cache)
            if case["kind"] == "dvd-xiso":
                require(record.get("media_sha256") == case["iso_sha256"], "optical variant media hash mismatch")
            require(record.get("timing_scope") == "caller-issue-to-consumer-ready", "shorter timing scope")
            require(integer(record.get("operations_completed")), "missing completed operation count")
            if "operation_bytes" in case or "operation_bytes" in record:
                expected_lengths = case.get("operation_bytes")
                if expected_lengths is None:
                    expected_lengths = [case["bytes_per_operation"]] * case["operations"]
                observed_lengths = record.get("operation_bytes")
                require(isinstance(observed_lengths, list) and len(observed_lengths) == case["operations"]
                        and all(integer(length, 0) for length in observed_lengths),
                        "missing/invalid per-operation byte evidence")
                if observed_lengths != expected_lengths:
                    failures.append(f"{attempt}: per-operation byte counts differ from frozen requests")
                    continue
                expected_bytes = sum(expected_lengths)
            else:
                expected_bytes = case["operations"] * case["bytes_per_operation"]
            if (record["operations_completed"] != case["operations"]
                    or record.get("bytes_completed") != expected_bytes
                    or record.get("assertions_executed") != case["assertions"]
                    or record.get("assertions_failed") != 0 or record.get("integrity_sha256") != case["expected_sha256"]):
                failures.append(f"{attempt}: incomplete operations/assertions, failed assertion or checksum")
                continue
            if case["kind"] == "write-flush":
                if "durability_policy" in schedule["spec"]:
                    problem = validate_public_write(schedule, job, record, evidence_root, evidence_cache)
                    if problem:
                        failures.append(f"{attempt}: {problem}")
                        continue
                elif record.get("flushes_completed") != case["real_flushes"] or record.get("durability_verified") is not True:
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
            if case["kind"] == "small-hdd-read" and "structural_policy" not in schedule["spec"]:
                require(isinstance(counters, dict) and all(integer(counters.get(key)) for key in
                        STRUCTURAL_UNITS),
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


def calibrate(schedule, records, results_sha256, *, evidence_root=None):
    require(schedule.get("phase") == "AA", "calibration requires A/A only")
    require(hash_string(results_sha256), "pin raw pilot results hash")
    run_metrics, issues, failures, _ = inspect_records(schedule, records, evidence_root=evidence_root)
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


def read_structural_artifact(descriptor, evidence_root, cache, as_json=False):
    """Verify immutable companion evidence inside the supplied evidence directory."""
    require(isinstance(descriptor, dict) and hash_string(descriptor.get("sha256")),
            "structural artifact lacks hash")
    name = descriptor.get("path")
    require(isinstance(name, str) and name.strip() and not Path(name).is_absolute(),
            "structural artifact requires relative path")
    require(evidence_root is not None, "structural evidence directory missing")
    root = Path(evidence_root).resolve()
    path = (root / name).resolve()
    require(path.is_relative_to(root) and path.is_file(), "structural artifact outside evidence directory or missing")
    key = (path, descriptor["sha256"])
    if key not in cache:
        raw = path.read_bytes()
        require(hashlib.sha256(raw).hexdigest() == descriptor["sha256"], "structural artifact hash mismatch")
        cache[key] = raw
    if as_json:
        return json.loads(cache[key].decode("utf-8-sig"), object_pairs_hook=unique_json_object)
    return descriptor["sha256"]


def validate_public_contract(schedule, job, policy_key, record, evidence_root, cache):
    """Check frozen public fixture facts; factual independent review remains external."""
    policy = schedule["spec"][policy_key]
    public = policy_key == "durability_policy"
    descriptor = policy["timing_contract" if public else "fixture_contract"]
    contract = read_structural_artifact(descriptor, evidence_root, cache, as_json=True)
    require(isinstance(contract, dict) and contract.get("schema_version") == 1
            and contract.get("contract") == ("public-api-flush-reopen" if public else "fixture-fixed")
            and contract.get("fixture_sha256") == job["manifest"]["fixture_sha256"]
            and contract.get("method_qualified") is True, "public fixture contract mismatch or unqualified")
    require(utc(contract.get("reviewed_utc")) < utc(record["started_utc"]), "public contract reviewed after capture")
    require(contract.get("cases") == {case["id"]: digest(case) for case in schedule["spec"]["cases"]},
            "public contract changed frozen case/request identities")
    require(read_structural_artifact(contract.get("fixture_artifact"), evidence_root, cache)
            == job["manifest"]["fixture_sha256"], "public contract fixture bytes differ")
    sources = contract.get("source_artifacts")
    require(isinstance(sources, list) and sources, "public fixture source artifacts missing")
    for source in sources:
        read_structural_artifact(source, evidence_root, cache)
    if public:
        require(contract.get("fixture_generation") == 2 and contract.get("assertions_per_operation") == 11,
                "public readback requires generation2 full comparison semantics")
        require(contract.get("timing_conversion") == "recorded-rdtsc-frequency",
                "public timing conversion missing or unsupported")
        read_structural_artifact(contract.get("parser_artifact"), evidence_root, cache)
        for field in ("coverage_plan", "correspondence_rules"):
            require(read_structural_artifact(contract.get(field), evidence_root, cache) == policy[field + "_sha256"],
                    "public contract changed frozen physical plan/rules")
    else:
        require(contract.get("seed_semantics") == "METADATA_ONLY", "fixed label cannot claim a guest seed")
    return contract


def native_integer(value, base=10):
    pattern = r"[0-9]+" if base == 10 else r"[0-9a-fA-F]{8}"
    require(isinstance(value, str) and re.fullmatch(pattern, value) is not None,
            "raw public integer missing or invalid; no default values")
    return int(value, base)


def validate_public_milliseconds(observed, ticks, frequency):
    require(0 < ticks < 2**64 and 0 < frequency < 2**64, "public raw counter/frequency outside positive uint64")
    expected = ticks * 1000 / frequency
    try:
        consistent = number(observed) and math.isclose(observed, expected, rel_tol=PUBLIC_TIMING_REL_TOL, abs_tol=0.0)
    except OverflowError:
        consistent = False  # A malformed reported JSON integer remains attributable unknown evidence.
    require(number(expected) and consistent,
            "public timing does not map raw ticks through recorded RDTSC frequency")


def validate_public_write(schedule, job, record, evidence_root, cache):
    """Qualify API timing only; never infer a physical cache-sync or persistence fact."""
    policy, case = schedule["spec"]["durability_policy"], job["case"]
    require(record.get("durability_policy_sha256") == digest(policy), "durability policy mismatch")
    contract = validate_public_contract(schedule, job, "durability_policy", record, evidence_root, cache)
    ledger = read_structural_artifact(record.get("api_timing_provenance"), evidence_root, cache, as_json=True)
    require(isinstance(ledger, dict) and ledger.get("schema_version") == 1, "public raw ledger missing")
    wanted = {"case_sha256": digest(case), "fixture_sha256": job["manifest"]["fixture_sha256"],
              "parser_sha256": contract["parser_artifact"]["sha256"],
              "durability_policy_sha256": digest(policy), "timing_contract_sha256": policy["timing_contract"]["sha256"],
              "timing_sha256": digest({key: record.get(key) for key in ("elapsed_ms", "latencies_ms", "timing_scope")}),
              **{key: record[key] for key in ("attempt_id", "schedule_sha256", "manifest_sha256",
                                             "environment_sha256", "runner_sha256")},
              **{key: job[key] for key in WORKLOAD_FIELDS if key in job}}
    require(all(key in ledger and ledger[key] == value for key, value in wanted.items()),
            "public raw ledger identity/timing mapping mismatch")
    meta, summary, end = (ledger.get(key) for key in ("meta", "summary", "end"))
    require(isinstance(meta, dict) and meta.get("version") == "1" and meta.get("fixture_generation") == "2"
            and meta.get("counter") == "rdtsc" and native_integer(meta.get("frequency")) > 0,
            "public raw generation/counter metadata missing")
    frequency = native_integer(meta["frequency"])
    require(isinstance(summary, dict) and summary.get("id") == case["id"]
            and summary.get("cache") == case["cache_policy"] and isinstance(end, dict)
            and native_integer(end.get("cases")) == 1, "public raw complete case/end evidence missing")
    lengths = case.get("operation_bytes", [case.get("bytes_per_operation")] * case["operations"])
    require(native_integer(summary.get("operations")) == case["operations"]
            and native_integer(summary.get("bytes")) == sum(lengths)
            and native_integer(summary.get("assertions")) == case["assertions"]
            and native_integer(summary.get("ticks")) > 0, "public raw operation/byte/assertion mapping differs")
    validate_public_milliseconds(record.get("elapsed_ms"), native_integer(summary["ticks"]), frequency)
    flushes = native_integer(summary.get("flush_calls"))  # Never use the native parser's absent-field default.
    require(integer(record.get("flush_api_calls_completed")) and record["flush_api_calls_completed"] == flushes,
            "public flush count lacks matching raw observation")
    require(summary.get("persistence") in ("0", "1")
            and type(record.get("reopen_readback_verified")) is bool
            and record["reopen_readback_verified"] == (summary["persistence"] == "1"),
            "public reopen comparison missing or contradictory")
    operations = ledger.get("operations")
    require(isinstance(operations, list) and len(operations) == case["operations"],
            "public raw operations incomplete")
    samples = record.get("latencies_ms")
    require(isinstance(samples, list) and len(samples) == case["operations"], "public operation timings missing")
    bad = native_integer(summary.get("failures")) != 0 or native_integer(end.get("failures")) != 0
    for index, (operation, length) in enumerate(zip(operations, lengths)):
        require(isinstance(operation, dict) and operation.get("id") == case["id"]
                and native_integer(operation.get("index")) == index
                and native_integer(operation.get("ticks")) > 0, "public raw operation order/timing incomplete")
        validate_public_milliseconds(samples[index], native_integer(operation["ticks"]), frequency)
        bad |= (native_integer(operation.get("status"), 16) != 0
                or native_integer(operation.get("io_status"), 16) != 0
                or native_integer(operation.get("information")) != length)
    if bad or flushes != case["api_flush_calls"] or not record["reopen_readback_verified"]:
        return "observed public write/API-flush/reopen operation or integrity failure"
    return None


def validate_structural_row(schedule, job, row, timing, evidence_root, cache, embedded,
                            acceptance_overlays, acceptance_ids):
    """Validate declared native evidence; a reviewer still owns its factual qualification."""
    policy = schedule["spec"]["structural_policy"]
    require(isinstance(row, dict) and row.get("schema_version") == 1, "structural schema_version must be 1")
    require(row.get("status") == "ok" and "error" in row and row["error"] is None,
            "structural capture outcome is failed/partial/missing or contradictory")
    mode = "same-run" if embedded else "diagnostic-companion"
    require(row.get("capture_mode") == mode and row.get("diagnostic") is (not embedded),
            "structural capture must explicitly identify diagnostic versus same-run evidence")
    wanted = {
        "timing_attempt_id": job["attempt_id"], "schedule_sha256": schedule["sha256"],
        "calibration_sha256": schedule["calibration_sha256"], "policy_sha256": digest(policy),
        "method": policy["method"],
        "route_id": policy["route_id"],
        "machine_id": schedule["machine_id"],
        "environment_sha256": digest(schedule["spec"]["environment"]),
        "memory_profile": schedule["spec"]["environment"]["memory_profile"],
        "acceptance_manifest_sha256": job["manifest_sha256"], "case_sha256": digest(job["case"]),
        **{key: job[key] for key in ("case_id", "pair_index", "arm", "workload_seed")},
        **{key: job[key] for key in WORKLOAD_FIELDS if key in job},
    }
    for field, value in wanted.items():
        require(row.get(field) == value, f"structural {field} mismatch")
    require(hash_string(row.get("collector_sha256")), "structural actual collector hash missing")
    if "collector_sha256" in policy:
        require(row["collector_sha256"] == policy["collector_sha256"], "structural frozen collector mismatch")
    require(integer(row.get("pair_index")) and integer(row.get("workload_seed")),
            "structural pair/seed must be integers")
    run = row.get("capture_run_id")
    require(isinstance(run, str) and run.strip(), "structural capture_run_id missing")
    capture = row.get("capture_manifest")
    validate_manifest(capture)
    for field in FIXED_MANIFEST_FIELDS:
        # A diagnostic fixture may add markers, but its workload mapping needs qualified correspondence.
        if field != "fixture_sha256":
            require(capture[field] == job["manifest"][field], f"structural capture changed pinned {field}")
    start, end = utc(row.get("started_utc")), utc(row.get("finished_utc"))
    require(end > start and start >= utc(schedule["created_utc"])
            and end <= datetime.datetime.now(datetime.timezone.utc), "invalid structural capture time range")
    if embedded:
        require(capture == job["manifest"] and run == job["attempt_id"]
                and row.get("overlay_id") == job["overlay_id"], "same-run structural identity mismatch")
        require(row.get("started_utc") == timing.get("started_utc")
                and row.get("finished_utc") == timing.get("finished_utc")
                and row.get("counters") == timing.get("counters"), "same-run structural window/count mismatch")
    else:
        require(run not in acceptance_ids, "diagnostic capture cannot claim any scheduled timing identity")
        overlay = row.get("overlay_id")
        require(isinstance(overlay, str) and overlay.strip()
                and overlay not in acceptance_overlays,
                "diagnostic requires a separate overlay identity")
    require(row.get("fresh_process") is True and row.get("fresh_overlay") is True,
            "structural capture requires fresh process and overlay")
    prep = row.get("cache_preparation")
    require(isinstance(prep, dict) and prep.get("success") is True
            and isinstance(prep.get("details"), str) and prep["details"].strip()
            and prep.get("policy_sha256") == digest(schedule["spec"]["cache_policies"][job["cache_policy"]]),
            "structural cache preparation missing or changed")
    require(row.get("counter_scope") == "caller-issue-to-consumer-ready", "structural window is incomplete")
    coverage = row.get("coverage")
    require(isinstance(coverage, dict) and coverage.get("complete") is True
            and all(integer(coverage.get(key)) and coverage[key] == 0
                    for key in ("lost_events", "overflows", "ambiguous_events"))
            and integer(coverage.get("operations_observed"))
            and coverage["operations_observed"] == job["case"]["operations"]
            and isinstance(coverage.get("counter_keys"), list)
            and len(coverage["counter_keys"]) == len(STRUCTURAL_UNITS)
            and set(coverage["counter_keys"]) == set(STRUCTURAL_UNITS),
            "structural coverage incomplete/lost/overflowed/ambiguous")
    counters = row.get("counters")
    require(isinstance(counters, dict) and all(integer(counters.get(key)) for key in STRUCTURAL_UNITS),
            "structural counter missing/invalid; unavailable is not zero")
    artifacts = row.get("raw_artifacts")
    require(isinstance(artifacts, list) and artifacts and all(isinstance(item, dict) for item in artifacts),
            "structural raw evidence missing")
    ledgers = [item for item in artifacts if item.get("role") == "counter-ledger"]
    support = [item for item in artifacts if item.get("role") == "qualification-support"]
    routes = [item for item in artifacts if item.get("role") == "route-proof"]
    require(len(ledgers) == 1 and len(routes) == 1 and support
            and len({item.get("path") for item in artifacts}) == len(artifacts),
            "structural evidence needs one counter ledger, one route proof and distinct qualification support")
    hashes = {read_structural_artifact(item, evidence_root, cache) for item in artifacts}
    implementation = row.get("collector_implementation")
    require(isinstance(implementation, dict) and implementation.get("sha256") == row["collector_sha256"],
            "structural collector implementation hash mismatch")
    read_structural_artifact(implementation, evidence_root, cache)
    require(row.get("route_sha256") == routes[0]["sha256"], "structural route proof hash mismatch")
    route = read_structural_artifact(routes[0], evidence_root, cache, as_json=True)
    require(isinstance(route, dict) and route.get("schema_version") == 1
            and route.get("route_verified") is True and route.get("route_id") == policy["route_id"]
            and route.get("capture_run_id") == run and route.get("capture_manifest_sha256") == digest(capture),
            "structural runtime route unverified or mismatched")
    ledger = read_structural_artifact(ledgers[0], evidence_root, cache, as_json=True)
    require(isinstance(ledger, dict) and ledger.get("schema_version") == 1,
            "structural counter ledger schema mismatch")
    for field in ("capture_run_id", "timing_attempt_id", "schedule_sha256", "counter_scope", "policy_sha256",
                  "counters", "coverage", "route_sha256", "status", "error"):
        require(field in ledger, f"structural counter ledger {field} missing")
        require(ledger.get(field) == row.get(field), f"structural counter ledger {field} mismatch")
    qualification = read_structural_artifact(row.get("qualification"), evidence_root, cache, as_json=True)
    require(isinstance(qualification, dict) and qualification.get("schema_version") == 1,
            "structural qualification schema mismatch")
    for field, value in {
        "policy_sha256": digest(policy), "capture_manifest_sha256": digest(capture),
        "acceptance_manifest_sha256": job["manifest_sha256"], "case_sha256": digest(job["case"]),
        "environment_sha256": wanted["environment_sha256"], "capture_mode": mode,
        "route_id": policy["route_id"],
        "method": policy["method"], "collector_sha256": row["collector_sha256"],
    }.items():
        require(qualification.get(field) == value, f"structural qualification {field} mismatch")
    require(utc(qualification.get("reviewed_utc")) <= start, "structural qualification postdates capture")
    read_structural_artifact(qualification.get("collector_source"), evidence_root, cache)
    for field in ("coverage_plan", "correspondence_rules"):
        descriptor = qualification.get(field)
        require(isinstance(descriptor, dict) and descriptor.get("sha256") == policy[field + "_sha256"],
                f"structural {field} differs from frozen policy")
        read_structural_artifact(descriptor, evidence_root, cache)
    require(all(qualification.get(key) is True for key in
                ("method_qualified", "coverage_qualified", "correspondence_qualified", "interference_qualified")),
            "structural method/coverage/correspondence/interference not qualified")
    pinned_support = qualification.get("support_sha256s")
    require(isinstance(pinned_support, list) and pinned_support
            and all(hash_string(value) for value in pinned_support)
            and set(pinned_support) == {item["sha256"] for item in support}
            and set(pinned_support).issubset(hashes), "structural qualification support mismatch")
    return {key: counters[key] for key in STRUCTURAL_UNITS}


def inspect_structural(schedule, actual, valid_timing, records, evidence_root):
    """Join independent diagnostics by scheduled identity, never by list position."""
    expected = {job["attempt_id"]: job for job in schedule["jobs"] if job["case"]["kind"] == "small-hdd-read"}
    selected, embedded, issues, counts, evidence, cache = {}, set(), [], {}, [], {}
    acceptance_overlays = {job["overlay_id"] for job in schedule["jobs"]}
    acceptance_ids = {job["attempt_id"] for job in schedule["jobs"]}
    for row in records or []:
        require(isinstance(row, dict) and row.get("timing_attempt_id") in expected,
                "unscheduled structural companion")
        attempt = row["timing_attempt_id"]
        require(attempt not in selected, "duplicate structural companion; no favorable replacements")
        selected[attempt] = row
    for attempt in expected:
        if attempt in valid_timing and "structural_evidence" in actual.get(attempt, {}):
            require(attempt not in selected, "ambiguous same-run and companion structural evidence")
            selected[attempt] = actual[attempt]["structural_evidence"]
            embedded.add(attempt)
    windows = []
    for attempt, timing in actual.items():
        if timing.get("machine_id") != schedule["machine_id"]:
            continue
        try:
            start, end = utc(timing.get("started_utc")), utc(timing.get("finished_utc"))
            if end > start:
                windows.append((start, end, attempt))
        except (ValueError, TypeError):
            continue  # The normal timing validator already records invalid timestamps.
    windows.sort()
    prefix_ends = []
    for _, end, _ in windows:
        prefix_ends.append(max(end, prefix_ends[-1]) if prefix_ends else end)
    overlaps, timing_issues, contaminated, attempts = {}, [], set(), []
    diagnostic_windows = []
    for attempt, row in selected.items():
        if not isinstance(row, dict):
            continue
        attempts.append({key: row[key] for key in
                         ("timing_attempt_id", "capture_run_id", "capture_mode", "started_utc", "finished_utc",
                          "status", "error") if key in row})
        if attempt in embedded or row.get("machine_id") != schedule["machine_id"]:
            continue
        try:
            start, end = utc(row.get("started_utc")), utc(row.get("finished_utc"))
            if end <= start:
                continue
            diagnostic_windows.append((start, end, attempt))
            index = bisect.bisect_right(prefix_ends, start)
            while index < len(windows) and windows[index][0] < end:
                if windows[index][1] > start:
                    timing_id = windows[index][2]
                    overlaps.setdefault(attempt, []).append(timing_id)
                    contaminated.add(timing_id)
                    timing_issues.append(f"{timing_id}: overlapping diagnostic {row.get('capture_run_id')} "
                                         "invalidates untraced timing")
                index += 1
        except (ValueError, TypeError):
            continue
    # Recorded occupancy matters even when a capture's counters/outcome cannot qualify.
    # The furthest prior end detects every overlapping member without filtering status.
    diagnostic_windows.sort()
    diagnostic_overlaps = set()
    furthest_end, furthest_attempt = None, None
    for start, end, attempt in diagnostic_windows:
        if furthest_end is not None and start < furthest_end:
            diagnostic_overlaps.update((attempt, furthest_attempt))
        if furthest_end is None or end > furthest_end:
            furthest_end, furthest_attempt = end, attempt
    run_ids, overlays = set(), set()
    previous_end = None
    for attempt, job in expected.items():
        row = selected.get(attempt)
        if row is None:
            issues.append(f"{attempt}: missing qualified structural evidence")
            continue
        try:
            require(attempt not in overlaps and attempt not in diagnostic_overlaps
                    and not (attempt in embedded and attempt in contaminated),
                    "structural capture overlapped diagnostic/acceptance execution on this host")
            observed = validate_structural_row(schedule, job, row, actual.get(attempt), evidence_root, cache,
                                               attempt in embedded, acceptance_overlays, acceptance_ids)
            require(row["capture_run_id"] not in run_ids, "structural capture_run_id reused")
            require(row["overlay_id"] not in overlays, "structural overlay reused")
            if attempt not in embedded:
                start, end = utc(row["started_utc"]), utc(row["finished_utc"])
                require(previous_end is None or start >= previous_end, "diagnostic captures overlapped or ignored order")
                previous_end = end
            run_ids.add(row["capture_run_id"])
            overlays.add(row["overlay_id"])
            counts[attempt] = observed
            evidence.append({"timing_attempt_id": attempt, "capture_run_id": row["capture_run_id"],
                             "capture_mode": row["capture_mode"], "counters": observed,
                             "capture_manifest_sha256": digest(row["capture_manifest"]),
                             "raw_artifacts": row["raw_artifacts"], "qualification": row["qualification"]})
        except (ValueError, KeyError, TypeError, OSError) as error:
            issues.append(f"{attempt}: {error}")
    return counts, issues, evidence, timing_issues, contaminated, attempts


def verdict_for(verdicts):
    return ("REGRESSION" if "REGRESSION" in verdicts else
            "INCONCLUSIVE" if "INCONCLUSIVE" in verdicts else "PASS")


def compare(calibration, schedule, records, results_sha256, *, structural_records=None,
            structural_results_sha256=None, evidence_root=None):
    validate_calibration(calibration)
    require(schedule.get("phase") == "AB" and schedule.get("calibration_sha256") == calibration["sha256"],
            "A/B schedule must bind frozen calibration")
    require(schedule["spec"] == calibration["spec"] and schedule["pairs"] == calibration["confirmatory_pairs"],
            "A/B rules/count changed after calibration")
    require(utc(schedule["created_utc"]) >= utc(calibration["created_utc"]), "A/B precedes frozen calibration")
    require(hash_string(results_sha256), "pin raw candidate results hash")
    run_metrics, issues, failures, actual = inspect_records(schedule, records, evidence_root=evidence_root)
    separated = "structural_policy" in schedule["spec"]
    separated_durability = "durability_policy" in schedule["spec"]
    if structural_records is not None:
        require(separated and isinstance(structural_records, list) and hash_string(structural_results_sha256),
                "structural companions require predeclared policy and pinned raw JSONL")
    else:
        require(structural_results_sha256 is None, "structural hash supplied without records")
    timing_failures = list(failures)
    structural_counts, structural_issues, structural_evidence = ({}, [], [])
    structural_attempts = []
    if separated:
        (structural_counts, structural_issues, structural_evidence, contamination_issues,
         contaminated, structural_attempts) = inspect_structural(schedule, actual, run_metrics,
                                                                structural_records, evidence_root)
        issues.extend(contamination_issues)
        for attempt in contaminated:
            run_metrics.pop(attempt, None)
    timing_issues = list(issues)
    ratios = pair_metrics(schedule, run_metrics)
    cases, timing_decisions, structural_decisions, structural_failures = [], [], [], []
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
        prefixes = tuple(job["attempt_id"] + ":" for job in jobs)
        timing_case_failures = [value for value in timing_failures if value.startswith(prefixes)]
        timing_case_issues = [value for value in timing_issues if value.startswith(prefixes)]
        timing_verdict = verdict_for(verdicts + (["REGRESSION"] if timing_case_failures else [])
                                    + (["INCONCLUSIVE"] if timing_case_issues else []))
        timing_decisions.append(timing_verdict)
        structural_verdict = "NOT_REQUIRED"
        if case["kind"] == "small-hdd-read":
            paired, increased = {}, []
            for job in jobs:
                if separated and job["attempt_id"] in structural_counts:
                    paired.setdefault(job["pair_index"], {})[job["arm"]] = structural_counts[job["attempt_id"]]
                elif not separated and job["attempt_id"] in run_metrics:
                    paired.setdefault(job["pair_index"], {})[job["arm"]] = actual[job["attempt_id"]]["counters"]
            for pair, arms in paired.items():
                if set(arms) == {"A", "B"}:
                    for counter in STRUCTURAL_UNITS:
                        if arms["B"][counter] > arms["A"][counter]:
                            increased.append(f"{case['id']}/pair-{pair}: increased {counter}")
                            verdicts.append("REGRESSION")
            failures.extend(increased)
            structural_failures.extend(increased)
            if separated or separated_durability:
                complete_pairs = sum(set(arms) == {"A", "B"} for arms in paired.values())
                structural_verdict = verdict_for((["REGRESSION"] if increased else [])
                                                + (["INCONCLUSIVE"] if complete_pairs != schedule["pairs"] else []))
                structural_decisions.append(structural_verdict)
                verdicts.append(structural_verdict)
        case_failures = [failure for failure in failures
                         if failure.startswith(prefixes) or failure.startswith(case["id"] + "/pair-")]
        case_issues = [issue for issue in issues if issue.startswith(prefixes)]
        if separated:
            case_issues += [issue for issue in structural_issues if issue.startswith(prefixes)]
        if case_failures:
            verdicts.append("REGRESSION")
        if case_issues:
            verdicts.append("INCONCLUSIVE")
        case_verdict = verdict_for(verdicts)
        cases.append({"case_id": case["id"], "cache_policy": case["cache_policy"],
                      "verdict": case_verdict, "metrics": metrics, "failures": case_failures, "issues": case_issues})
        durability_verdict = "INCONCLUSIVE" if separated_durability and case["kind"] == "write-flush" else "NOT_REQUIRED"
        if durability_verdict == "INCONCLUSIVE":
            verdicts.append(durability_verdict)
        if separated or separated_durability:
            cases[-1].update(timing_verdict=timing_verdict, structural_verdict=structural_verdict)
            cases[-1]["durability_verdict"] = durability_verdict
            cases[-1]["verdict"] = verdict_for(verdicts)
    issues.extend(structural_issues)
    verdicts = [case["verdict"] for case in cases]
    verdict = "REGRESSION" if failures or "REGRESSION" in verdicts else "INCONCLUSIVE" if issues or "INCONCLUSIVE" in verdicts else "PASS"
    report = {"schema_version": 1, "verdict": verdict, "machine_id": schedule["machine_id"],
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
    if separated:
        report.update(timing_verdict=verdict_for(timing_decisions),
                      structural_verdict=verdict_for(structural_decisions),
                      structural_policy_sha256=digest(schedule["spec"]["structural_policy"]),
                      structural_results_sha256=structural_results_sha256,
                      structural_issues=structural_issues, structural_failures=structural_failures,
                      structural_evidence=structural_evidence, structural_attempts=structural_attempts)
    if separated_durability:
        report.update(timing_verdict=verdict_for(timing_decisions), durability_verdict="INCONCLUSIVE",
                      structural_verdict=verdict_for(structural_decisions),
                      durability_policy_sha256=digest(schedule["spec"]["durability_policy"]),
                      durability_issues=[f"{case['id']}: qualified physical cache-sync/persistence evidence unavailable"
                                         for case in schedule["spec"]["cases"] if case["kind"] == "write-flush"],
                      durability_attempts=[{key: row[key] for key in ("attempt_id", "case_id", "status", "error",
                                               "flush_api_calls_completed", "reopen_readback_verified",
                                               "flushes_completed", "durability_verified", "api_timing_provenance")
                                            if key in row}
                                           for job in schedule["jobs"] if job["case"]["kind"] == "write-flush"
                                           for row in [actual.get(job["attempt_id"], {})]])
    return report


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
                             "workload_seed": spec["seeds"]["workload"] + (0 if "workload_policy" in spec else pair),
                             "overlay_id": f"{phase}-{ordinal:06d}",
                             "fresh_process_required": True})
                if "workload_policy" in spec:
                    jobs[-1].update(fixed_workload_fields(spec, case))
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
    freeze.add_argument("--evidence-dir", help="directory containing frozen public fixture/operation evidence")
    confirm = commands.add_parser("confirmatory", help="bind candidate identity after calibration")
    confirm.add_argument("--calibration", required=True)
    confirm.add_argument("--candidate", required=True)
    confirm.add_argument("--output", required=True)
    analyze = commands.add_parser("compare", help="decide every case from the frozen paired A/B")
    analyze.add_argument("--calibration", required=True)
    analyze.add_argument("--schedule", required=True)
    analyze.add_argument("--results", required=True)
    analyze.add_argument("--structural-results", help="separate diagnostic companion JSONL; requires frozen policy")
    analyze.add_argument("--structural-evidence-dir", "--evidence-dir", dest="evidence_dir",
                         help="directory containing hashed public/companion evidence files")
    analyze.add_argument("--output", help="exclusive output file; default stdout")
    args = parser.parse_args(argv)
    try:
        if args.command == "pilot":
            write_json(args.output, make_schedule(read_json(args.spec)))
        elif args.command == "calibrate":
            records, raw_hash = read_results(args.results)
            write_json(args.output, calibrate(read_json(args.schedule), records, raw_hash, evidence_root=args.evidence_dir))
        elif args.command == "confirmatory":
            write_json(args.output, make_confirmatory(read_json(args.calibration), read_json(args.candidate)))
        else:
            records, raw_hash = read_results(args.results)
            structural, structural_hash = (read_results(args.structural_results)
                                           if args.structural_results else (None, None))
            report = compare(read_json(args.calibration), read_json(args.schedule), records, raw_hash,
                             structural_records=structural, structural_results_sha256=structural_hash,
                             evidence_root=args.evidence_dir)
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
