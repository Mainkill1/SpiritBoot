#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Run a finalized release64 title gate through the HTTP runner, unattended."""
from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path
from typing import Any

from finalize_release_jobs import _stage_package, build_title_job, sha256_file
from rclass_gate import ERROR_PATTERNS
from release_title_analyzer import (score_doa_create, score_doa_reload,
                                    score_halo2, score_halo2_pair,
                                    score_pgr2_create, score_pgr2_reload,
                                    require_ocr_dependencies)


def require_idle(api: Any) -> None:
    status = api.json("/api/v1/status")
    queue = status.get("Queue", {})
    if status.get("CurrentJob") is not None or queue.get("Pending") or queue.get("Testing"):
        raise RuntimeError("runner is busy: " + json.dumps(status))


def register_firmware(api: Any, asset: dict[str, str], flash: Path) -> None:
    route = "/api/v1/disk-assets/" + urllib.parse.quote(asset["id"], safe="")
    try:
        present = api.json(route)
    except Exception as error:
        if getattr(error, "status", None) != 404:
            raise
        present = None
    if present is not None:
        if present.get("sha256") != asset["sha256"] or not present.get("ready"):
            raise RuntimeError("firmware asset id exists with different or incomplete content")
        return
    api.json("/api/v1/disk-assets", "POST", {
        "id": asset["id"], "kind": "readonly-input",
        "length": flash.stat().st_size, "sha256": asset["sha256"],
        "description": "Pinned SpiritBoot release64 title-gate candidate",
    })
    api.upload_path(route + "/content", flash, flash.stat().st_size, asset["sha256"])


def run_one(work: Any, package: Path, evidence: Path) -> tuple[dict[str, Any], Path]:
    job = json.loads((package / "job.json").read_text())
    job_id = job["id"]
    work.submit(package, job_id, None, 8 * 1024 * 1024)
    while True:
        result = work.wait(job_id, 40)
        if result.get("state") == "tested":
            break
        if result.get("blocker") or result.get("state") in (
                "held", "blocked", "cancelled", "unavailable", "draft"):
            raise RuntimeError("runner rejected " + job_id + ": " + json.dumps(result))
    outcome = result.get("outcome") or {}
    if outcome.get("execution") != "completed" or outcome.get("correctness") != "passed":
        raise RuntimeError("title job failed " + job_id + ": " + json.dumps(result))
    receipt = work.collect(job_id, evidence, [], True)
    run_root = evidence / receipt["runId"]
    return result, run_root


def common_score(root: Path) -> dict[str, Any]:
    result = json.loads((root / "result.json").read_text())
    log = (root / "qemu.log").read_text(errors="replace") if (root / "qemu.log").exists() else ""
    errors = ERROR_PATTERNS.findall(log)
    activity = result.get("operatorActivity") or {}
    process = (result.get("status") == "completed" and result.get("exitCode") == 0
               and not (result.get("crash") or {}).get("Crashed", False))
    job = json.loads((root / "job.json").read_text()) if (root / "job.json").is_file() else {}
    planned_diagnostics = sum(row.get("type", row.get("Type")) == "diagnostic"
                              for row in job.get("plan", job.get("Plan", [])))
    completed_diagnostics = result.get("diagnostics") or []
    diagnostic_count = int(activity.get("Diagnostics", 0) or 0)
    diagnostics_are_planned = (
        diagnostic_count == planned_diagnostics == len(completed_diagnostics)
        and all(row.get("Status", row.get("status")) == "completed"
                for row in completed_diagnostics)
    )
    non_diagnostic_activity = any(int(activity.get(name, 0) or 0) != 0 for name in (
        "ManualInputs", "Pauses", "Screenshots", "PreviewCaptures",
        "BulkTransfers", "HostStateChanges"))
    unattended = (not non_diagnostic_activity and
                  (not activity.get("Intervened", False) or diagnostics_are_planned))
    workload = result.get("workload") or {}
    correctness = workload.get("Correctness", result.get("correctnessStatus")) == "passed"
    complete = workload.get("Evidence", result.get("evidenceStatus")) == "complete"
    return {
        "process": process,
        "runner_correctness": correctness,
        "runner_evidence": complete,
        "unattended": unattended,
        "corruption_or_io_log_matches": errors,
        "pass": process and correctness and complete and unattended and not errors,
    }


