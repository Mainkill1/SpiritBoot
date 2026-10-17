"""Synthetic companion evidence tests; no native counters or firmware qualification."""
import copy
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import test_storage_perf_compare as fixtures


COUNTERS = {
    "upper_worker_hops": 0, "allocations": 0, "bounce_copies": 0,
    "lower_commands": 1024, "interrupts": 1024,
}
UNITS = {
    "upper_worker_hops": "upper-request-worker-executions",
    "allocations": "successful-new-storage-pool-allocations",
    "bounce_copies": "bounce-copy-operations",
    "lower_commands": "physical-command-issue-attempts",
    "interrupts": "storage-isr-entries",
}
COVERAGE_PLAN = b"Synthetic full boundary coverage plan; no native qualification.\n"
CORRESPONDENCE_RULES = b"Synthetic diagnostic-to-untraced correspondence rules; no native qualification.\n"


def canonical(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     allow_nan=False).encode()).hexdigest()


def companion_spec():
    value = fixtures.specification()
    value["structural_policy"] = {
        "schema_version": 1, "mode": "diagnostic-companion",
        "method": "synthetic-owned-boundary-observer",
        "coverage_plan_sha256": hashlib.sha256(COVERAGE_PLAN).hexdigest(),
        "correspondence_rules_sha256": hashlib.sha256(CORRESPONDENCE_RULES).hexdigest(),
        "route_id": "primary-hdd",
        "counter_units": dict(UNITS),
    }
    return value


def pilot(tool):
    value = tool.make_schedule(companion_spec())
    value["created_utc"] = "2026-01-01T00:00:00+00:00"
    return fixtures.reseal_fixture(value)


def timing_records(schedule):
    records = fixtures.records_for(schedule)
    for row in records:
        row.pop("counters")
    return records


def write_artifact(folder, name, value):
    data = json.dumps(value, sort_keys=True, allow_nan=False).encode()
    (folder / name).write_bytes(data)
    return {"path": name, "sha256": hashlib.sha256(data).hexdigest()}


