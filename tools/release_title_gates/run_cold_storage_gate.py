#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run the product-owned cold-storage XBE across two fresh xemu processes."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from finalize_release_jobs import _replace_firmware, _stage_package, sha256_file
from run_release_gates import (common_score, import_retained_hdd,
                               register_firmware, require_idle, run_one)


def _artifact_check(name: str, contains: str) -> dict[str, Any]:
    return {
        "name": name, "scope": "result", "path": "native-serial.log",
        "mustExist": True, "minimumBytes": 1,
        "minimumNonBlackPixelRatio": None, "nonBlackPixelThreshold": 0,
        "imageRegion": None, "expectedSha256": None,
        "containsText": contains, "equalsText": None,
    }


def build_cold_job(base_job: dict[str, Any], candidate_id: str, phase: str,
                   firmware: dict[str, str], disc: dict[str, str],
                   hdd: dict[str, str]) -> dict[str, Any]:
    if phase not in ("A", "B"):
        raise ValueError("cold-storage phase must be A or B")
    old_flash = next(row["expectedSha256"] for row in base_job["inputs"]
                     if row["path"] == "flash.bin")
    job = _replace_firmware(copy.deepcopy(base_job), old_flash, firmware["sha256"])
    suffix = phase.lower()
    job["id"] = f"sb-{candidate_id}-cold-storage-{suffix}-release64"
    job["timeoutSeconds"] = 180
    job["tags"] = ["SPIRITBOOT", "RELEASE64", "FRESH-PROCESS",
                   "PRIVATE-HDD-COPY", "COLD-APP-CACHE", "COLD-STORAGE",
                   "PHASE-" + phase]
    result_line = f"COLD_STORAGE_RESULT phase={phase} status=PASS"
    job["plan"] = [{
        "type": "wait_for_artifact", "delayMs": 0, "button": None,
        "durationMs": 100, "name": None, "diagnosticId": None,
        "condition": {
            "name": "", "scope": "result", "path": "native-serial.log",
            "mustExist": True, "minimumBytes": 1,
            "nonBlackPixelThreshold": 0, "containsText": result_line,
        },
        "timeoutMs": 150_000, "pollIntervalMs": 250,
    }]
    job["diagnostics"] = []
    runtime = job["runtimeState"]
    runtime["keepOnSuccess"] = phase == "A"
    runtime["keepOnFailure"] = True
    runtime["diskAssets"] = [{
        "assetId": hdd["id"], "expectedSha256": hdd["sha256"],
        "destination": "hdd.qcow2",
        "retention": "keep" if phase == "A" else "deleteAfterEvidence",
    }]
    for row in runtime["isolation"]["readOnlyAssets"]:
        if row["field"] == "flashrom_path":
            row["assetId"], row["expectedSha256"] = firmware["id"], firmware["sha256"]
        elif row["field"] == "dvd_path":
            row["assetId"], row["expectedSha256"] = disc["id"], disc["sha256"]
    checks = [_artifact_check("cold-storage-result", result_line)]
    if phase == "B":
        checks.append(_artifact_check("cold-storage-pending", "pending_reads="))
    job["workload"] = {
        "correctnessChecks": checks,
        "evidenceRequirements": [_artifact_check("qemu-log", "") | {
            "path": "qemu.log", "minimumBytes": 0, "containsText": None}],
        "reportedMetrics": [], "minimumMetricSamples": 0,
        "requirePlanCompletion": True,
    }
    job["experiment"] = {
        "id": f"spiritboot-cold-storage-{candidate_id}",
        "variant": "phase-" + phase.lower(), "reference": None,
        "variedFactors": ["cold-process"],
        "controlledFactors": ["release64-firmware-" + firmware["sha256"],
                              "cold-storage-xiso-" + disc["sha256"],
                              "same-eeprom", "64MiB"],
        "requireCorrectnessPass": True, "requireCompleteEvidence": True,
        "allowOperatorIntervention": False, "allowDiagnostics": False,
    }
    job["operations"]["allowDiagnostics"] = False
    job["operations"]["diagnosticsAllowed"] = False
    return job