def _qmp_stats(root: Path, diagnostic_id: str) -> dict[str, dict[str, Any]]:
    matches = list(root.glob(f"diagnostics/*-{diagnostic_id}/qmp-result.json"))
    if len(matches) != 1:
        return {}
    value = json.loads(matches[0].read_text())
    return {str(row.get("device")): row.get("stats", {}) for row in value}


def qmp_write_score(root: Path, before_id: str, after_id: str) -> dict[str, Any]:
    before = _qmp_stats(root, before_id)
    after = _qmp_stats(root, after_id)
    writes = bytes_written = 0
    for device in set(before) & set(after):
        writes += int(after[device].get("wr_operations", 0) or 0) - int(before[device].get("wr_operations", 0) or 0)
        bytes_written += int(after[device].get("wr_bytes", 0) or 0) - int(before[device].get("wr_bytes", 0) or 0)
    return {"write_operations": writes, "write_bytes": bytes_written, "pass": writes > 0 and bytes_written > 0}


def doa_write_score(root: Path) -> dict[str, Any]:
    return qmp_write_score(root, "doa-save-write-before", "doa-save-write-after")


def import_retained_hdd(api: Any, create_root: Path, candidate_id: str,
                        purpose: str) -> dict[str, str]:
    state = json.loads((create_root / "runtime-state.json").read_text())
    runtime = state.get("directory")
    if not runtime:
        raise RuntimeError(purpose + " create phase did not retain a runtime directory")
    slug = purpose.lower().replace(" ", "-")
    asset_id = f"sb-{candidate_id}-{slug}-{create_root.name[:17].lower()}"
    route = "/api/v1/disk-assets/" + urllib.parse.quote(asset_id, safe="") + "/import-local"
    api.json(route, "POST", {
        "path": runtime.rstrip("\\/") + "\\hdd.qcow2",
        "description": "Exact retained " + {
            "doa-save": "DOA save",
            "pgr2-profile": "PGR2 profile",
            "cold-storage": "cold-storage XBE",
        }.get(purpose, purpose.replace("-", " ")) + " create-phase HDD for cold reload gate",
    })
    deadline = time.monotonic() + 300
    while time.monotonic() < deadline:
        status = api.json(route)
        if status.get("state") in ("failed", "cancelled") or status.get("error"):
            raise RuntimeError(purpose + " HDD import failed: " + json.dumps(status))
        try:
            asset = api.json("/api/v1/disk-assets/" + urllib.parse.quote(asset_id, safe=""))
        except Exception as error:
            if getattr(error, "status", None) != 404:
                raise
            asset = None
        if asset and asset.get("ready"):
            return {"id": asset_id, "sha256": asset["sha256"],
                    "retention": "deleteAfterEvidence"}
        time.sleep(1)
    raise TimeoutError(purpose + " HDD import did not finish within 300 seconds")