def companions(schedule, folder, capture_mode="diagnostic-companion"):
    """Invented files exercise the validator; reviewed=true is not a real review."""
    policy = schedule["spec"]["structural_policy"]
    rows = []
    proof = write_artifact(folder, "synthetic-proof.json", {"note": "invented coverage proof"})
    collector = write_artifact(folder, "synthetic-collector.json", {"note": "invented collector implementation"})
    source = write_artifact(folder, "synthetic-collector-source.json", {"note": "invented collector source inventory"})
    (folder / "coverage-plan.txt").write_bytes(COVERAGE_PLAN)
    (folder / "correspondence-rules.txt").write_bytes(CORRESPONDENCE_RULES)
    for job in schedule["jobs"]:
        if job["case"]["kind"] != "small-hdd-read":
            continue
        acceptance = job["manifest"]
        capture = dict(acceptance)
        if capture_mode == "diagnostic-companion":
            capture.update(pe_sha256="b" * 64, flash_sha256="c" * 64,
                           source_tree="b" * 40, patch_sha256s=["a" * 64])
        run_id = ("diagnostic-" + job["attempt_id"] if capture_mode == "diagnostic-companion"
                  else job["attempt_id"])
        coverage = {"complete": True, "lost_events": 0, "overflows": 0,
                    "ambiguous_events": 0, "operations_observed": 1024,
                    "counter_keys": list(COUNTERS)}
        route = write_artifact(folder, "route-" + run_id + ".json", {
            "schema_version": 1, "capture_run_id": run_id,
            "capture_manifest_sha256": canonical(capture),
            "route_id": "primary-hdd", "route_verified": True,
        })
        route["role"] = "route-proof"
        ledger = {"schema_version": 1, "capture_run_id": run_id,
                  "timing_attempt_id": job["attempt_id"],
                  "schedule_sha256": schedule["sha256"],
                  "counter_scope": "caller-issue-to-consumer-ready",
                  "policy_sha256": canonical(policy), "counters": dict(COUNTERS),
                  "route_sha256": route["sha256"],
                  "status": "ok", "error": None,
                  "coverage": copy.deepcopy(coverage)}
        raw = write_artifact(folder, run_id + ".json", ledger)
        raw["role"] = "counter-ledger"
        support = dict(proof, role="qualification-support")
        qualification = {
            "schema_version": 1, "policy_sha256": canonical(policy),
            "capture_manifest_sha256": canonical(capture),
            "acceptance_manifest_sha256": job["manifest_sha256"],
            "case_sha256": canonical(job["case"]),
            "environment_sha256": canonical(schedule["spec"]["environment"]),
            "capture_mode": capture_mode, "reviewed_utc": "2026-01-02T00:00:00+00:00",
            "route_id": "primary-hdd",
            "method": policy["method"], "collector_sha256": collector["sha256"],
            "collector_source": source,
            "coverage_plan": {"path": "coverage-plan.txt", "sha256": policy["coverage_plan_sha256"]},
            "correspondence_rules": {"path": "correspondence-rules.txt", "sha256": policy["correspondence_rules_sha256"]},
            "method_qualified": True, "coverage_qualified": True,
            "correspondence_qualified": True, "interference_qualified": True,
            "support_sha256s": [proof["sha256"]],
        }
        qualified = write_artifact(folder, f"qualified-{job['case_id']}-{job['arm']}.json", qualification)
        begun = datetime.datetime(2026, 1, 4, tzinfo=datetime.timezone.utc)
        begun += datetime.timedelta(seconds=2 * job["ordinal"])
        rows.append({
            "schema_version": 1, "capture_mode": capture_mode,
            "diagnostic": capture_mode == "diagnostic-companion",
            "capture_run_id": run_id, "timing_attempt_id": job["attempt_id"],
            "schedule_sha256": schedule["sha256"],
            "calibration_sha256": schedule["calibration_sha256"],
            "policy_sha256": canonical(policy), "method": policy["method"],
            "collector_sha256": collector["sha256"], "collector_implementation": collector,
            "machine_id": schedule["machine_id"],
            "environment_sha256": canonical(schedule["spec"]["environment"]),
            "memory_profile": schedule["spec"]["environment"]["memory_profile"],
            "acceptance_manifest_sha256": job["manifest_sha256"],
            "capture_manifest": capture,
            "case_sha256": canonical(job["case"]), "case_id": job["case_id"],
            "pair_index": job["pair_index"], "arm": job["arm"],
            "workload_seed": job["workload_seed"],
            "overlay_id": "diagnostic-" + job["overlay_id"],
            "fresh_process": True, "fresh_overlay": True,
            "status": "ok", "error": None,
            "started_utc": begun.isoformat(),
            "finished_utc": (begun + datetime.timedelta(seconds=1)).isoformat(),
            "cache_preparation": {"success": True, "details": "synthetic independent preparation",
                                  "policy_sha256": canonical(schedule["spec"]["cache_policies"][job["cache_policy"]])},
            "counter_scope": "caller-issue-to-consumer-ready",
            "coverage": coverage, "counters": dict(COUNTERS),
            "route_id": "primary-hdd", "route_sha256": route["sha256"],
            "raw_artifacts": [raw, support, route], "qualification": qualified,
            # These diagnostic times must never replace the 256ms acceptance data.
            "elapsed_ms": 1, "latencies_ms": [0.0001] * 1024,
        })
    return rows


def rewrite_context(row, folder, label):
    """Keep invented raw identities/outcomes coherent when exercising a validation gate."""
    route = json.loads((folder / row["raw_artifacts"][2]["path"]).read_text())
    route["capture_run_id"] = row["capture_run_id"]
    raw_route = write_artifact(folder, label + "-route.json", route)
    row["raw_artifacts"][2] = dict(raw_route, role="route-proof")
    row["route_sha256"] = raw_route["sha256"]
    ledger = json.loads((folder / row["raw_artifacts"][0]["path"]).read_text())
    for key in ("capture_run_id", "route_sha256", "status", "error"):
        if key in row:
            ledger[key] = row[key]
        else:
            ledger.pop(key, None)
    row["raw_artifacts"][0] = dict(write_artifact(folder, label + "-ledger.json", ledger), role="counter-ledger")