def register_readonly(api: Any, asset: dict[str, str], path: Path,
                      description: str) -> None:
    route = "/api/v1/disk-assets/" + urllib.parse.quote(asset["id"], safe="")
    try:
        present = api.json(route)
    except Exception as error:
        if getattr(error, "status", None) != 404:
            raise
        present = None
    if present is not None:
        if present.get("sha256") != asset["sha256"] or not present.get("ready"):
            raise RuntimeError("asset id exists with different or incomplete content")
        return
    api.json("/api/v1/disk-assets", "POST", {
        "id": asset["id"], "kind": "readonly-input", "length": path.stat().st_size,
        "sha256": asset["sha256"], "description": description,
    })
    api.upload_path(route + "/content", path, path.stat().st_size, asset["sha256"])


def execute(finalized: Path, xiso: Path, grader: Path, evidence: Path,
            runner_url: str, runner_client: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runner_client.resolve()))
    from runner_transport import RunnerApi
    from runner_workflows import Workflows

    report = json.loads((finalized / "finalization.json").read_text())
    contract = json.loads((finalized / "contract.resolved.json").read_text())
    base_package = finalized / "packages" / "pgr2-create"
    flash = base_package / "flash.bin"
    if sha256_file(flash) != report["firmware_sha256"]:
        raise RuntimeError("finalized firmware no longer matches finalization.json")
    disc_hash = sha256_file(xiso)
    disc = {"id": "cold-storage-persistence-" + disc_hash[:12], "sha256": disc_hash}
    firmware = contract["common"]["firmware_asset"]
    seed = contract["titles"]["pgr2"]["hdd_seed"]
    api = RunnerApi(runner_url, timeout=120)
    require_idle(api)
    register_firmware(api, firmware, flash)
    register_readonly(api, disc, xiso, "Product-owned cold-storage persistence XISO")
    work = Workflows(api, operation_seconds=1200, progress=True)
    evidence.mkdir(parents=True, exist_ok=False)
    base_job = json.loads((base_package / "job.json").read_text())

    phase_a_job = build_cold_job(base_job, report["candidate_id"], "A",
                                 firmware, disc, seed)
    phase_a_package = finalized / "packages" / "cold-storage-a"
    _stage_package(base_package, phase_a_package, flash, phase_a_job,
                   {"phase": "A", "disc": disc, "hdd": seed})
    result_a, root_a = run_one(work, phase_a_package, evidence / "phase-a")
    score_a = common_score(root_a)
    if not score_a["pass"]:
        raise RuntimeError("cold-storage phase A failed: " + json.dumps(score_a))

    retained = import_retained_hdd(api, root_a, report["candidate_id"],
                                   "cold-storage")
    phase_b_job = build_cold_job(base_job, report["candidate_id"], "B",
                                 firmware, disc, retained)
    phase_b_package = finalized / "packages" / "cold-storage-b"
    _stage_package(base_package, phase_b_package, flash, phase_b_job,
                   {"phase": "B", "disc": disc, "hdd": retained})
    require_idle(api)
    result_b, root_b = run_one(work, phase_b_package, evidence / "phase-b")
    score_b = common_score(root_b)
    completed = subprocess.run(
        [sys.executable, str(grader), str(root_a / "native-serial.log"),
         str(root_b / "native-serial.log")], text=True, capture_output=True)
    summary = {
        "schema_version": 1,
        "pass": score_a["pass"] and score_b["pass"] and completed.returncode == 0,
        "candidate_id": report["candidate_id"],
        "firmware_sha256": report["firmware_sha256"], "xiso": disc,
        "phase_a": {"run_id": root_a.name, "outcome": result_a.get("outcome"),
                    "score": score_a},
        "phase_b": {"run_id": root_b.name, "outcome": result_b.get("outcome"),
                    "score": score_b},
        "grader_exit": completed.returncode, "grader_stdout": completed.stdout,
        "grader_stderr": completed.stderr,
    }
    (evidence / "cold-storage-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    if not summary["pass"]:
        raise RuntimeError("cold-storage gate failed: " + json.dumps(summary))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalized", type=Path, required=True)
    parser.add_argument("--xiso", type=Path, required=True)
    parser.add_argument("--grader", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runner-url", required=True)
    parser.add_argument("--runner-client", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(execute(args.finalized, args.xiso, args.grader, args.evidence,
                             args.runner_url, args.runner_client), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
