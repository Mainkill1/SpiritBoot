"""Independently chosen host fixtures; no measured firmware timings."""
import copy
import datetime
import hashlib
import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/storage_perf_compare.py"


def manifest():
    return {
        "product_commit": "1" * 40,
        "roswell_base": "2" * 40,
        "source_tree": "3" * 40,
        "patch_sha256s": ["4" * 64],
        "toolchain_revision": "independent-test-compiler",
        "pe_sha256": "5" * 64,
        "flash_sha256": "6" * 64,
        "xemu_sha256": "7" * 64,
        "fixture_sha256": "8" * 64,
        "eeprom_sha256": "9" * 64,
        "hdd_seed_sha256": "a" * 64,
        "iso_sha256": "b" * 64,
    }


def specification():
    cases = []
    for cache in ("warm", "cold-ish"):
        definitions = [{"kind": "small-hdd-read", "queue_depth": 1,
                        "request_bytes": 512, "alignment_bytes": 512}]
        for sequence in ("sequence-1", "sequence-2"):
            for depth in (1, 4, 12):
                for pressure in (0, 900):
                    definitions.append({"kind": "fatx-read", "sequence": sequence,
                                        "sequence_sha256": ("c" if sequence == "sequence-1" else "d") * 64,
                                        "queue_depth": depth, "pressure_pages": pressure})
        definitions += [{"kind": "write-flush", "real_flushes": 1},
                        {"kind": "dvd-xiso", "variant": "standard", "iso_sha256": "b" * 64},
                        {"kind": "dvd-xiso", "variant": "alternate", "iso_sha256": "a" * 64},
                        {"kind": "boundary-sg", "variant": "split"},
                        {"kind": "boundary-sg", "variant": "fragmented"}]
        for number, case in enumerate(definitions):
            cases.append(dict(case, id=f"{cache}-{number}", cache_policy=cache,
                              operations=1024, bytes_per_operation=512,
                              expected_sha256="e" * 64, assertions=1))
    return {
        "schema_version": 1, "machine_id": "test-deck", "machine_role": "primary",
        "baseline": manifest(),
        "environment": {"xemu_config": {"renderer": "vulkan"}, "host_ssd": "test-ssd",
                        "cpu_governor": "performance", "power_policy": "fixed-test-watts",
                        "thermal_policy": "fixed-test-temperature", "memory_profile": "64MiB",
                        "cpu_gpu_config": "fixed-test-cpu-gpu"},
        "cache_policies": {"warm": "prime the exact case; fresh independent overlay",
                           "cold-ish": "evict pinned host pages; fresh independent overlay"},
        "seeds": {"workload": 41, "schedule": 19}, "order": "alternate",
        "runner_sha256": "f" * 64,
        "pilot_pairs": 5, "minimum_confirmatory_pairs": 30,
        "maximum_confirmatory_pairs": 2000, "planning_power": 0.8,
        "planning_confidence": 0.8,
        "limits": {"latency": 1.02, "throughput": 0.98, "p95": 1.05, "p99": 1.05},
        "cases": cases,
    }


def candidate_manifest():
    value = manifest()
    value.update(product_commit="0" * 40, source_tree="a" * 40,
                 pe_sha256="0" * 64, flash_sha256="1" * 64,
                 patch_sha256s=["2" * 64])
    return value


