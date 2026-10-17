"""Invented public timing evidence; no native durability or workload qualification."""
import copy
import datetime
import hashlib
import json
import math
import pathlib
import tempfile
import unittest

import test_storage_perf_compare as fixtures
import test_storage_perf_companions as companion_fixtures


def artifact(folder, name, value):
    return companion_fixtures.write_artifact(folder, name, value)


def specification(tool, folder, *, fixed=True):
    spec = fixtures.specification()
    fixture = artifact(folder, "fixture.json", {"synthetic": "not an executed XBE"})
    source = artifact(folder, "source.json", {"synthetic": "not native source qualification"})
    parser = artifact(folder, "parser.json", {"synthetic": "not an actual native parser"})
    spec["baseline"]["fixture_sha256"] = fixture["sha256"]
    for case in spec["cases"]:
        if case["kind"] == "write-flush":
            case.update(api_flush_calls=1024, assertions=11264, bytes_per_operation=4096)
    coverage = artifact(folder, "coverage.json", {"synthetic": "future physical coverage plan"})
    correspondence = artifact(folder, "correspondence.json", {"synthetic": "future correspondence rules"})
    common = {"schema_version": 1, "fixture_sha256": fixture["sha256"],
              "fixture_artifact": fixture, "source_artifacts": [source],
              "reviewed_utc": "2025-12-31T00:00:00+00:00", "method_qualified": True,
              "cases": {case["id"]: tool.digest(case) for case in spec["cases"]}}
    public = dict(common, contract="public-api-flush-reopen", parser_artifact=parser,
                  fixture_generation=2, assertions_per_operation=11,
                  timing_conversion="recorded-rdtsc-frequency",
                  coverage_plan=coverage, correspondence_rules=correspondence)
    spec["durability_policy"] = {
        "schema_version": 1, "mode": "diagnostic-companion",
        "timing_workload": "public-api-flush-reopen", "method": "synthetic-future-physical-method",
        "persistence_scope": "device-cache-sync-and-persistence",
        "coverage_plan_sha256": coverage["sha256"], "correspondence_rules_sha256": correspondence["sha256"],
        "timing_contract": artifact(folder, "public-contract.json", public),
    }
    if fixed:
        fixed_contract = dict(common, contract="fixture-fixed", seed_semantics="METADATA_ONLY")
        spec["workload_policy"] = {
            "schema_version": 1, "mode": "fixture-fixed", "seed_semantics": "METADATA_ONLY",
            "fixture_sha256": fixture["sha256"],
            "fixture_contract": artifact(folder, "fixed-contract.json", fixed_contract),
        }
    return spec


def records(tool, schedule, folder):
    rows = fixtures.records_for(schedule)
    jobs = {job["attempt_id"]: job for job in schedule["jobs"]}
    contract = json.loads((folder / schedule["spec"]["durability_policy"]["timing_contract"]["path"]).read_text())
    for row in rows:
        job = jobs[row["attempt_id"]]
        for field in ("workload_seed_semantics", "workload_policy_sha256", "workload_identity_sha256"):
            if field in job:
                row[field] = job[field]
        if job["case"]["kind"] != "write-flush":
            continue
        case = job["case"]
        lengths = case.get("operation_bytes", [case["bytes_per_operation"]] * case["operations"])
        row.update(bytes_completed=sum(lengths), assertions_executed=case["assertions"],
                   flush_api_calls_completed=case["api_flush_calls"], reopen_readback_verified=True,
                   durability_policy_sha256=tool.digest(schedule["spec"]["durability_policy"]),
                   flushes_completed=None, durability_verified=None)
        ledger = {
            "schema_version": 1,
            **{field: row[field] for field in ("attempt_id", "schedule_sha256", "manifest_sha256",
                                              "environment_sha256", "runner_sha256")},
            "case_sha256": tool.digest(case), "fixture_sha256": job["manifest"]["fixture_sha256"],
            "parser_sha256": contract["parser_artifact"]["sha256"],
            "durability_policy_sha256": row["durability_policy_sha256"],
            "timing_contract_sha256": schedule["spec"]["durability_policy"]["timing_contract"]["sha256"],
            "timing_sha256": tool.digest({key: row[key] for key in ("elapsed_ms", "latencies_ms", "timing_scope")}),
            "meta": {"version": "1", "fixture_generation": "2", "counter": "rdtsc", "frequency": "1000000"},
            "summary": {"id": case["id"], "operations": str(case["operations"]), "bytes": str(sum(lengths)),
                        "assertions": str(case["assertions"]), "failures": "0", "flush_calls": "1024",
                        "persistence": "1", "ticks": "256000", "cache": case["cache_policy"]},
            "end": {"cases": "1", "failures": "0"},
            "operations": [{"id": case["id"], "index": str(i), "ticks": "250", "status": "00000000",
                            "io_status": "00000000", "information": str(length)}
                           for i, length in enumerate(lengths)],
        }
        for field in ("workload_seed_semantics", "workload_policy_sha256", "workload_identity_sha256"):
            if field in row:
                ledger[field] = row[field]
        row["api_timing_provenance"] = artifact(folder, row["attempt_id"] + ".json", ledger)
    return rows


