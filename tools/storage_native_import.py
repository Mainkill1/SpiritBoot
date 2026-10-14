#!/usr/bin/env python3
"""Local replay of reviewed native evidence; never dispatches or starts a VM.

Approval/code/ledger pins are explicit caller inputs, not self-declared evidence
authority. Unsigned controlled-lab receipts provide consistency, not proof
against a hostile machine. Historical functional runs remain ineligible for A/A.
"""
import argparse
import copy
import hashlib
import importlib.util
import json
import re
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        require(key not in value, "duplicate JSON field: " + key)
        value[key] = item
    return value


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=unique_object)


def pinned(path, expected):
    require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected)
            and sha(path) == expected, "trusted file pin differs: " + str(path))
    return read(path)


def load_owned(name):
    path = Path(__file__).with_name(name)
    spec = importlib.util.spec_from_file_location("native_import_" + name.replace(".", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativeImporter:
    """Replay the exact reviewed collector, with evidence locations supplied by the caller."""
    def __init__(self, *, collector_path, collector_sha256, review_path, review_sha256,
                 evidence_root, ledger_path, ledger_sha256, plan_path=None):
        self.evidence_root = Path(evidence_root).resolve()
        self.collector_path = Path(collector_path).resolve()
        review = pinned(review_path, review_sha256)
        require(review.get("status") == "reviewed_no_critical_or_important_findings"
                and review.get("collector_sha256") == collector_sha256,
                "external review does not approve collector")
        require(sha(self.collector_path) == collector_sha256, "trusted collector bytes differ")
        self.plan_path = Path(plan_path or self.collector_path.with_name("qualification-plan.json")).resolve()
        self.plan = pinned(self.plan_path, review["plan_sha256"])
        manifest_path = self.plan_path.with_name("manifest.json")
        manifest = pinned(manifest_path, review["manifest_sha256"])
        root, seen = self.plan_path.parent, set()
        for item in manifest["files"]:
            relative = Path(item["path"])
            require(not relative.is_absolute() and ".." not in relative.parts and relative.as_posix() == item["path"]
                    and item["path"] not in seen, "invalid or duplicate approved source path")
            seen.add(item["path"])
            path = root / relative
            require(path.resolve().is_relative_to(root) and not path.is_symlink() and path.is_file()
                    and type(item["bytes"]) is int and path.stat().st_size == item["bytes"]
                    and sha(path) == item["sha256"], "approved source/input bytes differ: " + item["path"])
        # Only the explicitly named, externally pinned implementation is executed.
        # JSON evidence never selects executable code.
        spec = importlib.util.spec_from_file_location("reviewed_native_import_collector", self.collector_path)
        self.collector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.collector)
        if hasattr(self.collector, "configure"):
            self.collector.configure(root, review["plan_sha256"])
        require(self.collector.PLAN_SHA == review["plan_sha256"] and self.collector.PLAN == self.plan,
                "collector initialized a different native plan")
        self.collector.validate_review(review)
        parser = load_owned("storage_native_runner.py")
        require(sha(Path(parser.__file__)) == review["parser_sha256"] == self.plan["parser_sha256"],
                "product parser differs from approved native method")
        self.collector.native = parser
        self.parser = parser
        require(sha(ledger_path) == ledger_sha256, "trusted native ledger bytes differ")
        self.rows = []
        for line_number, line in enumerate(Path(ledger_path).read_text(encoding="utf-8-sig").splitlines(), 1):
            try:
                row = json.loads(line, object_pairs_hook=unique_object)
                require(isinstance(row, dict), "native ledger row must be an object")
            except ValueError as error:
                raise ValueError(f"native ledger line {line_number}: {error}") from error
            self.rows.append(row)
        attempts = [row.get("attempt_id") for row in self.rows]
        runs = [row.get("run_id") for row in self.rows]
        require(all(isinstance(value, str) for value in attempts) and len(set(attempts)) == len(attempts),
                "duplicate or missing native attempt")
        require(all(isinstance(value, str) and Path(value).name == value
                and value not in ("", ".", "..") for value in runs) and len(set(runs)) == len(runs),
                "duplicate or missing actual native run")
        self.by_id = {row["attempt_id"]: row for row in self.rows}
        self.declared = {row["id"]: row for row in self.plan["attempts"]}
        require(len(self.declared) == len(self.plan["attempts"]) and set(self.by_id).issubset(self.declared),
                "native ledger contains unknown or duplicate plan attempts")

    def verify_attempt(self, attempt_id):
        require(attempt_id in self.by_id, "actual native attempt missing")
        prior, attempt = self.by_id[attempt_id], self.declared[attempt_id]
        evidence = self.evidence_root / prior["run_id"]
        require(evidence.resolve().is_relative_to(self.evidence_root) and not evidence.is_symlink(),
                "native evidence directory escaped")
        output = {"attempt_id": attempt_id, "native_run_id": prior["run_id"],
                  "verification_status": "failed_verification", "performance_eligible": False,
                  "eligibility_reasons": ["no pre-capture A/A schedule binding in historical functional plan"],
                  "normative_clock_qualified": False, "provider_precision_proved": False}
        actual = {}
        try:
            # Observe before grading so failures retain the real outcome and available hashes.
            observed = self.collector.observe(evidence, actual)
            output.update({key: value for key, value in actual.items() if key != "artifacts"})
            require(prior.get("plan_sha256") == self.collector.PLAN_SHA
                    and prior.get("parser_sha256") == self.plan["parser_sha256"]
                    and prior.get("collector_sha256") == sha(self.collector_path), "native ledger method identity differs")
            require(prior.get("performance_acceptance_eligible") is attempt.get("performance_acceptance_eligible"),
                    "native ledger altered declared eligibility")
            for key, value in actual.items():
                if key != "artifacts":
                    require(prior.get(key) == value, "retained original native artifact/outcome differs: " + key)
            validated = self.collector.evaluate(attempt, evidence, observed)
            for key, value in validated.items():
                require(prior.get(key) == value, "retained original native grading differs: " + key)
            require(prior.get("status") == "qualified_for_declared_scope", "original native outcome was not qualified")
            raw, result, manifest, cleanup = observed
            launch = read(evidence / "launch.json")
            require(launch["runId"] == prior["run_id"] and launch["job"] == attempt_id
                    and launch["executableSha256"] == result["executableSha256"]
                    and launch.get("startPaused") is False and result.get("startPaused") is False,
                    "actual launch identity or initial pause differs")
            require(result["operations"].get("AllowManualInput") is False
                    and result["operations"].get("AllowPauseResume") is False, "actual run allows manual intervention")
            ready = read(evidence / "crash/native/ready.json")
            exited = read(evidence / "crash/native/exit-native.json")
            require(ready.get("pid") == exited.get("pid") == result["processId"]
                    and isinstance(ready.get("identity"), str) and ready["identity"] == exited.get("identity")
                    and exited.get("exitCode") == 0 and exited.get("signal") is None,
                    "owned ready/exit lifetime differs")
            case = validated["parsed"]["cases"][attempt["expected_case"]["id"]]
            disk = validated["actual_prepared_hdd"]
            output.update(verification_status="verified_native_functional", error=None, native=case,
                          metadata=validated["parsed"]["metadata"], expected_case=attempt["expected_case"],
                          integrity=validated["integrity"], prepared_image={"sha256":disk["Sha256"],"bytes":disk["Bytes"],
                          "source_seed_sha256":disk["SeedSha256"],"source_seed_asset_id":disk["DiskAssetId"]},
                          dvd_media=validated.get("dvd_media"), source_scope=validated.get("functional_scope"))
        except (ValueError, KeyError, TypeError, OSError) as error:
            output.update(actual)
            output["error"] = str(error)
        return output

    def configure_schedule(self, schedule, *, artifact_root, clock_review_sha256):
        """Bind a pre-capture A/A schedule and externally trusted clock review.

        This opt-in path cannot promote an old functional cohort. The functional
        collector's false P1 acceptance flag is retained independently of the new
        cohort's explicit relative-timing calibration scope.
        """
        comp = load_owned("storage_perf_compare.py")
        comp.validate_schedule(schedule)
        require(schedule["phase"] == "AA" and self.plan.get("timing_calibration_eligible") is True
                and self.plan.get("timing_scope") == "within-host-relative-AA",
                "native cohort was not declared eligible for relative A/A before capture")
        require(self.plan.get("schedule_sha256") == schedule["sha256"]
                and schedule["spec"]["runner_sha256"] == sha(self.collector_path),
                "predeclared schedule or actual collector runner identity differs")
        spec = schedule["spec"]
        require("artifact_policy" in spec and "counter_policy" in spec,
                "native A/A requires explicit per-case artifacts and source-fixed contract")
        descriptor = spec["counter_policy"]["context_contract"]
        require(self.plan.get("context_contract_sha256") == descriptor["sha256"],
                "native plan changed predeclared clock contract")
        root, cache = Path(artifact_root).resolve(), {}
        contract = comp.read_structural_artifact(descriptor, root, cache, as_json=True)
        require(contract.get("platform") == "deck" and contract.get("counter_hz") == 733333333
                and contract.get("conversion") == "source-fixed-rdtsc",
                "this importer qualifies only the declared Deck source-fixed method")
        review = comp.read_structural_artifact(contract["review_receipt"], root, cache, as_json=True)
        require(contract["review_receipt"]["sha256"] == clock_review_sha256
                and review.get("status") == "reviewed_for_conditional_arithmetic"
                and review.get("contract_facts_sha256") == comp.digest({k:v for k,v in contract.items() if k != "review_receipt"})
                and comp.utc(review["reviewed_utc"]) < comp.utc(schedule["created_utc"]),
                "trusted clock review or pre-capture contract facts differ")
        for role in ("source_binding", "verifier_artifact", "interval_helper"):
            comp.read_structural_artifact(contract[role], root, cache)
        require(contract["verifier_artifact"]["sha256"] == sha(__file__)
                and contract["interval_helper"]["sha256"] == sha(Path(__file__).with_name("storage_counter_intervals.py")),
                "clock contract does not identify the executed importer/helper")
        requirements = contract.get("runtime_requirements")
        require(isinstance(requirements, dict) and requirements.get("method") == "deck-post-END-construction-v1"
                and re.fullmatch(r"[0-9a-f]{64}", requirements.get("libc_sha256", ""))
                and requirements.get("host_cache_mode") in ("cold","warm")
                and isinstance(requirements.get("host_controls"), dict) and requirements["host_controls"],
                "pin actual runtime libc and declared dynamic host policy before capture")
        self.comp, self.schedule, self.artifact_root, self.contract = comp, copy.deepcopy(schedule), root, contract
        self.schedule_jobs = {job["attempt_id"]:job for job in schedule["jobs"]}

    def _scheduled_job(self, attempt, manifest):
        path = self.plan_path.parent / attempt["input_directory"] / "aa-binding.json"
        require(path.resolve().is_relative_to(self.plan_path.parent), "A/A binding input escaped frozen plan")
        wanted_hash = attempt["expected_inputs"].get("aa-binding.json")
        binding = pinned(path, wanted_hash)
        request = pinned(self.plan_path.parent / attempt["request_path"], attempt["request_sha256"])
        declared = [row for row in request["files"] if row.get("Path") == "aa-binding.json"]
        actual = [row for row in manifest["Inputs"] if row.get("Path") == "aa-binding.json"]
        require(len(declared) == len(actual) == 1 and declared[0].get("Sha256") == wanted_hash
                and declared[0].get("Length") == path.stat().st_size
                and actual[0].get("Sha256") == actual[0].get("ExpectedSha256") == wanted_hash
                and actual[0].get("Verified") is True, "actual pre-capture A/A metadata input differs")
        job = self.schedule_jobs.get(binding.get("scheduled_attempt_id"))
        require(job is not None, "A/A metadata names an unscheduled job")
        wanted = {"schema_version":1,"scheduled_attempt_id":job["attempt_id"],
            "schedule_sha256":self.schedule["sha256"],"manifest_sha256":job["manifest_sha256"],
            "case_sha256":self.comp.digest(job["case"]),
            "environment_sha256":self.comp.digest(self.schedule["spec"]["environment"]),
            "runner_sha256":self.schedule["spec"]["runner_sha256"],
            **{key:job[key] for key in ("artifact_set_sha256","case_artifact_sha256","workload_identity_sha256")}}
        require(binding == wanted, "pre-capture A/A binding differs from exact frozen scheduled job")
        case, expected = job["case"], attempt["expected_case"]
        lengths = case.get("operation_bytes", [case.get("bytes_per_operation")] * case["operations"])
        require(all(expected.get(key) == value for key,value in {
            "id":case["id"],"kind":case["kind"],"operations":case["operations"],
            "queue_depth":case.get("queue_depth",1),"cache_policy":case["cache_policy"],
            "expected_operation_bytes":lengths,"assertions_expected":case["assertions"],
            "expected_sha256":case["expected_sha256"]}.items()), "native requests differ from scheduled workload")
        for key in ("request_vectors", "pressure_target_pages"):
            if key in case:
                require(expected.get(key) == case[key], "native scheduled request/pressure mapping differs: " + key)
        if "pressure_pages" in case:
            require(expected.get("pressure_target_pages")==case["pressure_pages"],
                    "native pressure allocation target differs from scheduled workload")
        require(attempt.get("tracing_enabled") is False, "traced timing is diagnostic only")
        return job, request

    def _context(self, evidence, observed, job):
        raw, result, manifest, cleanup = observed
        post = read(evidence / "native-storage-post-context.json")
        binding = post["binding"]
        require(post.get("guard_complete") is True and post.get("error") is None and post.get("stage") == "post"
                and post.get("target_pid") == binding.get("pid") == result["processId"]
                and binding.get("exe_sha256") == job["manifest"]["xemu_sha256"]
                and binding.get("manifest") == manifest and binding.get("launch") == read(evidence / "launch.json")
                and post.get("start_time_at_end") == binding.get("start_time_before")
                and post.get("exe_path_at_end") == binding.get("exe_path"),
                "actual post-END target/lifetime/context binding failed")
        serial = post["serial_end"]
        require(serial.get("strict_successful_END_verified") is True and serial.get("sha256") == sha(evidence / "native-serial.log")
                and serial.get("bytes") == serial.get("offset_at_eof") == (evidence / "native-serial.log").stat().st_size,
                "actual post-END serial EOF/prefix bytes differ")
        clock = post["clock_context"]
        reads, info = clock.get("monotonic_reads_ns"), clock.get("clock", {})
        require(clock.get("schema_version") == 1 and clock.get("errors") == {}
                and info.get("implementation") == "clock_gettime(CLOCK_MONOTONIC)"
                and info.get("monotonic") is True and info.get("adjustable") is False
                and isinstance(reads,list) and len(reads)==2 and all(type(x) is int and x>0 for x in reads) and reads[1]>reads[0]
                and bool(clock.get("target_boot_id")) and clock["target_boot_id"] == clock.get("observer_boot_id")
                and bool(clock.get("target_time_namespace")) and clock["target_time_namespace"] == clock.get("observer_time_namespace")
                and type(clock.get("target_seccomp")) is int and clock["target_seccomp"] == 0
                and clock.get("interposition_variables_present") == {"LD_PRELOAD":False,"LD_AUDIT":False}
                and clock.get("continuous_observation") is False and clock.get("constructor_branch_observed_directly") is False,
                "actual clock route/namespace/interposition observations missing or changed")
        # Recompute the reviewed observer's file/mapping proof, including the
        # narrow Btrfs root-subvolume device distinction. A asserted method label
        # does not establish that proof.
        observer_path=Path(__file__).parent.parent / "tests/xbe/storage-perf/storage-post-context.py"
        require(sha(observer_path)==self.plan["method_source_pins"]["storage-post-context.py"],
                "product clock observer differs from reviewed native method")
        observer_spec=importlib.util.spec_from_file_location("native_import_post_observer",observer_path)
        observer=importlib.util.module_from_spec(observer_spec);observer_spec.loader.exec_module(observer)
        observer.validate_clock_context(clock)
        libc, mappings, vdso = clock.get("libc_file"), clock.get("libc_mappings"), clock.get("vdso_mappings")
        requirements = self.contract["runtime_requirements"]
        require(isinstance(libc,dict) and libc.get("sha256") == requirements["libc_sha256"]
                and type(libc.get("bytes")) is int and libc["bytes"]>0 and mappings
                and all(row in clock.get("maps",[]) and row.get("path")==libc.get("path")
                        and row.get("device")==libc.get("mapped_device") and row.get("inode")==libc.get("mapped_inode") for row in mappings)
                and isinstance(vdso,list) and len(vdso)==1 and vdso[0].get("path")=="[vdso]"
                and vdso[0] in clock.get("maps",[]), "actual mapped libc/vDSO bytes or identity differ")
        controls = {}
        for line in (evidence / "native-host-controls.txt").read_text().splitlines():
            key, separator, value = line.partition("=")
            require(separator and key not in controls, "malformed or duplicate actual host control")
            controls[key]=value.strip()
        require(controls.get("pid") == str(result["processId"]) and controls.get("uid") == str(binding["uid"])
                and all(controls.get(key)==value for key,value in requirements["host_controls"].items()),
                "actual host policy differs from predeclared controls")
        return post

    def emit_job(self, native_attempt_id, *, output_root):
        """Emit actual rows and readable proofs; missing evidence never supplies a value."""
        require(hasattr(self,"schedule"), "configure the frozen schedule before import")
        functional = self.verify_attempt(native_attempt_id)
        attempt, prior = self.declared[native_attempt_id], self.by_id[native_attempt_id]
        evidence, actual = self.evidence_root / prior["run_id"], {}
        row = {**functional,"performance_acceptance_eligible":False,"timing_qualified_for_declared_scope":False}
        try:
            observed = self.collector.observe(evidence, actual)
            job, request = self._scheduled_job(attempt, observed[2])
            row.update(schema_version=1,attempt_id=job["attempt_id"],native_attempt_id=native_attempt_id,
                schedule_sha256=self.schedule["sha256"],machine_id=self.schedule["machine_id"],
                environment_sha256=self.comp.digest(self.schedule["spec"]["environment"]),
                runner_sha256=self.schedule["spec"]["runner_sha256"],
                **{key:job[key] for key in ("manifest_sha256","ordinal","pair_index","arm","case_id","workload_seed","overlay_id")},
                **{key:job[key] for key in self.comp.WORKLOAD_FIELDS if key in job},
                **self.comp.case_artifact_fields(self.schedule["spec"],job["case"]))
            require(functional["verification_status"] == "verified_native_functional", functional.get("error","native functional grading failed"))
            raw,result,manifest,cleanup = observed
            case,entry = job["case"],self.schedule["spec"]["artifact_policy"]["cases"][job["case_id"]]
            row.update(functional["native"])
            row.update(status="ok",error=None,integrity_sha256=functional["integrity"][case["id"]],
                operation_bytes=[int(op["information"]) for op in functional["native"]["operation_records"]],
                started_utc=result["startedUtc"],finished_utc=result["endedUtc"],fresh_process=True,
                fresh_overlay=False,tracing=attempt["tracing_enabled"],expensive_guest_clocks=False,
                cache_preparation={"success":False,"policy_sha256":self.comp.digest(self.schedule["spec"]["cache_policies"][job["cache_policy"]]),"details":"actual runtime cache report not yet qualified"})
            require(self.comp.utc(result["startedUtc"])>=self.comp.utc(self.schedule["created_utc"])
                    and self.comp.utc(result["endedUtc"])>self.comp.utc(result["startedUtc"]),
                    "actual native capture precedes frozen schedule or has invalid duration")
            require(all(attempt["expected_inputs"].get(name)==job["manifest"][field] for name,field in
                        (("xemu","xemu_sha256"),("flash.bin","flash_sha256")))
                    and attempt["expected_inputs"].get("storage-perf.iso") == entry["boot_iso"]["sha256"] == entry["measured_media_iso"]["sha256"]
                    and attempt.get("recorder_xbe_sha256") == entry["recorder_xbe"]["sha256"], "actual ROM/xemu/recorder/boot media role differs")
            prep, disk = entry["preparation"],functional["prepared_image"]
            eeprom=[item for item in manifest["RuntimeFiles"] if item.get("Destination")=="eeprom.bin"]
            require(disk["source_seed_sha256"]==entry["hdd_seed"]["sha256"] and disk["source_seed_asset_id"]==entry["hdd_seed"]["asset_id"]
                    and attempt["seed_request_mode"]==prep["mode"] and len(eeprom)==1 and eeprom[0].get("Sha256")==job["manifest"]["eeprom_sha256"],
                    "actual source/prepared disk or EEPROM differs")
            isolation=request["job"]["runtimeState"]
            require(isolation.get("enabled") is True and isolation.get("isolation",{}).get("requirePrivateGuestState") is True,
                    "actual request lacks independent private guest state")
            row["fresh_overlay"]=True
            post=self._context(evidence,observed,job)
            report=read(evidence / "diagnostics/run-state/report.json")
            # Guest priming (case warm/cold-ish) and host runtime cache isolation
            # are separate controls; the reviewed native collector checks the former.
            mode=self.contract["runtime_requirements"]["host_cache_mode"]
            require(report.get("Status")=="complete" and report.get("ComparisonReady") is True
                    and report.get("DriverNamespaceVerified") is True and report.get("Issues")==[]
                    and report.get("CacheMode")==mode and isolation.get("isolation",{}).get("cacheMode")==mode,
                    "actual cache preparation incomplete/unqualified or policy differs")
            row["cache_preparation"].update(success=True,details="actual completed private runtime/cache report; OS page cache remains predeclared uncontrolled")
            root=Path(output_root).resolve();require(root==self.artifact_root, "emit proofs in the pinned artifact evidence root")
            bindings={key:row[key] for key in ("attempt_id","schedule_sha256","manifest_sha256","environment_sha256","runner_sha256")}
            bindings["case_sha256"]=self.comp.digest(case)
            records={}
            for line in raw.splitlines():
                marker=line.find("STORAGE-PERF-")
                if marker<0:continue
                words=line[marker:].split();tag=words.pop(0)
                if tag in ("STORAGE-PERF-META","STORAGE-PERF-CASE","STORAGE-PERF-END"):
                    require(tag not in records,"duplicate canonical counter record")
                    records[tag]=self.parser._unique_fields(words)
            ledger={"schema_version":1,**bindings,"meta":records["STORAGE-PERF-META"],"summary":records["STORAGE-PERF-CASE"],
                "end":records["STORAGE-PERF-END"],"operations":functional["native"]["operation_records"],
                "timing_sha256":self.comp.digest({key:row[key] for key in ("elapsed_ms","latencies_ms","timing_scope")})}
            directory=root / ("native-import/"+job["attempt_id"]);directory.mkdir(parents=True,exist_ok=True)
            require(not directory.is_symlink() and directory.resolve().is_relative_to(root),"proof directory escaped")
            def store(name, data):
                path=directory/name
                raw=data.read_bytes() if isinstance(data,Path) else (json.dumps(data,sort_keys=True,allow_nan=False)+"\n").encode()
                require(not path.is_symlink(),"proof path is a symlink")
                if path.exists():require(path.read_bytes()==raw,"preserve differing previous proof: "+name)
                else:
                    with path.open("xb") as destination:destination.write(raw)
                return {"path":path.relative_to(root).as_posix(),"sha256":sha(path),"bytes":path.stat().st_size}
            preparation={"schema_version":1,**bindings,"native_run_id":prior["run_id"],"actual_prepared_image":disk,
                "eeprom":eeprom[0],"request_sha256":attempt["request_sha256"],"input_manifest_sha256":sha(evidence/"input-manifest.json"),
                "preparation_mode":prep["mode"]}
            evidence_files={"request":store("request.json",self.plan_path.parent/attempt["request_path"]),
                **{role:store(role+".json",evidence/name) for role,name in {
                    "result":"result.json","input_manifest":"input-manifest.json","guard":"native-storage-post-context.json"}.items()},
                "host_context":store("host-context.json",{"post":post,"host_controls":(evidence/"native-host-controls.txt").read_text(),"runtime_report":report}),
                "preparation_receipt":store("preparation.json",preparation)}
            row["artifact_bindings"]={"verified_by_native_importer":True,"case_artifact_sha256":job["case_artifact_sha256"],
                **{role+"_sha256":evidence_files[role]["sha256"] for role in ("request","input_manifest","preparation_receipt")},
                **{role+"_sha256":entry[role]["sha256"] for role in ("recorder_xbe","boot_iso","measured_media_iso")},
                "source_seed_sha256":disk["source_seed_sha256"],"source_seed_asset_id":disk["source_seed_asset_id"],
                "preparation_mode":prep["mode"],"prepared_image":{key:disk[key] for key in ("sha256","bytes")},
                "eeprom_source_sha256":eeprom[0]["Sha256"]}
            self.comp.validate_case_artifacts(self.schedule,job,row,root,{})
            if case["kind"]=="write-flush":
                row["durability_policy_sha256"]=self.comp.digest(self.schedule["spec"]["durability_policy"])
                ledger.update(fixture_sha256=job["manifest"]["fixture_sha256"],parser_sha256=self.plan["parser_sha256"],
                    durability_policy_sha256=row["durability_policy_sha256"],
                    timing_contract_sha256=self.schedule["spec"]["durability_policy"]["timing_contract"]["sha256"],
                    **{key:job[key] for key in self.comp.WORKLOAD_FIELDS if key in job})
            row["counter_provenance"]=store("counter.json",ledger)
            if case["kind"]=="write-flush":row["api_timing_provenance"]=row["counter_provenance"]
            proof={"schema_version":1,"verification_status":"verified_by_pinned_importer",**bindings,
                "native_run_id":prior["run_id"],"context_contract_sha256":self.schedule["spec"]["counter_policy"]["context_contract"]["sha256"],
                "verifier_sha256":sha(__file__),"raw_counter_sha256":row["counter_provenance"]["sha256"],"native_evidence":evidence_files}
            row["clock_provenance"]=store("clock.json",proof)
            intervals,problem=self.comp.validate_counter_capture(self.schedule,job,row,root,{})
            require(problem is None,problem or "counter evidence failed")
            if case["kind"]=="write-flush":
                problem=self.comp.validate_public_write(self.schedule,job,row,root,{})
                require(problem is None,problem or "public API timing evidence failed")
            row.update(timing_qualified_for_declared_scope=True,eligibility_reasons=[],clock_scope="conditional within-host relative conversion; sampled post-END context with construction assumptions")
        except (ValueError,KeyError,TypeError,OSError,OverflowError) as error:
            row.pop("clock_provenance",None)
            row["eligibility_reasons"]=[str(error)]
        return row


def verify_windows_context(context_path, receipt_path, *, receipt_sha256):
    """Validate retained V4 observation semantics; do not promote its diagnostic scope."""
    receipt = pinned(receipt_path, receipt_sha256)
    require(receipt.get("status") == "BOUNDED_NATIVE_CONTEXT_COLLECTION_QUALIFIED", "unreviewed Windows context")
    descriptors = [row for row in receipt["raw_portable_artifacts"] if row["path"].endswith("context.json")]
    require(len(descriptors) == 1 and sha(context_path) == descriptors[0]["sha256"]
            and Path(context_path).stat().st_size == descriptors[0]["bytes"], "Windows raw context bytes differ")
    context = read(context_path)
    require(context.get("status") == "complete_context_observations" and context.get("error") is None,
            "Windows context observation failed")
    require(receipt["actual_clock_samples"] == {"initial":context["initial_clock"],"final":context["final_clock"]},
            "Windows actual clock samples differ from retained receipt")
    clocks = [context["initial_clock"],context["final_clock"]]
    frequencies = []
    for clock in clocks:
        require(all(clock.get(key) is True for key in ("qpf_success","qpc_before_success","qpc_after_success")),
                "actual Windows QPF/QPC call failed")
        frequency = int(clock["qpf_frequency_dec"])
        require(1 <= frequency <= 4294967295 and 0 < int(clock["qpc_before_dec"]) <= int(clock["qpc_after_dec"]),
                "actual Windows counter/frequency outside reviewed domain")
        frequencies.append(frequency)
    require(frequencies[0] == frequencies[1], "actual Windows QPF changed during lifetime")
    binding = context["binding"]
    initial, final = binding["processes"]["guest"], context["final_process"]
    require(initial == final, "actual Windows PID/start/executable/argv/owner lifetime changed")
    desktop = context["desktop"]
    require(desktop.get("user_interactive") is True and desktop.get("session",0) > 0
            and str(desktop.get("user_name","")).lower() == "codex"
            and initial["session"] == desktop["session"] and initial["owner_sid"] == desktop["owner_sid"],
            "actual Windows USER desktop identity differs")
    state = context["initial_managed_status"]["response"]
    require(state.get("status") == "running" and state.get("running") is True
            and ("singlestep" not in state or state["singlestep"] is False), "sampled Windows VM state is not ordinary running")
    require(context.get("performance_acceptance_eligible") is False
            and context.get("provider_precision_proved") is False and context.get("normative_clock_qualified") is False,
            "retained diagnostic scope cannot be promoted")
    report = binding["report"]
    return {"qpf_hz":frequencies[0],"count_quantum_ns":1000000000 / frequencies[0],
            "single_step":state.get("singlestep"),"source_xemu_sha256":receipt["actual_pinned_inputs"]["xemu.exe"],
            "driver_cache_verified":report.get("DriverNamespaceVerified"),
            "performance_eligible":False,"provider_precision_proved":False,
            "scope":"retained actual sampled Windows QPF/owned desktop context; no storage cohort qualification"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("collector","collector-sha256","review","review-sha256","evidence-root","ledger","ledger-sha256","output"):
        parser.add_argument("--"+name,required=True)
    parser.add_argument("--attempt")
    parser.add_argument("--schedule",type=Path)
    parser.add_argument("--schedule-sha256",help="trusted canonical sealed schedule identity")
    parser.add_argument("--artifact-root",type=Path)
    parser.add_argument("--clock-review-sha256",help="externally trusted pre-capture clock contract review")
    args = parser.parse_args()
    importer = NativeImporter(collector_path=args.collector,collector_sha256=args.collector_sha256,
        review_path=args.review,review_sha256=args.review_sha256,evidence_root=args.evidence_root,
        ledger_path=args.ledger,ledger_sha256=args.ledger_sha256)
    attempts = [args.attempt] if args.attempt else list(importer.by_id)
    if args.schedule:
        require(args.schedule_sha256 and args.artifact_root and args.clock_review_sha256,"supply schedule, artifact root and trusted clock review pins")
        schedule=read(args.schedule)
        require(schedule.get("sha256")==args.schedule_sha256,"trusted sealed schedule identity differs")
        importer.configure_schedule(schedule,artifact_root=args.artifact_root,clock_review_sha256=args.clock_review_sha256)
        records=[importer.emit_job(attempt,output_root=args.artifact_root) for attempt in attempts]
    else:
        require(not any((args.schedule_sha256,args.artifact_root,args.clock_review_sha256)),"schedule options require --schedule")
        records=[importer.verify_attempt(attempt) for attempt in attempts]
    with Path(args.output).open("x",encoding="utf-8") as destination:
        for record in records: destination.write(json.dumps(record,sort_keys=True,allow_nan=False)+"\n")
    field="timing_qualified_for_declared_scope" if args.schedule else "verification_status"
    wanted=True if args.schedule else "verified_native_functional"
    return 0 if all(row[field]==wanted for row in records) else 2


if __name__ == "__main__":
    raise SystemExit(main())
