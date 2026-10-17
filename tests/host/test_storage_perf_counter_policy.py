"""Invented clock provenance and raw ticks; arithmetic/interface controls only."""
import copy
import hashlib
import json
import pathlib
import tempfile
import unittest

import test_storage_perf_compare as legacy
import test_storage_perf_durability as public

RATE = 733333333


def specification(tool, folder, *, platform="deck", qpf=None, base_spec=None):
    spec = public.specification(tool, folder) if base_spec is None else base_spec
    source = public.artifact(folder, "clock-source.json", {"invented": "compiled source binding"})
    verifier = public.artifact(folder, "clock-verifier.py", {"invented": "reviewed importer; not executed"})
    helper = {"path": "interval-helper.py", "sha256": hashlib.sha256(
        (legacy.ROOT / "tools/storage_counter_intervals.py").read_bytes()).hexdigest()}
    (folder / helper["path"]).write_bytes((legacy.ROOT / "tools/storage_counter_intervals.py").read_bytes())
    contract = {"schema_version": 1, "conversion": "source-fixed-rdtsc", "counter_hz": RATE,
                "platform": platform, "xemu_sha256": spec["baseline"]["xemu_sha256"],
                "environment_sha256": tool.digest(spec["environment"]),
                "source_binding": source, "verifier_artifact": verifier, "interval_helper": helper,
                "assumptions": ["invented controlled host, not actual runtime qualification"]}
    if qpf is not None: contract["qpf_hz"] = qpf
    contract["review_receipt"] = public.artifact(folder, "clock-review.json", {
        "status": "reviewed_for_conditional_arithmetic", "reviewed_utc": "2025-12-31T00:00:00+00:00",
        "contract_facts_sha256": tool.digest(contract)})
    descriptor = public.artifact(folder, "clock-contract.json", contract)
    spec["counter_policy"] = {"schema_version": 1, "conversion": "source-fixed-rdtsc", "counter_hz": RATE,
                              "platform": platform, "paired_conversion_budget": {"numerator": 1, "denominator": 1000},
                              "context_contract": descriptor}
    old = spec["durability_policy"]["timing_contract"]
    public_contract = json.loads((folder / old["path"]).read_text())
    public_contract.update(timing_conversion="source-fixed-rdtsc", reported_timing_conversion="recorded-rdtsc-frequency")
    spec["durability_policy"]["timing_contract"] = public.artifact(folder, old["path"], public_contract)
    return spec