def execute(finalized: Path, evidence: Path, runner_url: str,
            runner_client: Path, analyzer_dir: Path) -> dict[str, Any]:
    sys.path.insert(0, str(runner_client.resolve()))
    from runner_transport import RunnerApi
    from runner_workflows import Workflows

    report = json.loads((finalized / "finalization.json").read_text())
    contract = json.loads((finalized / "contract.resolved.json").read_text())
    flash = finalized / "packages" / "forza" / "flash.bin"
    if sha256_file(flash) != report["firmware_sha256"]:
        raise RuntimeError("finalized firmware no longer matches finalization.json")
    try:
        require_ocr_dependencies()
    except (ImportError, RuntimeError) as error:
        raise RuntimeError("title analyzer dependencies are unavailable: " + str(error)) from error
    api = RunnerApi(runner_url, timeout=120)
    require_idle(api)
    register_firmware(api, contract["common"]["firmware_asset"], flash)
    work = Workflows(api, operation_seconds=1200, progress=True)
    evidence.mkdir(parents=True, exist_ok=False)
    results: dict[str, Any] = {}

    order = ("pgr2-create", "forza", "halo2-a", "halo2-b", "doa-create")
    roots: dict[str, Path] = {}
    for title in order:
        require_idle(api)
        result, root = run_one(work, finalized / "packages" / title, evidence / title)
        roots[title] = root
        score = common_score(root)
        if title == "pgr2-create":
            score["title"] = score_pgr2_create(root)
            score["hdd_writes"] = qmp_write_score(
                root, "pgr2-profile-write-before", "pgr2-profile-write-after")
            score["pass"] = (score["pass"] and score["title"]["pass"]
                             and score["hdd_writes"]["pass"])
        elif title == "forza":
            completed = subprocess.run(
                [sys.executable, str(analyzer_dir / "analyze_evidence.py"), str(root)],
                check=False, text=True, capture_output=True)
            (root / "forza-analyzer.stdout.log").write_text(completed.stdout)
            (root / "forza-analyzer.stderr.log").write_text(completed.stderr)
            score["forza_qualification_exit"] = completed.returncode
            score["pass"] = score["pass"] and completed.returncode == 0
        elif title.startswith("halo2-"):
            score["title"] = score_halo2(root)
            score["pass"] = score["pass"] and score["title"]["pass"]
        elif title == "doa-create":
            score["title"] = score_doa_create(root)
            score["hdd_writes"] = doa_write_score(root)
            score["pass"] = (score["pass"] and score["title"]["pass"]
                             and score["hdd_writes"]["pass"])
        results[title] = {"run_id": root.name, "outcome": result.get("outcome"), "score": score}
        if not score["pass"]:
            raise RuntimeError(title + " objective gate failed: " + json.dumps(score))

    pgr2_phase_two = import_retained_hdd(
        api, roots["pgr2-create"], report["candidate_id"], "pgr2-profile")
    pgr2_contract = copy.deepcopy(contract)
    pgr2_contract["titles"]["pgr2"]["phase_two_hdd"] = pgr2_phase_two
    base_package = finalized / "packages" / "forza"
    base_job = json.loads((base_package / "job.json").read_text())
    pgr2_job, pgr2_spec = build_title_job(
        base_job, pgr2_contract, "pgr2-reload", report["candidate_id"])
    pgr2_package = finalized / "packages" / "pgr2-reload"
    _stage_package(base_package, pgr2_package, flash, pgr2_job, pgr2_spec)
    require_idle(api)
    result, root = run_one(work, pgr2_package, evidence / "pgr2-reload")
    score = common_score(root)
    score["title"] = score_pgr2_reload(root)
    score["pass"] = score["pass"] and score["title"]["pass"]
    results["pgr2-reload"] = {
        "run_id": root.name, "outcome": result.get("outcome"), "score": score}
    if not score["pass"]:
        raise RuntimeError("pgr2-reload objective gate failed: " + json.dumps(score))

    phase_two = import_retained_hdd(
        api, roots["doa-create"], report["candidate_id"], "doa-save")
    reload_contract = copy.deepcopy(contract)
    reload_contract["titles"]["doa"]["phase_two_hdd"] = phase_two
    reload_job, reload_spec = build_title_job(
        base_job, reload_contract, "doa-reload", report["candidate_id"])
    reload_package = finalized / "packages" / "doa-reload"
    _stage_package(base_package, reload_package, flash, reload_job, reload_spec)
    require_idle(api)
    result, root = run_one(work, reload_package, evidence / "doa-reload")
    score = common_score(root)
    score["title"] = score_doa_reload(root)
    score["pass"] = score["pass"] and score["title"]["pass"]
    results["doa-reload"] = {"run_id": root.name, "outcome": result.get("outcome"), "score": score}
    if not score["pass"]:
        raise RuntimeError("doa-reload objective gate failed: " + json.dumps(score))

    halo_ids = [results[name]["run_id"] for name in ("halo2-a", "halo2-b")]
    halo_pair = score_halo2_pair(results["halo2-a"]["score"]["title"],
                                 results["halo2-b"]["score"]["title"])
    if not halo_pair["pass"]:
        raise RuntimeError("Halo 2 repeated-launch stability failed: " + json.dumps(halo_pair))
    summary = {"schema_version": 1, "pass": all(x["score"]["pass"] for x in results.values()),
               "candidate_id": report["candidate_id"], "firmware_sha256": report["firmware_sha256"],
               "halo2_independent_run_ids": halo_ids, "halo2_pair": halo_pair,
               "results": results}
    (evidence / "qualification-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--finalized", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--runner-url", required=True)
    parser.add_argument("--runner-client", type=Path, required=True)
    parser.add_argument("--analyzer-dir", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(execute(args.finalized, args.evidence, args.runner_url,
                             args.runner_client, args.analyzer_dir), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