class StoragePerformanceCompanions(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = fixtures.load_tool()

    def experiment(self):
        try:
            aa = pilot(self.tool)
            frozen = self.tool.calibrate(aa, timing_records(aa), "a" * 64)
        except ValueError as error:
            self.fail(f"qualified timing A/A cannot be calibrated without private counts: {error}")
        frozen["created_utc"] = "2026-01-02T00:00:00+00:00"
        fixtures.reseal_fixture(frozen)
        return frozen, fixtures.confirmatory_fixture(self.tool, frozen, fixtures.candidate_manifest())

    def analyze(self, frozen, schedule, records, structural=None, folder=None):
        try:
            return self.tool.compare(frozen, schedule, records, "b" * 64,
                                     structural_records=structural,
                                     structural_results_sha256="d" * 64 if structural is not None else None,
                                     evidence_root=folder)
        except TypeError as error:
            self.fail(f"separate structural companions are unsupported: {error}")

    def test_missing_private_counts_preserves_all_valid_timing_rows(self):
        # Catch discarding otherwise valid acceptance data or inserting invented zeros.
        aa = pilot(self.tool)
        rows = timing_records(aa)
        metrics, issues, failures, actual = self.tool.inspect_records(aa, rows)
        self.assertEqual(len(metrics), 360)
        self.assertEqual(issues, [])
        self.assertEqual(failures, [])
        self.assertTrue(all("counters" not in row for row in actual.values()))

    def test_timing_calibration_freezes_rules_and_count_before_collector_exists(self):
        # Catch making timing A/A wait for a diagnostic implementation or changing its derived count.
        frozen, _ = self.experiment()
        self.assertNotIn("collector_sha256", frozen["spec"]["structural_policy"])
        self.assertEqual(frozen["confirmatory_pairs"], 197)
        self.assertEqual(frozen["spec"]["structural_policy"]["coverage_plan_sha256"],
                         hashlib.sha256(COVERAGE_PLAN).hexdigest())

    def test_companion_needs_actual_collector_hash_and_available_source_artifact(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            descriptor = evidence[0]["qualification"]
            qualification = json.loads((folder / descriptor["path"]).read_text())
            del qualification["collector_source"]
            evidence[0]["qualification"] = write_artifact(folder, "missing-source.json", qualification)
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
            self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
            evidence = companions(schedule, folder)
            del evidence[0]["collector_sha256"]
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
            self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_missing_companions_keeps_combined_inconclusive_with_timing_pass(self):
        frozen, schedule = self.experiment()
        report = self.analyze(frozen, schedule, timing_records(schedule))
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["timing_verdict"], "PASS")
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["valid_runs"], len(schedule["jobs"]))

    def test_joined_actual_companions_pass_without_using_diagnostic_latencies(self):
        # Catch joining by position, taking diagnostic latency or changing the denominator ROM.
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            evidence.reverse()
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(report["structural_verdict"], "PASS")
        self.assertEqual(report["cases"][0]["metrics"]["latency"]["baseline_median"], 256)
        self.assertEqual(report["cases"][0]["metrics"]["latency"]["candidate_median"], 256)
        self.assertEqual(report["structural_results_sha256"], "d" * 64)
        self.assertEqual(frozen["spec"]["baseline"]["flash_sha256"], "6" * 64)

    def test_mismatched_companion_bindings_do_not_discard_valid_timings(self):
        frozen, schedule = self.experiment()
        changes = {
            "machine_id": "another-host", "memory_profile": "128MiB",
            "schedule_sha256": "0" * 64, "calibration_sha256": "1" * 64,
            "acceptance_manifest_sha256": "2" * 64, "case_sha256": "3" * 64,
            "workload_seed": -1, "arm": "wrong", "pair_index": -1,
            "environment_sha256": "4" * 64, "policy_sha256": "5" * 64,
            "collector_sha256": "6" * 64,
        }
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            for key, value in changes.items():
                with self.subTest(key=key):
                    damaged = copy.deepcopy(evidence)
                    damaged[0][key] = value
                    report = self.analyze(frozen, schedule, timing_records(schedule), damaged, folder)
                    self.assertEqual(report["verdict"], "INCONCLUSIVE")
                    self.assertEqual(report["timing_verdict"], "PASS")
                    self.assertTrue(report["structural_issues"])

    def test_incomplete_lost_overflowed_or_ambiguous_coverage_is_unknown(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            for key, value in (("complete", False), ("lost_events", 1), ("overflows", 1),
                               ("ambiguous_events", 1), ("operations_observed", 1023)):
                with self.subTest(key=key):
                    damaged = copy.deepcopy(evidence)
                    damaged[0]["coverage"][key] = value
                    raw = damaged[0]["raw_artifacts"][0]
                    ledger = json.loads((folder / raw["path"]).read_text())
                    ledger["coverage"] = copy.deepcopy(damaged[0]["coverage"])
                    damaged[0]["raw_artifacts"][0] = dict(
                        write_artifact(folder, "coverage-" + key + ".json", ledger), role="counter-ledger")
                    report = self.analyze(frozen, schedule, timing_records(schedule), damaged, folder)
                    self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
                    self.assertEqual(report["timing_verdict"], "PASS")

    def test_missing_counter_is_unknown_not_zero_even_when_other_counts_are_zero(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            del evidence[0]["counters"]["allocations"]
            raw = evidence[0]["raw_artifacts"][0]
            ledger = json.loads((folder / raw["path"]).read_text())
            del ledger["counters"]["allocations"]
            evidence[0]["raw_artifacts"][0] = dict(write_artifact(folder, "missing-count.json", ledger),
                                                       role="counter-ledger")
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_each_observed_healthy_cost_increase_is_regression(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            index = next(i for i, row in enumerate(evidence) if row["arm"] == "B")
            original = json.loads((folder / evidence[index]["raw_artifacts"][0]["path"]).read_text())
            for name, value in COUNTERS.items():
                with self.subTest(counter=name):
                    damaged = copy.deepcopy(evidence)
                    damaged[index]["counters"][name] = value + 1
                    ledger = copy.deepcopy(original)
                    ledger["counters"][name] = value + 1
                    raw = write_artifact(folder, "increased.json", ledger)
                    damaged[index]["raw_artifacts"][0] = dict(raw, role="counter-ledger")
                    report = self.analyze(frozen, schedule, timing_records(schedule), damaged, folder)
                    self.assertEqual(report["verdict"], "REGRESSION")
                    self.assertEqual(report["structural_verdict"], "REGRESSION")
                    self.assertEqual(report["timing_verdict"], "PASS")

    def test_unqualified_same_run_integers_do_not_bypass_companion_gate(self):
        frozen, schedule = self.experiment()
        report = self.analyze(frozen, schedule, fixtures.records_for(schedule))
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_unreviewed_or_tampered_raw_evidence_remains_unknown(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            (folder / evidence[0]["raw_artifacts"][0]["path"]).write_text("tampered")
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
            self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_wrong_route_is_unknown_even_with_matching_host_and_rom(self):
        # Catch attributing another channel/device's valid counts to the required HDD path.
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            evidence[0]["route_id"] = "secondary-dvd"
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["timing_verdict"], "PASS")

    def test_unverified_runtime_route_is_unknown_despite_reviewed_static_method(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            descriptor = evidence[0]["raw_artifacts"][2]
            route = json.loads((folder / descriptor["path"]).read_text())
            route["route_verified"] = False
            new = write_artifact(folder, "unverified-route.json", route)
            evidence[0]["raw_artifacts"][2] = dict(new, role="route-proof")
            evidence[0]["route_sha256"] = new["sha256"]
            raw = evidence[0]["raw_artifacts"][0]
            ledger = json.loads((folder / raw["path"]).read_text())
            ledger["route_sha256"] = new["sha256"]
            evidence[0]["raw_artifacts"][0] = dict(write_artifact(folder, "unverified-ledger.json", ledger),
                                                       role="counter-ledger")
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_valid_same_run_actual_counts_need_the_full_qualified_metadata(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            records = fixtures.records_for(schedule)
            by_attempt = {row["attempt_id"]: row for row in records}
            for row in companions(schedule, folder, "same-run"):
                timing = by_attempt[row["timing_attempt_id"]]
                row.update(overlay_id=timing["overlay_id"], started_utc=timing["started_utc"],
                           finished_utc=timing["finished_utc"])
                timing["structural_evidence"] = row
            report = self.analyze(frozen, schedule, records, folder=folder)
        self.assertEqual(report["verdict"], "PASS")
        self.assertTrue(all(row["capture_mode"] == "same-run" for row in report["structural_evidence"]))

    def test_unknown_other_evidence_cannot_hide_observed_growth(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            selected = next(row for row in evidence if row["arm"] == "B")
            selected["counters"]["allocations"] = 1
            raw = selected["raw_artifacts"][0]
            ledger = json.loads((folder / raw["path"]).read_text())
            ledger["counters"]["allocations"] = 1
            selected["raw_artifacts"][0] = dict(write_artifact(folder, "growth.json", ledger), role="counter-ledger")
            del evidence[-1]
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["verdict"], "REGRESSION")
        self.assertTrue(report["structural_issues"])

    def test_duplicates_unscheduled_and_ambiguous_same_run_companions_are_rejected(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            for change in ("duplicate", "unscheduled", "embedded"):
                with self.subTest(change=change):
                    rows = copy.deepcopy(evidence)
                    timing = timing_records(schedule)
                    if change == "duplicate":
                        rows.append(copy.deepcopy(rows[0]))
                    elif change == "unscheduled":
                        rows[0]["timing_attempt_id"] = "unplanned-favorable-run"
                    else:
                        selected = next(row for row in timing if row["attempt_id"] == rows[0]["timing_attempt_id"])
                        selected["structural_evidence"] = copy.deepcopy(rows[0])
                    with self.assertRaisesRegex(ValueError, "duplicate|unscheduled|ambiguous"):
                        self.analyze(frozen, schedule, timing, rows, folder)

    def test_good_diagnostic_counts_cannot_hide_acceptance_correctness_failure(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            timing = timing_records(schedule)
            timing[0]["assertions_failed"] = 1
            report = self.analyze(frozen, schedule, timing, evidence, folder)
        self.assertEqual(report["verdict"], "REGRESSION")
        self.assertEqual(report["timing_verdict"], "REGRESSION")
        self.assertEqual(report["structural_verdict"], "PASS")

    def test_cli_pins_separate_raw_jsonl_even_when_structural_capture_is_missing(self):
        # Catch a library-only feature or substituting the acceptance hash for companion bytes.
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            (folder / "calibration.json").write_text(json.dumps(frozen))
            (folder / "schedule.json").write_text(json.dumps(schedule))
            (folder / "timing.jsonl").write_bytes(b"")
            (folder / "structural.jsonl").write_bytes(b"")
            result = subprocess.run([
                sys.executable, str(fixtures.TOOL), "compare",
                "--calibration", str(folder / "calibration.json"),
                "--schedule", str(folder / "schedule.json"),
                "--results", str(folder / "timing.jsonl"),
                "--structural-results", str(folder / "structural.jsonl"),
                "--structural-evidence-dir", str(folder),
            ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["structural_results_sha256"],
                         "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
        self.assertEqual(report["valid_runs"], 0)

    def test_diagnostic_identity_cannot_reuse_another_scheduled_timing_identity(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            evidence[0]["capture_run_id"] = next(job["attempt_id"] for job in schedule["jobs"]
                                                   if job["attempt_id"] != evidence[0]["timing_attempt_id"])
            rewrite_context(evidence[0], folder, "aliased")
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["timing_verdict"], "PASS")

    def test_same_host_diagnostic_overlap_invalidates_affected_timing_and_counts(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            timing = timing_records(schedule)
            evidence = companions(schedule, folder)
            affected = next(row for row in timing if row["attempt_id"] == evidence[0]["timing_attempt_id"])
            evidence[0].update(started_utc=affected["started_utc"], finished_utc=affected["finished_utc"])
            report = self.analyze(frozen, schedule, timing, evidence, folder)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["timing_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["valid_runs"], len(schedule["jobs"]) - 1)
        unaffected = next(case for case in report["cases"] if case["case_id"] != affected["case_id"])
        self.assertEqual(unaffected["timing_verdict"], "PASS")

    def test_overlap_also_disqualifies_same_run_growth_in_a_mixed_capture(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            timing = fixtures.records_for(schedule)
            by_attempt = {row["attempt_id"]: row for row in timing}
            embedded = companions(schedule, folder, "same-run")
            for row in embedded:
                target = by_attempt[row["timing_attempt_id"]]
                row.update(overlay_id=target["overlay_id"], started_utc=target["started_utc"],
                           finished_utc=target["finished_utc"])
                target["structural_evidence"] = row
            self.assertEqual(self.analyze(frozen, schedule, timing, folder=folder)["verdict"], "PASS")
            victim = next(row for row in timing if row["case_id"] == "warm-0" and row["arm"] == "B")
            victim["counters"]["allocations"] = 1
            row = victim["structural_evidence"]
            row["counters"]["allocations"] = 1
            raw = row["raw_artifacts"][0]
            ledger = json.loads((folder / raw["path"]).read_text())
            ledger["counters"]["allocations"] = 1
            row["raw_artifacts"][0] = dict(write_artifact(folder, "same-run-growth.json", ledger),
                                           role="counter-ledger")
            diagnostic_dir = folder / "diagnostic"
            diagnostic_dir.mkdir()
            diagnostic = next(row for row in companions(schedule, diagnostic_dir)
                              if row["case_id"] == "cold-ish-0" and row["arm"] == "A")
            # Different qualification filenames preserve the valid same-run positive control.
            qualified = json.loads((diagnostic_dir / diagnostic["qualification"]["path"]).read_text())
            for key in ("collector_source", "coverage_plan", "correspondence_rules"):
                qualified[key]["path"] = "diagnostic/" + qualified[key]["path"]
            diagnostic["qualification"] = write_artifact(folder, "diagnostic-qualification.json", qualified)
            for descriptor in diagnostic["raw_artifacts"] + [diagnostic["collector_implementation"]]:
                descriptor["path"] = "diagnostic/" + descriptor["path"]
            diagnostic.update(started_utc=victim["started_utc"], finished_utc=victim["finished_utc"])
            del by_attempt[diagnostic["timing_attempt_id"]]["structural_evidence"]
            report = self.analyze(frozen, schedule, timing, [diagnostic], folder)
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["structural_failures"], [])
        self.assertTrue(all(row["timing_attempt_id"] != victim["attempt_id"]
                            for row in report["structural_evidence"]))

    def test_failed_diagnostic_lifetime_disqualifies_other_overlapping_growth(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            original = companions(schedule, folder)
            for status in ("error", "partial"):
                with self.subTest(status=status):
                    evidence = copy.deepcopy(original)
                    failed = evidence[0]
                    failed.update(status=status, error="capture remained active while later diagnostics ran")
                    end = datetime.datetime.fromisoformat(failed["started_utc"]) + datetime.timedelta(seconds=1000)
                    failed["finished_utc"] = end.isoformat()
                    rewrite_context(failed, folder, "occupied-" + status)
                    victim = next(row for row in evidence if row["case_id"] != failed["case_id"]
                                  and row["arm"] == "B"
                                  and datetime.datetime.fromisoformat(row["finished_utc"]) < end)
                    victim["counters"]["allocations"] = 1
                    raw = victim["raw_artifacts"][0]
                    ledger = json.loads((folder / raw["path"]).read_text())
                    ledger["counters"]["allocations"] = 1
                    victim["raw_artifacts"][0] = dict(write_artifact(folder, "occupied-growth-" + status + ".json", ledger),
                                                       role="counter-ledger")
                    report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
                    self.assertEqual(report["timing_verdict"], "PASS")
                    self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
                    self.assertEqual(report["structural_failures"], [])
                    self.assertTrue(all(row["timing_attempt_id"] != victim["timing_attempt_id"]
                                        for row in report["structural_evidence"]))
                    observed = next(row for row in report["structural_attempts"]
                                    if row["timing_attempt_id"] == failed["timing_attempt_id"])
                    self.assertEqual(observed["status"], status)
                    self.assertEqual(observed["error"], failed["error"])

    def test_failed_partial_and_missing_outcomes_are_unknown_and_retained(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            for status, error in (("error", "actual diagnostic failed before consumer readiness"),
                                  ("partial", "observer only captured initial requests"),
                                  ("ok", "contradictory successful outcome"), (None, None)):
                with self.subTest(status=status):
                    damaged = copy.deepcopy(evidence)
                    if status is None:
                        del damaged[0]["error"]
                    else:
                        damaged[0].update(status=status, error=error)
                    rewrite_context(damaged[0], folder, "outcome")
                    report = self.analyze(frozen, schedule, timing_records(schedule), damaged, folder)
                    self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")
                    self.assertEqual(report["timing_verdict"], "PASS")
                    observed = next(row for row in report["structural_attempts"]
                                    if row["timing_attempt_id"] == damaged[0]["timing_attempt_id"])
                    self.assertEqual(observed["status"], damaged[0]["status"])
                    if "error" in damaged[0]:
                        self.assertEqual(observed["error"], error)
                    else:
                        self.assertNotIn("error", observed)

    def test_contradictory_raw_ledger_outcome_cannot_qualify(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            raw = evidence[0]["raw_artifacts"][0]
            ledger = json.loads((folder / raw["path"]).read_text())
            ledger.update(status="error", error="raw collector failed")
            evidence[0]["raw_artifacts"][0] = dict(write_artifact(folder, "failed-ledger.json", ledger),
                                                       role="counter-ledger")
            report = self.analyze(frozen, schedule, timing_records(schedule), evidence, folder)
        self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_qualification_requires_readable_policy_bound_plan_and_rules(self):
        frozen, schedule = self.experiment()
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            evidence = companions(schedule, folder)
            for field in ("coverage_plan", "correspondence_rules"):
                with self.subTest(field=field):
                    damaged = copy.deepcopy(evidence)
                    qualification = json.loads((folder / damaged[0]["qualification"]["path"]).read_text())
                    del qualification[field]
                    damaged[0]["qualification"] = write_artifact(folder, "missing-" + field + ".json", qualification)
                    report = self.analyze(frozen, schedule, timing_records(schedule), damaged, folder)
                    self.assertEqual(report["structural_verdict"], "INCONCLUSIVE")

    def test_policy_cannot_change_after_calibration_or_accept_logical_allocation_units(self):
        frozen, schedule = self.experiment()
        self.assertEqual(frozen["confirmatory_pairs"], 197)
        self.assertEqual(frozen["spec"]["structural_policy"], companion_spec()["structural_policy"])
        changed = copy.deepcopy(schedule)
        changed["spec"]["structural_policy"]["method"] = "post-hoc-cheaper-observer"
        fixtures.reseal_fixture(changed)
        with self.assertRaisesRegex(ValueError, "rules"):
            self.tool.compare(frozen, changed, timing_records(changed), "b" * 64)
        spec = companion_spec()
        spec["structural_policy"]["counter_units"]["allocations"] = "logical-irp-checkouts"
        with self.assertRaisesRegex(ValueError, "structural|counter"):
            self.tool.make_schedule(spec)


if __name__ == "__main__":
    unittest.main()
