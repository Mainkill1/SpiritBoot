"""Invented multi-recorder artifacts; no executed native or physical evidence."""
import copy
import hashlib
import json
import pathlib
import tempfile
import unittest

import test_storage_perf_compare as legacy
import test_storage_perf_durability as public


def file_artifact(folder, name, raw):
    (folder / name).write_bytes(raw)
    return {"path": name, "sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def specification(tool, folder):
    spec = public.specification(tool, folder)
    del spec["baseline"]["fixture_sha256"]
    del spec["baseline"]["iso_sha256"]
    suite = file_artifact(folder, "suite.xbe", b"invented suite executable")
    suite_iso = file_artifact(folder, "suite.iso", b"invented suite image")
    recorder = file_artifact(folder, "dvd.xbe", b"invented DVD executable")
    source = file_artifact(folder, "recorder-source.txt", b"invented source binding")
    build = file_artifact(folder, "build.json", b'{"invented":"build receipt"}')
    recipe = file_artifact(folder, "recipe.json", b'{"invented":"prepared-image recipe"}')
    entries = {}
    for case in spec["cases"]:
        entry = {"recorder_xbe": suite, "boot_iso": suite_iso, "measured_media_iso": suite_iso,
                 "recorder_source": source, "recorder_build": build,
                 "hdd_seed": {"asset_id": "invented-original-seed", "sha256": "a" * 64},
                 "preparation": {"mode": "prepared_xiso", "recipe": recipe}}
        if case["kind"] == "dvd-xiso":
            variant = case["variant"]
            payload = (variant.encode() + b"!") * 512
            entry.update(recorder_xbe=recorder,
                         boot_iso=file_artifact(folder, variant + ".iso", b"wrapper:" + payload),
                         original_released_iso=file_artifact(folder, variant + "-original.iso", b"original:" + payload),
                         extracted_target_xbe=file_artifact(folder, variant + "-target.xbe", payload),
                         reference_header=file_artifact(folder, variant + "-reference.bin", payload[:4096]),
                         source_filename="default.xbe", request_filename="target.xbe",
                         request_path="\\Device\\CdRom0\\target.xbe")
            entry["measured_media_iso"] = entry["boot_iso"]
            case.update(iso_sha256=entry["measured_media_iso"]["sha256"],
                        request_path=entry["request_path"],
                        request_vectors=[{"index": i, "file": "target.xbe", "offset": 0, "bytes": 512}
                                         for i in range(case["operations"])])
        entry["preparation"] = dict(entry["preparation"], request_contract=public.artifact(
            folder, case["id"] + "-request.json", {"case_sha256": tool.digest(case)}))
        entry["preparation"]["request_contract"]["bytes"] = (
            folder / entry["preparation"]["request_contract"]["path"]).stat().st_size
        entries[case["id"]] = entry
    descriptor = public.artifact(folder, "artifact-set.json", {"schema_version": 1, "cases": entries})
    descriptor["bytes"] = (folder / descriptor["path"]).stat().st_size
    spec["artifact_policy"] = {"schema_version": 1, "mode": "per-case", "artifact_set": descriptor, "cases": entries}
    policy = spec["workload_policy"]
    del policy["fixture_sha256"]
    policy["artifact_set_sha256"] = descriptor["sha256"]
    for key, field in (("workload_policy", "fixture_contract"), ("durability_policy", "timing_contract")):
        old = spec[key][field]
        contract = json.loads((folder / old["path"]).read_text())
        del contract["fixture_sha256"]
        del contract["fixture_artifact"]
        contract.update(artifact_set_sha256=descriptor["sha256"],
                        cases={case["id"]: tool.digest(case) for case in spec["cases"]})
        spec[key][field] = public.artifact(folder, old["path"], contract)
    return spec


def rows(tool, schedule, folder):
    records = public.records(tool, schedule, folder)
    for row, job in zip(records, schedule["jobs"]):
        entry = schedule["spec"]["artifact_policy"]["cases"][job["case_id"]]
        row.update(artifact_set_sha256=job["artifact_set_sha256"], case_artifact_sha256=job["case_artifact_sha256"],
                   artifact_bindings={
                       "verified_by_native_importer": True,
                       "case_artifact_sha256": job["case_artifact_sha256"],
                       "request_sha256": "1" * 64, "input_manifest_sha256": "2" * 64,
                       "preparation_receipt_sha256": "3" * 64,
                       "recorder_xbe_sha256": entry["recorder_xbe"]["sha256"],
                       "boot_iso_sha256": entry["boot_iso"]["sha256"],
                       "measured_media_iso_sha256": entry["measured_media_iso"]["sha256"],
                       "source_seed_sha256": entry["hdd_seed"]["sha256"],
                       "source_seed_asset_id": entry["hdd_seed"]["asset_id"],
                       "preparation_mode": "prepared_xiso",
                       "prepared_image": {"sha256": hashlib.sha256(job["attempt_id"].encode()).hexdigest(), "bytes": 1310720},
                       "eeprom_source_sha256": job["manifest"]["eeprom_sha256"]})
    return records


class StoragePerformanceArtifacts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tool = legacy.load_tool()

    def pilot(self, folder):
        schedule = self.tool.make_schedule(specification(self.tool, folder))
        schedule["created_utc"] = "2026-01-01T00:00:00+00:00"
        return legacy.reseal_fixture(schedule)

    def test_full36_resolves_actual_case_files_without_faking_global_fixture(self):
        with tempfile.TemporaryDirectory() as temp:
            schedule = self.pilot(pathlib.Path(temp))
            self.tool.validate_schedule(schedule)
        self.assertEqual(len(schedule["spec"]["cases"]), 36)
        self.assertNotIn("fixture_sha256", schedule["spec"]["baseline"])
        self.assertNotIn("iso_sha256", schedule["spec"]["baseline"])
        self.assertEqual(len({job["manifest"]["fixture_sha256"] for job in schedule["jobs"]}), 2)
        self.assertEqual(len({job["manifest"]["iso_sha256"] for job in schedule["jobs"]}), 3)
        for job in schedule["jobs"]:
            self.assertNotEqual(job["artifact_set_sha256"], job["manifest"]["fixture_sha256"])

    def test_complete_aa_and_ab_keep_varying_prepared_bytes_and_physical_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            aa = self.pilot(folder)
            frozen = self.tool.calibrate(aa, rows(self.tool, aa, folder), "a" * 64, evidence_root=folder)
            frozen["created_utc"] = "2026-01-02T00:00:00+00:00"
            legacy.reseal_fixture(frozen)
            candidate = legacy.candidate_manifest()
            del candidate["fixture_sha256"]
            del candidate["iso_sha256"]
            ab = legacy.confirmatory_fixture(self.tool, frozen, candidate)
            records = rows(self.tool, ab, folder)
            report = self.tool.compare(frozen, ab, records, "b" * 64, evidence_root=folder)
        self.assertEqual(report["timing_verdict"], "PASS")
        self.assertEqual(report["durability_verdict"], "INCONCLUSIVE")
        self.assertEqual(report["verdict"], "INCONCLUSIVE")
        self.assertEqual(report["valid_runs"], len(ab["jobs"]))
        evidence = report["artifact_attempts"]
        self.assertEqual(len(evidence), len(records))
        self.assertGreater(len({row["artifact_bindings"]["prepared_image"]["sha256"] for row in evidence}), 1)
        self.assertTrue(all(row["artifact_bindings"]["source_seed_sha256"] == "a" * 64 for row in evidence))

    def test_missing_extra_or_ambiguous_case_binding_rejects_before_scheduling(self):
        with tempfile.TemporaryDirectory() as temp:
            original = specification(self.tool, pathlib.Path(temp))
            for fault in ("missing", "extra", "mixed", "seed"):
                with self.subTest(fault=fault):
                    spec = copy.deepcopy(original)
                    entries = spec["artifact_policy"]["cases"]
                    if fault == "missing": entries.pop(next(iter(entries)))
                    if fault == "extra": entries["unscheduled"] = next(iter(entries.values()))
                    if fault == "mixed": spec["baseline"]["fixture_sha256"] = "8" * 64
                    if fault == "seed": next(iter(entries.values()))["hdd_seed"]["sha256"] = "0" * 64
                    with self.assertRaises(ValueError): self.tool.make_schedule(spec)

    def test_stale_dvd_filename_cannot_hide_inside_rehashed_case_descriptor(self):
        with tempfile.TemporaryDirectory() as temp:
            original = specification(self.tool, pathlib.Path(temp))
            for fault in ("path", "vector", "index", "bytes"):
                with self.subTest(fault=fault):
                    spec = copy.deepcopy(original)
                    case = next(case for case in spec["cases"] if case["kind"] == "dvd-xiso")
                    if fault == "path": case["request_path"] = "\\Device\\CdRom0\\default.xbe"
                    if fault == "vector": case["request_vectors"][-1]["file"] = "default.xbe"
                    if fault == "index": case["request_vectors"][-1]["index"] = 0
                    if fault == "bytes": case["request_vectors"][-1]["bytes"] = 1024
                    with self.assertRaises(ValueError): self.tool.make_schedule(spec)

    def test_actual_role_and_set_bytes_are_required_not_just_declared_hashes(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            schedule = self.pilot(folder)
            records = rows(self.tool, schedule, folder)
            for fault in ("file", "set", "length"):
                with self.subTest(fault=fault):
                    descriptor = schedule["spec"]["artifact_policy"]["artifact_set"]
                    path = folder / ("suite.xbe" if fault == "file" else descriptor["path"])
                    saved = path.read_bytes()
                    if fault == "file": path.unlink()
                    elif fault == "set": path.write_bytes(b"{}")
                    else:
                        descriptor["bytes"] += 1
                        legacy.reseal_fixture(schedule)
                        records = rows(self.tool, schedule, folder)
                    metrics, issues, failures, _ = self.tool.inspect_records(schedule, records, evidence_root=folder)
                    self.assertLess(len(metrics), len(records))
                    self.assertTrue(issues)
                    self.assertFalse(failures)
                    path.write_bytes(saved)
                    if fault == "length": descriptor["bytes"] -= 1

    def test_unverified_missing_wrong_role_or_source_prepared_alias_is_unknown(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            schedule = self.pilot(folder)
            original = rows(self.tool, schedule, folder)
            for fault in ("missing", "unverified", "role", "seed", "prepared", "receipt", "eeprom"):
                with self.subTest(fault=fault):
                    records = copy.deepcopy(original)
                    bindings = records[0]["artifact_bindings"]
                    if fault == "missing": del records[0]["artifact_bindings"]
                    if fault == "unverified": bindings["verified_by_native_importer"] = False
                    if fault == "role": bindings["measured_media_iso_sha256"] = "0" * 64
                    if fault == "seed": bindings["source_seed_sha256"] = "0" * 64
                    if fault == "prepared": bindings["prepared_image"]["sha256"] = "a" * 64
                    if fault == "receipt": bindings.pop("input_manifest_sha256")
                    if fault == "eeprom": bindings["eeprom_source_sha256"] = "0" * 64
                    metrics, issues, failures, _ = self.tool.inspect_records(schedule, records, evidence_root=folder)
                    self.assertEqual(len(metrics), len(records) - 1)
                    self.assertTrue(any(issue.startswith(records[0]["attempt_id"] + ":") for issue in issues))
                    self.assertFalse(failures)

    def test_resealed_cross_case_manifest_rejects(self):
        with tempfile.TemporaryDirectory() as temp:
            schedule = self.pilot(pathlib.Path(temp))
            dvd = next(job for job in schedule["jobs"] if job["case"]["kind"] == "dvd-xiso")
            job = next(job for job in schedule["jobs"] if job["case"]["kind"] != "dvd-xiso")
            job["manifest"] = copy.deepcopy(dvd["manifest"])
            job["manifest_sha256"] = self.tool.digest(job["manifest"])
            legacy.reseal_fixture(schedule)
            with self.assertRaises(ValueError): self.tool.validate_schedule(schedule)

    def test_resealed_case_artifact_labels_reject(self):
        with tempfile.TemporaryDirectory() as temp:
            original = self.pilot(pathlib.Path(temp))
            for field in ("artifact_set_sha256", "case_artifact_sha256"):
                with self.subTest(field=field):
                    schedule = copy.deepcopy(original)
                    schedule["jobs"][0][field] = "0" * 64
                    legacy.reseal_fixture(schedule)
                    with self.assertRaises(ValueError): self.tool.validate_schedule(schedule)

    def test_direct_schedule_api_rejects_ambiguous_candidate_global_files(self):
        with tempfile.TemporaryDirectory() as temp:
            spec = specification(self.tool, pathlib.Path(temp))
            candidate = legacy.candidate_manifest()
            with self.assertRaises(ValueError):
                self.tool.make_schedule(spec, "AB", 30, candidate, "a" * 64)

    def test_malformed_policy_or_file_role_is_attributable_before_scheduling(self):
        with tempfile.TemporaryDirectory() as temp:
            original = specification(self.tool, pathlib.Path(temp))
            for fault in ("policy", "set", "media"):
                with self.subTest(fault=fault):
                    spec = copy.deepcopy(original)
                    if fault == "policy": spec["artifact_policy"] = None
                    if fault == "set": del spec["artifact_policy"]["artifact_set"]
                    if fault == "media":
                        case = next(case for case in spec["cases"] if case["kind"] == "dvd-xiso")
                        spec["artifact_policy"]["cases"][case["id"]]["measured_media_iso"] = None
                    with self.assertRaises(ValueError): self.tool.make_schedule(spec)

    def test_direct_copy_identity_is_exact_source_while_prepared_images_vary(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = pathlib.Path(temp)
            spec = specification(self.tool, folder)
            for entry in spec["artifact_policy"]["cases"].values():
                entry["preparation"]["mode"] = "direct_copy"
            descriptor = public.artifact(folder, "artifact-set.json", {
                "schema_version": 1, "cases": spec["artifact_policy"]["cases"]})
            spec["artifact_policy"]["artifact_set"] = descriptor
            spec["workload_policy"]["artifact_set_sha256"] = descriptor["sha256"]
            for key, field in (("workload_policy", "fixture_contract"), ("durability_policy", "timing_contract")):
                old = spec[key][field]
                contract = json.loads((folder / old["path"]).read_text())
                contract["artifact_set_sha256"] = descriptor["sha256"]
                spec[key][field] = public.artifact(folder, old["path"], contract)
            schedule = self.tool.make_schedule(spec)
            schedule["created_utc"] = "2026-01-01T00:00:00+00:00"
            legacy.reseal_fixture(schedule)
            records = rows(self.tool, schedule, folder)
            for row in records:
                row["artifact_bindings"].update(preparation_mode="direct_copy", prepared_image={"sha256": "a" * 64, "bytes": 1310720})
            metrics, issues, failures, _ = self.tool.inspect_records(schedule, records, evidence_root=folder)
            self.assertEqual(len(metrics), len(records))
            self.assertFalse(issues or failures)
            records[0]["artifact_bindings"]["prepared_image"]["sha256"] = "0" * 64
            metrics, issues, _, _ = self.tool.inspect_records(schedule, records, evidence_root=folder)
            self.assertEqual(len(metrics), len(records) - 1)
            self.assertTrue(issues)

    def test_legacy_single_fixture_and_seed_schedule_is_unchanged(self):
        schedule = legacy.pilot_fixture(self.tool)
        self.tool.validate_schedule(schedule)
        self.assertTrue(all(job["manifest"] == schedule["spec"]["baseline"] for job in schedule["jobs"]))
        self.assertNotIn("artifact_set_sha256", schedule["jobs"][0])
        self.assertEqual({job["workload_seed"] for job in schedule["jobs"]}, set(range(41, 46)))