def records(tool, schedule, folder, *, operation_ticks=183333, candidate_delta=0, only_case=None):
    if only_case is not None:
        schedule = dict(schedule, jobs=[job for job in schedule["jobs"] if job["case_id"] == only_case])
    rows = public.records(tool, schedule, folder)
    contract_sha = schedule["spec"]["counter_policy"]["context_contract"]["sha256"]
    contract = json.loads((folder / schedule["spec"]["counter_policy"]["context_contract"]["path"]).read_text())
    for row, job in zip(rows, schedule["jobs"]):
        case = job["case"]
        frequency = 733444576  # Original estimated metadata, deliberately different from source rate.
        ticks = operation_ticks + (candidate_delta if job["arm"] == "B" else 0)
        batch = ticks * case["operations"]
        row.update(elapsed_ms=batch * 1000 / frequency,
                   latencies_ms=[ticks * 1000 / frequency] * case["operations"])
        lengths = case.get("operation_bytes", [case["bytes_per_operation"]] * case["operations"])
        if "api_timing_provenance" in row:
            ledger = json.loads((folder / row["api_timing_provenance"]["path"]).read_text())
        else:
            ledger = {"schema_version": 1, "meta": {"counter": "rdtsc"},
                      "summary": {"id": case["id"], "operations": str(case["operations"]),
                                  "bytes": str(sum(lengths)), "failures": "0"},
                      "end": {"cases": "1", "failures": "0"},
                      "operations": [{"id": case["id"], "index": str(i), "status": "00000000",
                                      "io_status": "00000000", "information": str(length)}
                                     for i, length in enumerate(lengths)]}
        ledger.update(**{field: row[field] for field in ("attempt_id", "schedule_sha256", "manifest_sha256",
                                                        "environment_sha256", "runner_sha256")}, case_sha256=tool.digest(case),
                      timing_sha256=tool.digest({key: row[key] for key in ("elapsed_ms", "latencies_ms", "timing_scope")}))
        ledger["meta"].update(frequency=str(frequency), frequency_min="733400000", frequency_max="733480000")
        ledger["summary"]["ticks"] = str(batch)
        for op in ledger["operations"]: op["ticks"] = str(ticks)
        raw = public.artifact(folder, job["attempt_id"] + "-counter.json", ledger)
        row["counter_provenance"] = raw
        if "api_timing_provenance" in row: row["api_timing_provenance"] = raw
        roles = ["request", "result", "input_manifest", "guard", "host_context"]
        if "artifact_policy" in schedule["spec"]: roles.append("preparation_receipt")
        evidence = {role: public.artifact(folder, job["attempt_id"] + "-" + role + ".json", {
            "invented": "not actual native bytes", "role": role, "job": job["attempt_id"]})
                    for role in roles}
        row["native_run_id"] = "invented-native-" + job["attempt_id"]
        row["clock_provenance"] = public.artifact(folder, job["attempt_id"] + "-clock.json", {
            "schema_version": 1, "verification_status": "verified_by_pinned_importer",
            "native_run_id": row["native_run_id"],
            **{field: row[field] for field in ("attempt_id", "schedule_sha256", "manifest_sha256", "environment_sha256", "runner_sha256")},
            "case_sha256": tool.digest(case), "context_contract_sha256": contract_sha,
            "verifier_sha256": contract["verifier_artifact"]["sha256"],
            "raw_counter_sha256": raw["sha256"], "native_evidence": evidence})
    return rows


class StoragePerformanceCounterPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.tool = legacy.load_tool()

    def pilot(self, folder, **options):
        schedule = self.tool.make_schedule(specification(self.tool, folder, **options))
        schedule["created_utc"] = "2026-01-01T00:00:00+00:00"
        return legacy.reseal_fixture(schedule)

    def test_source_rate_derives_separate_metrics_and_preserves_reported_values(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp); schedule = self.pilot(folder)
            rows = records(self.tool, schedule, folder)
            original = copy.deepcopy(rows)
            metrics, issues, failures, _ = self.tool.inspect_records(schedule, rows, evidence_root=folder)
            self.assertFalse(issues or failures)
            self.assertEqual(rows, original)
            self.assertAlmostEqual(metrics[rows[0]["attempt_id"]]["latency"], 183333 * 1024 * 1000 / RATE)
            self.assertNotEqual(metrics[rows[0]["attempt_id"]]["latency"], rows[0]["elapsed_ms"])
            ledger = json.loads((folder / rows[0]["counter_provenance"]["path"]).read_text())
            self.assertEqual(ledger["meta"]["frequency"], "733444576")
            self.assertEqual(ledger["meta"]["frequency_min"], "733400000")

    def test_counter_policy_requires_exact_supported_rate_and_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            original = specification(self.tool, pathlib.Path(temp))
            for field, value in (("counter_hz", RATE + 1), ("platform", "unknown"),
                                 ("paired_conversion_budget", {"numerator": 2, "denominator": 1000})):
                with self.subTest(field=field):
                    spec = copy.deepcopy(original);spec["counter_policy"][field] = value
                    with self.assertRaises(ValueError): self.tool.make_schedule(spec)

    def test_missing_unreviewed_or_wrong_context_never_qualifies_from_boolean(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);schedule = self.pilot(folder)
            original = records(self.tool, schedule, folder)
            for fault in ("missing", "boolean", "verifier", "binding", "raw", "evidence"):
                with self.subTest(fault=fault):
                    rows = copy.deepcopy(original); row = rows[0]
                    proof = json.loads((folder / row["clock_provenance"]["path"]).read_text())
                    if fault == "missing": del row["clock_provenance"]
                    elif fault == "boolean": row["clock_provenance"] = {"verified": True}
                    else:
                        if fault == "verifier": proof["verifier_sha256"] = "0" * 64
                        if fault == "binding": proof["manifest_sha256"] = "0" * 64
                        if fault == "raw": proof["raw_counter_sha256"] = "0" * 64
                        if fault == "evidence": proof["native_evidence"] = []
                        row["clock_provenance"] = public.artifact(folder, "fault-" + fault + ".json", proof)
                    metrics, issues, failures, _ = self.tool.inspect_records(schedule, rows, evidence_root=folder)
                    self.assertNotIn(row["attempt_id"], metrics)
                    self.assertTrue(issues);self.assertFalse(failures)

    def test_coherent_raw_tick_frequency_and_operation_faults_are_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);schedule = self.pilot(folder)
            original = records(self.tool, schedule, folder)
            for fault in ("ticks", "frequency", "index", "case", "missing", "zero"):
                with self.subTest(fault=fault):
                    rows = copy.deepcopy(original); row = rows[0]
                    raw = json.loads((folder / row["counter_provenance"]["path"]).read_text())
                    if fault == "ticks": raw["summary"]["ticks"] = str(int(raw["summary"]["ticks"]) * 100)
                    if fault == "frequency": raw["meta"]["frequency"] = "1"
                    if fault == "index": raw["operations"][-1]["index"] = "0"
                    if fault == "case": raw["operations"][-1]["id"] = "wrong-case"
                    if fault == "missing": raw["operations"].pop()
                    if fault == "zero": raw["operations"][-1]["ticks"] = "0"
                    row["counter_provenance"] = public.artifact(folder, "raw-" + fault + ".json", raw)
                    proof = json.loads((folder / row["clock_provenance"]["path"]).read_text())
                    proof["raw_counter_sha256"] = row["counter_provenance"]["sha256"]
                    row["clock_provenance"] = public.artifact(folder, "proof-" + fault + ".json", proof)
                    metrics, issues, _, _ = self.tool.inspect_records(schedule, rows, evidence_root=folder)
                    self.assertNotIn(row["attempt_id"], metrics);self.assertTrue(issues)

    def test_whole_aa_refuses_budget_excess_or_zero_endpoints_without_filtering(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);schedule = self.pilot(folder)
            for ticks in (1, 2000):
                with self.subTest(ticks=ticks):
                    rows = records(self.tool, schedule, folder, operation_ticks=ticks)
                    with self.assertRaises(ValueError):
                        self.tool.calibrate(schedule, rows, "a" * 64, evidence_root=folder)
            rows = records(self.tool, schedule, folder, operation_ticks=2001)
            frozen = self.tool.calibrate(schedule, rows, "a" * 64, evidence_root=folder)
            self.assertEqual(len(frozen["pilot_intervals"]), 36)
            self.assertEqual(len(frozen["pilot_intervals"][schedule["jobs"][0]["case_id"]]["p99"]), 5)

    def test_planning_counts_upper_endpoints_not_only_central_ratios(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);spec = specification(self.tool, folder)
            spec["limits"].update(latency=1, p95=1, p99=1)
            schedule = self.tool.make_schedule(spec)
            schedule["created_utc"] = "2026-01-01T00:00:00+00:00";legacy.reseal_fixture(schedule)
            with self.assertRaises(ValueError):
                self.tool.calibrate(schedule, records(self.tool, schedule, folder), "a" * 64, evidence_root=folder)

    def test_windows_context_requires_actual_qpf_and_uses_platform_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);schedule = self.pilot(folder, platform="windows")
            with self.assertRaises(ValueError):
                self.tool.calibrate(schedule, records(self.tool, schedule, folder), "a" * 64, evidence_root=folder)
        for frequency, ticks, qualified in ((10000000, 2001, True), (3000001, 3468, False), (3000001, 3469, True)):
            with self.subTest(frequency=frequency,ticks=ticks), tempfile.TemporaryDirectory() as temp:
                folder = pathlib.Path(temp);schedule = self.pilot(folder, platform="windows",qpf=frequency)
                rows = records(self.tool, schedule, folder, operation_ticks=ticks)
                if qualified:
                    self.tool.calibrate(schedule, rows, "a" * 64, evidence_root=folder)
                else:
                    with self.assertRaises(ValueError): self.tool.calibrate(schedule, rows, "a" * 64,evidence_root=folder)

    def test_confirmatory_ranked_endpoints_can_cross_limit_despite_central_margin(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);spec = specification(self.tool, folder)
            spec["limits"].update(latency=1.0005,p95=1.0005,p99=1.0005)
            aa = self.tool.make_schedule(spec)
            aa["created_utc"] = "2026-01-01T00:00:00+00:00";legacy.reseal_fixture(aa)
            frozen = self.tool.calibrate(aa, records(self.tool, aa, folder, operation_ticks=200000), "a" * 64,evidence_root=folder)
            frozen["created_utc"] = "2026-01-02T00:00:00+00:00";legacy.reseal_fixture(frozen)
            candidate = legacy.candidate_manifest();candidate["fixture_sha256"] = spec["baseline"]["fixture_sha256"]
            ab = legacy.confirmatory_fixture(self.tool, frozen, candidate)
            selected = spec["cases"][0]["id"]
            partial = records(self.tool, ab, folder, operation_ticks=2001,candidate_delta=1,only_case=selected)
            report = self.tool.compare(frozen, ab, partial, "b" * 64,evidence_root=folder)
            metric = next(case for case in report["cases"] if case["case_id"] == selected)["metrics"]["p99"]
            self.assertEqual(metric["pairs"], ab["pairs"])
            self.assertLess(metric["median_ratio"], 1.0005)
            self.assertEqual(metric["verdict"], "INCONCLUSIVE")
            self.assertEqual(metric["lower_exact"], {"numerator": 2001,"denominator": 2002})
            self.assertEqual(metric["upper_exact"], {"numerator": 2003,"denominator": 2000})
            self.assertTrue(report["counter_conversion"]["arithmetic_envelope_only"])
            retained = next(row for row in report["counter_conversion"]["attempts"] if row["attempt_id"] == partial[0]["attempt_id"])
            self.assertEqual(retained["elapsed_ms"], partial[0]["elapsed_ms"])
            small = records(self.tool, ab, folder, operation_ticks=2000,only_case=selected)
            report = self.tool.compare(frozen, ab, small, "c" * 64,evidence_root=folder)
            metric = next(case for case in report["cases"] if case["case_id"] == selected)["metrics"]["p99"]
            self.assertEqual(metric["pairs"], ab["pairs"])
            self.assertEqual(metric["conversion_verdict"], "INCONCLUSIVE")
            self.assertIsNone(metric["upper_exact"])
            self.assertEqual(len(metric["ratio_intervals"]), ab["pairs"])

    def test_readable_review_and_source_contract_facts_are_checked_after_rehashing(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);original = specification(self.tool, folder)
            original_contract = json.loads((folder / original["counter_policy"]["context_contract"]["path"]).read_text())
            for fault in ("unreviewed", "late", "source", "helper"):
                with self.subTest(fault=fault):
                    spec = copy.deepcopy(original);contract = copy.deepcopy(original_contract)
                    review = {"status":"reviewed_for_conditional_arithmetic","reviewed_utc":"2025-12-31T00:00:00+00:00"}
                    if fault == "unreviewed": review["status"] = "draft"
                    if fault == "late": review["reviewed_utc"] = "2027-01-01T00:00:00+00:00"
                    if fault == "source": contract["xemu_sha256"] = "0" * 64
                    if fault == "helper": contract["interval_helper"] = public.artifact(folder,"wrong-helper.py",{"invented":"other code"})
                    review["contract_facts_sha256"] = self.tool.digest({key:value for key,value in contract.items() if key != "review_receipt"})
                    contract["review_receipt"] = public.artifact(folder,fault+"-review.json",review)
                    spec["counter_policy"]["context_contract"] = public.artifact(folder,fault+"-contract.json",contract)
                    schedule = self.tool.make_schedule(spec)
                    schedule["created_utc"] = "2026-01-01T00:00:00+00:00";legacy.reseal_fixture(schedule)
                    row = records(self.tool,schedule,folder,only_case=spec["cases"][0]["id"])[0]
                    metrics,issues,failures,_ = self.tool.inspect_records(schedule,[row],evidence_root=folder)
                    self.assertNotIn(row["attempt_id"],metrics)
                    self.assertTrue(any(issue.startswith(row["attempt_id"]+":") for issue in issues));self.assertFalse(failures)

    def test_observed_raw_native_error_is_regression_not_silent_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);schedule = self.pilot(folder)
            row = records(self.tool,schedule,folder,only_case=schedule["spec"]["cases"][0]["id"])[0]
            raw = json.loads((folder / row["counter_provenance"]["path"]).read_text())
            raw["operations"][0]["io_status"] = "c0000001"
            row["counter_provenance"] = public.artifact(folder,"observed-error.json",raw)
            proof = json.loads((folder / row["clock_provenance"]["path"]).read_text())
            proof["raw_counter_sha256"] = row["counter_provenance"]["sha256"]
            row["clock_provenance"] = public.artifact(folder,"observed-error-proof.json",proof)
            metrics,_,failures,_ = self.tool.inspect_records(schedule,[row],evidence_root=folder)
            self.assertNotIn(row["attempt_id"],metrics)
            self.assertTrue(any("observed raw counter operation" in failure for failure in failures))

    def test_resealed_calibration_cannot_omit_trim_or_overflow_exact_interval_facts(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp);schedule = self.pilot(folder)
            frozen = self.tool.calibrate(schedule,records(self.tool,schedule,folder),"a" * 64,evidence_root=folder)
            for fault in ("missing","trim","overflow"):
                with self.subTest(fault=fault):
                    value = copy.deepcopy(frozen)
                    if fault == "missing": del value["pilot_intervals"]
                    elif fault == "trim": next(iter(value["pilot_intervals"].values()))["p99"].pop()
                    else:
                        facts = next(iter(value["pilot_intervals"].values()))["p99"][0]
                        for key in ("center","lower","upper"): facts[key] = {"numerator":10**400,"denominator":1}
                    legacy.reseal_fixture(value)
                    with self.assertRaises(ValueError): self.tool.validate_calibration(value)

    def test_per_case_artifact_and_clock_receipts_must_join_exact_native_inputs(self):
        import test_storage_perf_artifacts as artifacts
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            spec = specification(self.tool,folder,base_spec=artifacts.specification(self.tool,folder))
            schedule = self.tool.make_schedule(spec)
            schedule["created_utc"] = "2026-01-01T00:00:00+00:00";legacy.reseal_fixture(schedule)
            selected = next(case["id"] for case in spec["cases"] if case["kind"] == "dvd-xiso")
            partial_schedule = dict(schedule,jobs=[job for job in schedule["jobs"] if job["case_id"] == selected])
            artifact_rows = artifacts.rows(self.tool,partial_schedule,folder)
            counter_rows = records(self.tool,schedule,folder,only_case=selected)
            for row, artifact_row in zip(counter_rows,artifact_rows):
                row.update(**{key:artifact_row[key] for key in ("artifact_set_sha256","case_artifact_sha256","artifact_bindings")})
                proof = json.loads((folder / row["clock_provenance"]["path"]).read_text())
                for role in ("request","input_manifest","preparation_receipt"):
                    row["artifact_bindings"][role + "_sha256"] = proof["native_evidence"][role]["sha256"]
            metrics,issues,failures,_ = self.tool.inspect_records(schedule,counter_rows,evidence_root=folder)
            self.assertEqual(len(metrics),len(counter_rows));self.assertFalse(failures)
            self.assertFalse(any(issue.startswith(row["attempt_id"]+":") for issue in issues for row in counter_rows))
            counter_rows[0]["artifact_bindings"]["request_sha256"] = "0" * 64
            metrics,issues,_,_ = self.tool.inspect_records(schedule,counter_rows,evidence_root=folder)
            self.assertNotIn(counter_rows[0]["attempt_id"],metrics)
            self.assertTrue(any("importer receipts differ" in issue for issue in issues))