def load_tool():
    spec = importlib.util.spec_from_file_location("storage_perf_compare", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records_for(schedule, ratio=1.0):
    """Synthetic 256ms/512KiB batches; never a real baseline observation."""
    start = datetime.datetime.fromisoformat(schedule["created_utc"]) + datetime.timedelta(seconds=1)
    per_arm_samples = {"A": [0.25] * 1024, "B": [0.25 * ratio] * 1024}
    records = []
    for job in schedule["jobs"]:
        factor = ratio if job["arm"] == "B" else 1
        begun = start + datetime.timedelta(seconds=2 * job["ordinal"])
        policy = schedule["spec"]["cache_policies"][job["cache_policy"]]
        canonical = lambda value: hashlib.sha256(json.dumps(value, sort_keys=True,
                                                            separators=(",", ":")).encode()).hexdigest()
        records.append({
            "schema_version": 1, "schedule_sha256": schedule["sha256"],
            "machine_id": schedule["machine_id"], "manifest_sha256": job["manifest_sha256"],
            "environment_sha256": canonical(schedule["spec"]["environment"]),
            "runner_sha256": schedule["spec"]["runner_sha256"],
            "attempt_id": job["attempt_id"], "ordinal": job["ordinal"],
            "pair_index": job["pair_index"], "arm": job["arm"], "case_id": job["case_id"],
            "workload_seed": job["workload_seed"], "overlay_id": job["overlay_id"],
            "fresh_process": True, "fresh_overlay": True, "tracing": False,
            "expensive_guest_clocks": False,
            "started_utc": begun.isoformat(),
            "finished_utc": (begun + datetime.timedelta(seconds=1)).isoformat(),
            "status": "ok", "error": None, "timing_scope": "caller-issue-to-consumer-ready",
            "cache_preparation": {"success": True, "policy_sha256": canonical(policy),
                                  "details": "independent synthetic cache setup"},
            "integrity_sha256": "e" * 64, "operations_completed": 1024,
            "media_sha256": job["case"].get("iso_sha256", schedule["spec"]["baseline"]["hdd_seed_sha256"]),
            "bytes_completed": 524288, "assertions_executed": 1, "assertions_failed": 0,
            "flushes_completed": job["case"].get("real_flushes", 0),
            "durability_verified": True, "elapsed_ms": 256 * factor,
            "latencies_ms": per_arm_samples[job["arm"]],
            "counters": {"upper_worker_hops": 0, "allocations": 0, "bounce_copies": 0,
                         "lower_commands": 1024, "interrupts": 1024},
        })
    return records


def pilot_fixture(tool):
    schedule = tool.make_schedule(specification())
    schedule["created_utc"] = "2026-01-01T00:00:00+00:00"
    del schedule["sha256"]
    schedule["sha256"] = hashlib.sha256(json.dumps(schedule, sort_keys=True,
                                                   separators=(",", ":")).encode()).hexdigest()
    return schedule


def reseal_fixture(value):
    del value["sha256"]
    value["sha256"] = hashlib.sha256(json.dumps(value, sort_keys=True,
                                               separators=(",", ":")).encode()).hexdigest()
    return value


def calibration_fixture(tool, pilot):
    frozen = tool.calibrate(pilot, records_for(pilot), "a" * 64)
    frozen["created_utc"] = "2026-01-02T00:00:00+00:00"
    return reseal_fixture(frozen)


def confirmatory_fixture(tool, frozen, candidate):
    schedule = tool.make_confirmatory(frozen, candidate)
    schedule["created_utc"] = "2026-01-03T00:00:00+00:00"
    return reseal_fixture(schedule)


class StoragePerformanceDecoding(unittest.TestCase):
    def test_results_reject_duplicate_keys_before_failure_can_be_overwritten(self):
        # Catch last-key-wins decoding that erases error or nested evidence.
        samples = (
            '{"status":"error","error":"retained failure","status":"ok","error":null}',
            '{"status":"error","\\u0073tatus":"ok"}',
            '{"checksums":{"verified":false,"verified":true}}',
        )
        for raw in samples:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                path = pathlib.Path(directory) / "results.jsonl"
                path.write_text('{}\n' + raw + '\n')
                with self.assertRaisesRegex(ValueError, r"JSONL line 2: .*duplicate JSON key"):
                    load_tool().read_results(path)

    def test_json_inputs_reject_duplicate_nested_identity_fields(self):
        # Catch a conflicting source/media pin being silently discarded.
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "spec.json"
            path.write_text('{"baseline":{"flash_sha256":"old","flash_sha256":"new"}}')
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                load_tool().read_json(path)

    def test_distinct_objects_can_repeat_field_names_and_preserve_raw_hash(self):
        # Duplicate rejection must be local to each object, including JSONL rows.
        raw = b'{"A":{"status":"ok"},"B":{"status":"error"}}\n{"status":"ok"}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "results.jsonl"
            path.write_bytes(raw)
            records, digest = load_tool().read_results(path)
        self.assertEqual(records, [{"A":{"status":"ok"},"B":{"status":"error"}}, {"status":"ok"}])
        self.assertEqual(digest, hashlib.sha256(raw).hexdigest())


class StoragePerformanceCLI(unittest.TestCase):
    def test_pilot_cli_produces_all_paired_jobs_without_candidate_measurements(self):
        # Catch silently omitting a workload/arm from the executable schedule.
        with tempfile.TemporaryDirectory() as directory:
            spec_path = pathlib.Path(directory) / "spec.json"
            output = pathlib.Path(directory) / "pilot.json"
            spec_path.write_text(json.dumps(specification()))
            result = subprocess.run([sys.executable, str(TOOL), "pilot", "--spec", str(spec_path),
                                     "--output", str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            schedule = json.loads(output.read_text())
            self.assertEqual(len(schedule["jobs"]), 360)
            self.assertEqual(schedule["phase"], "AA")
            self.assertEqual([job["arm"] for job in schedule["jobs"][:2]], ["A", "B"])
            self.assertEqual([job["arm"] for job in schedule["jobs"][72:74]], ["B", "A"])
            self.assertEqual(len({job["overlay_id"] for job in schedule["jobs"]}), 360)

    def test_pilot_rejects_unpinned_or_reduced_experiments(self):
        # Catch omission of identity, workload, sample-count, and cache controls.
        broken_specs = []
        missing_hash = specification()
        del missing_hash["baseline"]["pe_sha256"]
        broken_specs.append(missing_hash)
        missing_pressure = specification()
        missing_pressure["cases"] = [case for case in missing_pressure["cases"]
                                     if case.get("pressure_pages") != 900]
        broken_specs.append(missing_pressure)
        skipped_read = specification()
        skipped_read["cases"][1]["operations"] = 1023
        broken_specs.append(skipped_read)
        too_few_runs = specification()
        too_few_runs["minimum_confirmatory_pairs"] = 5
        broken_specs.append(too_few_runs)
        missing_cache = specification()
        del missing_cache["cache_policies"]["cold-ish"]
        broken_specs.append(missing_cache)
        premature_candidate = specification()
        premature_candidate["candidate"] = candidate_manifest()
        broken_specs.append(premature_candidate)
        missing_optical_identity = specification()
        del next(case for case in missing_optical_identity["cases"] if case["kind"] == "dvd-xiso")["iso_sha256"]
        broken_specs.append(missing_optical_identity)
        for index, broken in enumerate(broken_specs):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as directory:
                spec_path = pathlib.Path(directory) / "spec.json"
                output = pathlib.Path(directory) / "pilot.json"
                spec_path.write_text(json.dumps(broken))
                result = subprocess.run([sys.executable, str(TOOL), "pilot", "--spec", str(spec_path),
                                         "--output", str(output)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertFalse(output.exists())

    def test_cli_freezes_pilot_and_reports_missing_confirmatory_attempts(self):
        # Catch unusable calibration CLI or a missing-job PASS, including PS UTF8 BOM.
        tool = load_tool()
        pilot = pilot_fixture(tool)
        with tempfile.TemporaryDirectory() as directory:
            folder = pathlib.Path(directory)
            schedule_path, results_path = folder / "pilot.json", folder / "pilot.jsonl"
            frozen_path, candidate_path = folder / "frozen.json", folder / "candidate.json"
            ab_path, empty_path = folder / "ab.json", folder / "ab.jsonl"
            schedule_path.write_text(json.dumps(pilot), encoding="utf-8-sig")
            results_path.write_text("\n".join(json.dumps(row) for row in records_for(pilot)) + "\n",
                                    encoding="utf-8-sig")
            result = subprocess.run([sys.executable, str(TOOL), "calibrate", "--schedule", str(schedule_path),
                                     "--results", str(results_path), "--output", str(frozen_path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            frozen = json.loads(frozen_path.read_text())
            self.assertEqual(frozen["pilot_results_sha256"], hashlib.sha256(results_path.read_bytes()).hexdigest())
            candidate_path.write_text(json.dumps(candidate_manifest()))
            result = subprocess.run([sys.executable, str(TOOL), "confirmatory", "--calibration", str(frozen_path),
                                     "--candidate", str(candidate_path), "--output", str(ab_path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            empty_path.write_text("")
            result = subprocess.run([sys.executable, str(TOOL), "compare", "--calibration", str(frozen_path),
                                     "--schedule", str(ab_path), "--results", str(empty_path)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            report = json.loads(result.stdout)
            self.assertEqual(report["verdict"], "INCONCLUSIVE")
            self.assertEqual(report["attempts_recorded"], 0)
            self.assertEqual(len(report["issues"]), len(json.loads(ab_path.read_text())["jobs"]))


class StoragePerformanceAnalysis(unittest.TestCase):
    def setUp(self):
        self.tool = load_tool()

    def test_exact_bounds_use_run_count_and_independent_order_statistics(self):
        # Catch operation pseudoreplication and falsely finite bounds from tiny n.
        self.assertTrue(callable(getattr(self.tool, "median_bounds", None)), "median_bounds is missing")
        self.assertEqual(self.tool.median_bounds([1, 2, 3, 4], 0.05), (None, None))
        self.assertEqual(self.tool.median_bounds([1, 2, 3, 4, 5], 0.05), (1, 5))
        self.assertEqual(self.tool.median_bounds(list(range(1, 31)), 0.025), (10, 21))

    def test_calibration_freezes_count_before_candidate_identity_is_bound(self):
        # Catch five-pair confirmation, mutable rules, or mixed emulator/media identity.
        self.assertTrue(callable(getattr(self.tool, "calibrate", None)), "calibrate is missing")
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        self.assertGreaterEqual(frozen["confirmatory_pairs"], 30)
        self.assertNotIn("candidate", frozen)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        self.assertEqual(schedule["pairs"], frozen["confirmatory_pairs"])
        self.assertEqual(schedule["calibration_sha256"], frozen["sha256"])
        broken = copy.deepcopy(frozen)
        broken["spec"]["limits"]["latency"] = 1.5
        with self.assertRaisesRegex(ValueError, "hash"):
            self.tool.make_confirmatory(broken, candidate_manifest())
        candidate = candidate_manifest()
        candidate["xemu_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "xemu"):
            self.tool.make_confirmatory(frozen, candidate)

    def test_complete_frozen_evidence_decides_every_case(self):
        # Catch an averaged-away regression or failure to use confidence limits.
        self.assertTrue(callable(getattr(self.tool, "compare", None)), "compare is missing")
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        report = self.tool.compare(frozen, schedule, records_for(schedule), "b" * 64)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(len(report["cases"]), 36)
        metrics = report["cases"][0]["metrics"]
        self.assertEqual(metrics["latency"]["lower"], 1.0)
        self.assertEqual(metrics["latency"]["upper"], 1.0)
        self.assertEqual(metrics["throughput"]["baseline_median"], 2048.0)
        regressed = records_for(schedule, ratio=1.1)
        # Retain a single failed workload and leave every other workload healthy.
        healthy = records_for(schedule)
        chosen = schedule["spec"]["cases"][0]["id"]
        combined = [bad if bad["case_id"] == chosen else good for bad, good in zip(regressed, healthy)]
        report = self.tool.compare(frozen, schedule, combined, "c" * 64)
        self.assertEqual(report["verdict"], "REGRESSION")
        self.assertEqual(sum(case["verdict"] == "REGRESSION" for case in report["cases"]), 1)

    def test_invalid_and_failed_attempts_are_never_filtered_into_pass(self):
        # Catch dropped failures, shortened work, traced acceptance and mixed hosts.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        baseline_records = records_for(schedule)
        alterations = [({"machine_id": "other-i9"}, "INCONCLUSIVE"),
                       ({"tracing": True}, "INCONCLUSIVE"),
                       ({"expensive_guest_clocks": True}, "INCONCLUSIVE"),
                       ({"status": "timeout", "error": "native job exceeded budget"}, "REGRESSION"),
                       ({"integrity_sha256": "0" * 64}, "REGRESSION"),
                       ({"operations_completed": 1023}, "REGRESSION"),
                       ({"latencies_ms": [0.25] * 20}, "INCONCLUSIVE")]
        for changes, expected in alterations:
            with self.subTest(changes=list(changes)):
                altered = list(baseline_records)
                altered[0] = dict(altered[0], **changes)
                report = self.tool.compare(frozen, schedule, altered, "b" * 64)
                self.assertEqual(report["verdict"], expected)
                self.assertEqual(report["attempts_recorded"], len(schedule["jobs"]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.tool.compare(frozen, schedule, baseline_records + [baseline_records[0]], "b" * 64)
        unexpected = dict(baseline_records[0], attempt_id="unplanned-retry")
        with self.assertRaisesRegex(ValueError, "unscheduled"):
            self.tool.compare(frozen, schedule, baseline_records + [unexpected], "b" * 64)

    def test_uncertainty_crossing_predeclared_limit_is_inconclusive(self):
        # Catch substituting a favorable mean/median for a confidence bound.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        records = records_for(schedule)
        for record in records:
            if record["arm"] == "B":
                ratio = .97 if record["pair_index"] % 2 else 1.03
                record["elapsed_ms"] = 256 * ratio
                record["latencies_ms"] = [0.25 * ratio] * 1024
        report = self.tool.compare(frozen, schedule, records, "b" * 64)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["cases"][0]["metrics"]["latency"]["lower"], .97)
        self.assertEqual(report["cases"][0]["metrics"]["latency"]["upper"], 1.03)

    def test_failed_workload_is_reported_as_regression_in_its_own_case(self):
        # Catch hiding a failed checksum as only a global error or inconclusive case.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        records = records_for(schedule)
        records[0]["integrity_sha256"] = "0" * 64
        report = self.tool.compare(frozen, schedule, records, "b" * 64)
        case = next(case for case in report["cases"] if case["case_id"] == records[0]["case_id"])
        self.assertEqual(case["verdict"], "REGRESSION")
        self.assertEqual(report["attempts"][0]["operations_completed"], 1024)

    def test_sample_planning_refuses_noisy_aa_instead_of_choosing_five_pairs(self):
        # Catch unsupported power planning and accepting noisy A/A as calibrated.
        pilot = pilot_fixture(self.tool)
        with self.assertRaisesRegex(ValueError, "A/A.*planning"):
            self.tool.calibrate(pilot, records_for(pilot, ratio=1.03), "a" * 64)

    def test_real_flush_and_healthy_path_costs_remain_correctness_gates(self):
        # Catch apparent speedup from skipped device flush or an extra allocation.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        for kind in ("write-flush", "small-hdd-read"):
            records = records_for(schedule)
            selected = next(row for row, job in zip(records, schedule["jobs"])
                            if row["arm"] == "B" and job["case"]["kind"] == kind)
            if kind == "write-flush":
                selected["flushes_completed"] = 0
            else:
                selected["counters"] = dict(selected["counters"], allocations=1)
            report = self.tool.compare(frozen, schedule, records, "b" * 64)
            self.assertEqual(report["verdict"], "REGRESSION")

    def test_manually_resealed_schedule_cannot_mix_candidate_builds_or_media(self):
        # Catch a schedule that benchmarks different B binaries across pairs.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        candidate_job = next(job for job in schedule["jobs"] if job["arm"] == "B")
        candidate_job["manifest"] = dict(candidate_job["manifest"], flash_sha256="e" * 64)
        candidate_job["manifest_sha256"] = self.tool.digest(candidate_job["manifest"])
        del schedule["sha256"]
        self.tool.seal(schedule)
        with self.assertRaisesRegex(ValueError, "candidate.*manifest"):
            self.tool.compare(frozen, schedule, records_for(schedule), "b" * 64)

    def test_recorded_batch_duration_cannot_exceed_attempt_wall_time(self):
        # Catch unrelated or shortened timing-region metadata.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        records = records_for(schedule)
        records[0]["elapsed_ms"] = 1001
        report = self.tool.compare(frozen, schedule, records, "b" * 64)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")

    def test_same_seed_repeats_randomized_jobs_and_never_unpairs_arms(self):
        # Catch accidental dependence on ambient RNG or separating pair members.
        spec = specification()
        spec["order"] = "random"
        first, second = self.tool.make_schedule(spec), self.tool.make_schedule(spec)
        self.assertEqual(first["jobs"], second["jobs"])
        for offset in range(0, len(first["jobs"]), 2):
            left, right = first["jobs"][offset:offset + 2]
            self.assertEqual((left["case_id"], left["pair_index"]), (right["case_id"], right["pair_index"]))
            self.assertEqual({left["arm"], right["arm"]}, {"A", "B"})

    def test_malformed_ordinal_keeps_attempt_in_inconclusive_report(self):
        # Catch an invalid record crashing report generation instead of retaining it.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        records = records_for(schedule)
        records[0]["ordinal"] = None
        try:
            report = self.tool.compare(frozen, schedule, records, "b" * 64)
        except TypeError as error:
            self.fail(f"malformed attempt must yield a retained INCONCLUSIVE report: {error}")
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["attempts"][0]["attempt_id"], records[0]["attempt_id"])

    def test_resealed_calibration_cannot_reduce_sample_or_change_confidence_method(self):
        # Catch rehashed manual edits enabling five-pair or relaxed-confidence PASS.
        pilot = pilot_fixture(self.tool)
        original = calibration_fixture(self.tool, pilot)
        for changes in ({"confirmatory_pairs": 5}, {"one_sided_alpha": .05}):
            frozen = dict(original, **changes)
            del frozen["sha256"]
            self.tool.seal(frozen)
            with self.assertRaisesRegex(ValueError, "calibration"):
                confirmatory_fixture(self.tool, frozen, candidate_manifest())

    def test_resealed_calibration_cannot_lower_derived_count_within_allowed_range(self):
        # Catch lowering a legitimately derived 197-pair plan to the allowed floor.
        pilot = pilot_fixture(self.tool)
        original = calibration_fixture(self.tool, pilot)
        self.assertEqual(original["confirmatory_pairs"], 197)
        for remove_planning in (False, True):
            with self.subTest(remove_planning=remove_planning):
                frozen = copy.deepcopy(original)
                frozen["confirmatory_pairs"] = 30
                if remove_planning:
                    del frozen["planning"]
                del frozen["sha256"]
                self.tool.seal(frozen)
                with self.assertRaisesRegex(ValueError, "calibration"):
                    confirmatory_fixture(self.tool, frozen, candidate_manifest())
                # Comparison must reject the same edit even if a caller bypasses scheduling.
                forged_schedule = self.tool.make_schedule(frozen["spec"], "AB", 30,
                                                         candidate_manifest(), frozen["sha256"])
                forged_schedule["created_utc"] = "2026-01-03T00:00:00+00:00"
                reseal_fixture(forged_schedule)
                with self.assertRaisesRegex(ValueError, "calibration"):
                    self.tool.compare(frozen, forged_schedule, records_for(forged_schedule), "b" * 64)

    def test_resealed_calibration_rejects_missing_or_inconsistent_gate_facts(self):
        # Catch omitted gates or a misleading pilot fact/derived probability summary.
        pilot = pilot_fixture(self.tool)
        original = calibration_fixture(self.tool, pilot)
        changes = (
            ("planning", None),
            ("gate_count", None),
            ("pilot_pairs", 4),
            ("ratios", [1.0] * 4),
            ("ratios", [.99, 1.0, 1.0, 1.0, 1.0]),
            ("ratios", [1.0, 1.0, 1.0, 1.0, float("inf")]),
            ("inside_margin", 4),
            ("planning_probability_lower", .9),
            ("recommended_pairs", 30),
        )
        for field, value in changes:
            with self.subTest(field=field, value=value):
                frozen = copy.deepcopy(original)
                if field == "planning":
                    del frozen["planning"]
                elif field == "gate_count":
                    frozen["planning"].pop()
                else:
                    frozen["planning"][0][field] = value
                del frozen["sha256"]
                # An infinity cannot be sealed by the JSON contract; exercise validation directly.
                if field == "ratios" and value[-1] == float("inf"):
                    with self.assertRaises(ValueError):
                        self.tool.seal(frozen)
                    continue
                self.tool.seal(frozen)
                with self.assertRaisesRegex(ValueError, "calibration"):
                    confirmatory_fixture(self.tool, frozen, candidate_manifest())

    def test_ok_status_with_recorded_error_cannot_pass(self):
        # Catch silently ignoring an adapter-reported I/O error under status=ok.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        records = records_for(schedule)
        records[0]["error"] = "owned adapter observed an I/O error"
        report = self.tool.compare(frozen, schedule, records, "b" * 64)
        self.assertEqual(report["verdict"], "REGRESSION")
        self.assertIn("error", " ".join(report["failures"]))

    def test_future_dated_complete_capture_cannot_pass(self):
        # Catch using an entire internally ordered capture that has not finished yet.
        pilot = pilot_fixture(self.tool)
        frozen = calibration_fixture(self.tool, pilot)
        schedule = confirmatory_fixture(self.tool, frozen, candidate_manifest())
        records = records_for(schedule)
        shift = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=365)
                 - datetime.datetime.fromisoformat(records[0]["started_utc"]))
        for record in records:
            for field in ("started_utc", "finished_utc"):
                record[field] = (datetime.datetime.fromisoformat(record[field])
                                 + shift).isoformat()
        report = self.tool.compare(frozen, schedule, records, "b" * 64)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertIn("future", " ".join(report["issues"]))

    def test_original_pilot_ratio_ledger_must_cover_every_case_metric_and_pair(self):
        # Catch rederived planning from truncated, omitted, or nonpositive pilot facts.
        pilot = pilot_fixture(self.tool)
        original = calibration_fixture(self.tool, pilot)
        case_id = "warm-0"
        for change in ("ledger", "case", "metric", "pair", "value"):
            with self.subTest(change=change):
                frozen = copy.deepcopy(original)
                if change == "ledger":
                    del frozen["pilot_ratios"]
                elif change == "case":
                    del frozen["pilot_ratios"][case_id]
                elif change == "metric":
                    del frozen["pilot_ratios"][case_id]["latency"]
                elif change == "pair":
                    frozen["pilot_ratios"][case_id]["latency"].pop()
                else:
                    frozen["pilot_ratios"][case_id]["latency"][0] = 0
                reseal_fixture(frozen)
                with self.assertRaisesRegex(ValueError, "calibration"):
                    confirmatory_fixture(self.tool, frozen, candidate_manifest())


if __name__ == "__main__":
    unittest.main()