class StoragePerformanceDurability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = fixtures.load_tool()

    def pilot(self, folder, *, fixed=True):
        schedule = self.tool.make_schedule(specification(self.tool, folder, fixed=fixed))
        schedule["created_utc"] = "2026-01-01T00:00:00+00:00"
        return fixtures.reseal_fixture(schedule)

    def experiment(self, folder, *, fixed=True):
        aa = self.pilot(folder, fixed=fixed)
        try:
            frozen = self.tool.calibrate(aa, records(self.tool, aa, folder), "a" * 64, evidence_root=folder)
        except (ValueError, TypeError) as error:
            self.fail(f"complete public full36 timing cannot calibrate without physical telemetry: {error}")
        frozen["created_utc"] = "2026-01-02T00:00:00+00:00"
        fixtures.reseal_fixture(frozen)
        candidate = fixtures.candidate_manifest()
        candidate["fixture_sha256"] = aa["spec"]["baseline"]["fixture_sha256"]
        schedule = fixtures.confirmatory_fixture(self.tool, frozen, candidate)
        return aa, frozen, schedule

    def test_full36_public_aa_freezes_count_and_physical_requirements_without_collector(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa, frozen, _ = self.experiment(folder)
        self.assertEqual(len(aa["spec"]["cases"]), 36)
        self.assertEqual(frozen["spec"], aa["spec"])
        self.assertNotIn("collector_sha256", frozen["spec"]["durability_policy"])
        self.assertTrue(all(case["real_flushes"] > 0 for case in frozen["spec"]["cases"] if case["kind"] == "write-flush"))

    def test_complete_public_timing_never_closes_physical_durability_even_with_bare_true(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder)
            rows = records(self.tool, schedule, folder)
            for row in rows:
                if "api_timing_provenance" in row:
                    row.update(flushes_completed=1, durability_verified=True)
            report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
        self.assertEqual(report["timing_verdict"], "PASS")
        self.assertEqual(report["durability_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["valid_runs"], len(schedule["jobs"]))

    def test_fixed_policy_labels_do_not_claim_consumed_seed_and_legacy_still_varies(self):
        with tempfile.TemporaryDirectory() as temp:
            fixed = self.pilot(pathlib.Path(temp))
        self.assertEqual({job["workload_seed"] for job in fixed["jobs"]}, {41})
        self.assertEqual({job["workload_seed_semantics"] for job in fixed["jobs"]}, {"METADATA_ONLY"})
        for case in fixed["spec"]["cases"]:
            self.assertEqual(len({job["workload_identity_sha256"] for job in fixed["jobs"] if job["case_id"] == case["id"]}), 1)
        legacy = fixtures.pilot_fixture(self.tool)
        self.assertEqual({job["workload_seed"] for job in legacy["jobs"]}, set(range(41, 46)))

    def test_missing_raw_flush_calls_is_unknown_but_observed_zero_is_regression(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder)
            original = records(self.tool, schedule, folder)
            for missing in (True, False):
                with self.subTest(missing=missing):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
                    if missing:
                        del ledger["summary"]["flush_calls"]
                    else:
                        ledger["summary"]["flush_calls"] = "0"
                    row["flush_api_calls_completed"] = 0
                    row["api_timing_provenance"] = artifact(folder, "missing-or-zero.json", ledger)
                    report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
                    self.assertEqual(report["timing_verdict"], "INCONCLUSIVE" if missing else "REGRESSION")

    def test_missing_tampered_or_incomplete_public_proof_never_qualifies(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder)
            original = records(self.tool, schedule, folder)
            for fault in ("missing", "hash", "generation", "operations", "persistence", "cache"):
                with self.subTest(fault=fault):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    descriptor = row["api_timing_provenance"]
                    if fault == "missing":
                        del row["api_timing_provenance"]
                    elif fault == "hash":
                        descriptor["sha256"] = "0" * 64
                    else:
                        ledger = json.loads((folder / descriptor["path"]).read_text())
                        if fault == "generation":
                            ledger["meta"]["fixture_generation"] = "1"
                        elif fault == "operations":
                            ledger["operations"].pop()
                        elif fault == "persistence":
                            del ledger["summary"]["persistence"]
                        else:
                            ledger["summary"]["cache"] = "wrong-cache"
                        row["api_timing_provenance"] = artifact(folder, "proof-" + fault + ".json", ledger)
                    report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
                    self.assertEqual(report["timing_verdict"], "INCONCLUSIVE")

    def test_durability_only_mode_keeps_legacy_healthy_counter_requirement(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder, fixed=False)
            rows = records(self.tool, schedule, folder)
            small = next(job for job in schedule["jobs"] if job["case"]["kind"] == "small-hdd-read")
            next(row for row in rows if row["attempt_id"] == small["attempt_id"]).pop("counters")
            report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
        self.assertEqual(report["timing_verdict"], "INCONCLUSIVE")
        self.assertTrue(any("healthy-path structural counters" in issue for issue in report["issues"]))

    def test_durability_only_report_keeps_healthy_growth_required_and_attributable(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder, fixed=False)
            rows = records(self.tool, schedule, folder)
            small = next(job for job in schedule["jobs"] if job["case"]["kind"] == "small-hdd-read" and job["arm"] == "B")
            next(row for row in rows if row["attempt_id"] == small["attempt_id"])["counters"]["upper_worker_hops"] = 1
            report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
        self.assertEqual(report["verdict"], "REGRESSION")
        self.assertEqual(report.get("structural_verdict"), "REGRESSION")
        affected = next(case for case in report["cases"] if case["case_id"] == small["case_id"])
        self.assertEqual(affected["structural_verdict"], "REGRESSION")

    def test_policy_contract_and_fixed_identity_mismatches_are_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder)
            original = records(self.tool, schedule, folder)
            for field in ("durability_policy_sha256", "workload_identity_sha256", "workload_policy_sha256"):
                with self.subTest(field=field):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    row[field] = "0" * 64
                    report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
                    self.assertEqual(report["timing_verdict"], "INCONCLUSIVE")

    def test_legacy_missing_physical_evidence_remains_a_failure(self):
        aa = fixtures.pilot_fixture(self.tool)
        rows = fixtures.records_for(aa)
        write = next(job for job in aa["jobs"] if job["case"]["kind"] == "write-flush")
        target = next(row for row in rows if row["attempt_id"] == write["attempt_id"])
        target.update(flushes_completed=None, durability_verified=None)
        _, _, failures, _ = self.tool.inspect_records(aa, rows)
        self.assertTrue(any("real flush or persistence" in failure for failure in failures))

    def test_raw_operations_require_the_actual_case_identity_not_just_matching_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            original = records(self.tool, aa, folder)
            for missing in (True, False):
                with self.subTest(missing=missing):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    raw = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
                    if missing:
                        del raw["operations"][1]["id"]
                    else:
                        raw["operations"][1]["id"] = "other-case"
                    row["api_timing_provenance"] = artifact(folder, "wrong-operation-id.json", raw)
                    metrics, issues, failures, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
                    self.assertFalse(row["attempt_id"] in metrics)
                    self.assertTrue(any(issue.startswith(row["attempt_id"] + ":") for issue in issues))
                    self.assertEqual(failures, [])

    def test_rehashed_raw_counter_or_frequency_changes_cannot_keep_unrelated_timings(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            original = records(self.tool, aa, folder)
            for field in ("batch", "operation", "frequency"):
                with self.subTest(field=field):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
                    if field == "batch":
                        ledger["summary"]["ticks"] = str(int(ledger["summary"]["ticks"]) * 100)
                    elif field == "operation":
                        ledger["operations"][0]["ticks"] = str(int(ledger["operations"][0]["ticks"]) * 100)
                    else:
                        ledger["meta"]["frequency"] = str(int(ledger["meta"]["frequency"]) * 100)
                    row["api_timing_provenance"] = artifact(folder, "unrelated-" + field + ".json", ledger)
                    metrics, issues, failures, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
                    self.assertFalse(row["attempt_id"] in metrics)
                    self.assertTrue(any(issue.startswith(row["attempt_id"] + ":") for issue in issues))
                    self.assertEqual(failures, [])

    def test_public_conversion_rule_and_representation_tolerance_are_explicit(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            original = records(self.tool, aa, folder)
            for ulps, qualified in ((8, True), (9, False)):
                with self.subTest(ulps=ulps):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    row["elapsed_ms"] += ulps * math.ulp(row["elapsed_ms"])
                    row["latencies_ms"][0] += ulps * math.ulp(row["latencies_ms"][0])
                    ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
                    ledger["timing_sha256"] = self.tool.digest({key: row[key] for key in ("elapsed_ms", "latencies_ms", "timing_scope")})
                    row["api_timing_provenance"] = artifact(folder, "roundtrip.json", ledger)
                    metrics, _, failures, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
                    self.assertEqual(row["attempt_id"] in metrics, qualified)
                    self.assertEqual(failures, [])
            for declared in (None, "unqualified-new-source"):
                changed = copy.deepcopy(aa)
                descriptor = changed["spec"]["durability_policy"]["timing_contract"]
                contract = json.loads((folder / descriptor["path"]).read_text())
                if declared is None:
                    del contract["timing_conversion"]
                else:
                    contract["timing_conversion"] = declared
                changed["spec"]["durability_policy"]["timing_contract"] = artifact(folder, "conversion-rule.json", contract)
                fixtures.reseal_fixture(changed)
                rows = records(self.tool, changed, folder)
                metrics, issues, failures, _ = self.tool.inspect_records(changed, rows, evidence_root=folder)
                self.assertTrue(all("api_timing_provenance" not in row or row["attempt_id"] not in metrics for row in rows))
                self.assertTrue(issues)
                self.assertEqual(failures, [])

    def test_malformed_zero_and_overflow_raw_conversion_remain_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            original = records(self.tool, aa, folder)
            for value in ("0", "not-an-integer", str(2**64)):
                with self.subTest(value=value):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
                    ledger["summary"]["ticks"] = value
                    row["api_timing_provenance"] = artifact(folder, "bad-raw-ticks.json", ledger)
                    metrics, issues, failures, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
                    self.assertFalse(row["attempt_id"] in metrics)
                    self.assertTrue(issues)
                    self.assertEqual(failures, [])

    def test_tiny_mapping_has_no_absolute_epsilon_and_invalid_values_stay_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            original = records(self.tool, aa, folder)
            for fault in ("tiny-valid", "tiny-factor100", "frequency-overflow", "nan", "infinity"):
                with self.subTest(fault=fault):
                    rows = copy.deepcopy(original)
                    row = next(row for row in rows if "api_timing_provenance" in row)
                    ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
                    if fault.startswith("tiny"):
                        frequency = 2**64 - 1
                        ledger["meta"]["frequency"] = str(frequency)
                        ledger["summary"]["ticks"] = str(len(ledger["operations"]))
                        for operation in ledger["operations"]:
                            operation["ticks"] = "1"
                        row["elapsed_ms"] = len(ledger["operations"]) * 1000 / frequency
                        row["latencies_ms"] = [1000 / frequency] * len(ledger["operations"])
                        if fault == "tiny-factor100":
                            row["latencies_ms"][0] *= 100
                        ledger["timing_sha256"] = self.tool.digest({key: row[key] for key in ("elapsed_ms", "latencies_ms", "timing_scope")})
                    elif fault == "frequency-overflow":
                        ledger["meta"]["frequency"] = str(2**64)
                    else:
                        row["elapsed_ms"] = float("nan" if fault == "nan" else "inf")
                    row["api_timing_provenance"] = artifact(folder, "numeric-safety.json", ledger)
                    metrics, issues, failures, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
                    self.assertEqual(row["attempt_id"] in metrics, fault == "tiny-valid")
                    if fault != "tiny-valid":
                        self.assertTrue(any(issue.startswith(row["attempt_id"] + ":") for issue in issues))
                    self.assertEqual(failures, [])

    def test_huge_reported_integer_does_not_escape_attributable_unknown_handling(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            rows = records(self.tool, aa, folder)
            row = next(row for row in rows if "api_timing_provenance" in row)
            ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
            row["elapsed_ms"] = 10**400
            ledger["timing_sha256"] = self.tool.digest({key: row[key] for key in ("elapsed_ms", "latencies_ms", "timing_scope")})
            row["api_timing_provenance"] = artifact(folder, "huge-reported-timing.json", ledger)
            try:
                metrics, issues, failures, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
            except OverflowError:
                self.fail("malformed reported timing escaped attributable unknown handling")
            self.assertFalse(row["attempt_id"] in metrics)
            self.assertTrue(any(issue.startswith(row["attempt_id"] + ":") for issue in issues))
            self.assertEqual(failures, [])

    def test_qualified_contract_bytes_and_source_are_required_without_defaults(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            rows = records(self.tool, aa, folder)
            policy = aa["spec"]["durability_policy"]
            descriptor = policy["timing_contract"]
            data = (folder / descriptor["path"]).read_bytes()
            (folder / descriptor["path"]).unlink()
            metrics, issues, _, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
            self.assertEqual(len(metrics), len(rows) - sum(job["case"]["kind"] == "write-flush" for job in aa["jobs"]))
            self.assertTrue(issues)
            (folder / descriptor["path"]).write_bytes(data)
            contract = json.loads(data)
            source = contract["source_artifacts"][0]
            (folder / source["path"]).unlink()
            metrics, issues, _, _ = self.tool.inspect_records(aa, rows, evidence_root=folder)
            self.assertEqual(metrics, {})  # Both fixed and public contract source bindings fail.
            self.assertTrue(issues)

    def test_public_reopen_failure_and_policy_count_changes_cannot_hide_in_unknown_physical_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            _, frozen, schedule = self.experiment(folder)
            rows = records(self.tool, schedule, folder)
            row = next(row for row in rows if "api_timing_provenance" in row)
            ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
            ledger["summary"]["persistence"] = "0"
            row["reopen_readback_verified"] = False
            row["api_timing_provenance"] = artifact(folder, "actual-failed-reopen.json", ledger)
            report = self.tool.compare(frozen, schedule, rows, "b" * 64, evidence_root=folder)
            self.assertEqual(report["timing_verdict"], "REGRESSION")
            self.assertEqual(report["verdict"], "REGRESSION")
            modified = copy.deepcopy(schedule)
            modified["spec"]["durability_policy"]["method"] += "-post-hoc"
            fixtures.reseal_fixture(modified)
            with self.assertRaisesRegex(ValueError, "rules/count changed"):
                self.tool.compare(frozen, modified, rows, "b" * 64, evidence_root=folder)


if __name__ == "__main__":
    unittest.main()
