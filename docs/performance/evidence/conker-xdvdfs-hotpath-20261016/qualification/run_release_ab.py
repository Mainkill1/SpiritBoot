#!/usr/bin/env python3
"""Run matched release64 Conker profiles with XDVDFS forwarding off and on."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
COUNTER_SCRIPT = HERE.parent / "diagnostic-counter/run_windows_counter_trace.py"
spec = importlib.util.spec_from_file_location("counter_run", COUNTER_SCRIPT)
counter_run = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(counter_run)


ARMS = (
    (
        "off-a",
        ROOT / ".scratch/xdvdfs-forward-release64/flash.bin",
        "spiritboot-conker-xdvdfs-release64-off-a-20261016",
    ),
    (
        "on-a",
        ROOT / ".scratch/xdvdfs-forward-forced-release64/flash.bin",
        "spiritboot-conker-xdvdfs-release64-on-a-20261016",
    ),
)


def run_arm(label: str, bios: Path, job_id: str) -> dict[str, object]:
    counter_run.FILES["flash.bin"] = bios
    counter_run.JOB_ID = job_id
    request = counter_run.make_request()
    job = request["job"]
    job["id"] = job_id
    job["diagnostics"] = []
    job["plan"] = [
        job["plan"][0],
        {"type": "wait", "delayMs": 1000},
        {"type": "quit"},
    ]
    job["environment"]["SB_BIOS_ARM"] = f"xdvdfs-{label}"
    job["tags"] = ["spiritboot-real-game-profile", "conker", "release64", f"xdvdfs-{label}"]
    job["experiment"] = {
        "id": "conker-xdvdfs-forwarding-release-ab-20261016",
        "variant": label,
        "variedFactors": ["xdvdfs-forwarding"],
        "controlledFactors": ["product-source", "game", "hdd", "host", "sample-window"],
        "requireCorrectnessPass": False,
        "requireCompleteEvidence": True,
        "allowOperatorIntervention": False,
        "allowDiagnostics": False,
    }
    job["operations"]["allowDiagnostics"] = False

    output = HERE / label
    output.mkdir(parents=True, exist_ok=True)
    (output / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    api = counter_run.RunnerApi(counter_run.RUNNER, timeout=120)
    workflows = counter_run.Workflows(api, operation_seconds=900, progress=False)
    state = api.json("/api/v1/status")
    if state.get("CurrentJob") or state["Queue"]["Pending"] or state["Queue"]["Testing"]:
        raise RuntimeError(f"runner is not idle: {state}")
    api.json("/api/v1/jobs", "POST", request)
    api.json(counter_run.job_url(job_id) + "/reuse", "POST", {"sourceJobId": counter_run.REUSE_JOB})
    workflows.operation(job_id)
    available = {row["path"]: row for row in api.json(counter_run.job_url(job_id) + "/files")}
    for row in request["files"]:
        status = available.get(row["Path"], {}).get("status", {})
        if not status.get("complete") or available[row["Path"]].get("sha256") != row["Sha256"]:
            api.upload_path(counter_run.job_url(job_id) + "/files/" + row["Path"],
                            counter_run.FILES[row["Path"]], row["Length"], row["Sha256"])
    workflows.submit_draft(job_id)
    while True:
        state = workflows.wait(job_id, 45)
        print(json.dumps({"arm": label, "state": state.get("state"), "runId": state.get("runId")}), flush=True)
        if state.get("state") == "tested":
            break
        if state.get("blocker") or state.get("state") in {"draft", "held", "blocked", "unavailable", "cancelled"}:
            raise RuntimeError(state)
    receipt = workflows.collect(job_id, output / "evidence", [], True)
    (output / "collection.json").write_text(json.dumps(receipt, indent=2) + "\n")
    results = list((output / "evidence").glob("*/result.json"))
    performances = list((output / "evidence").glob("*/performance.json"))
    if len(results) != 1 or len(performances) != 1:
        raise RuntimeError("expected one result and one performance artifact")
    result = json.loads(results[0].read_text())
    if result.get("status") != "completed" or result.get("evidenceStatus") != "complete":
        raise RuntimeError(result)
    performance = json.loads(performances[0].read_text())
    return {"label": label, "biosSha256": counter_run.sha256(bios), "result": result, "performance": performance}


def main() -> int:
    rows = [run_arm(*arm) for arm in ARMS]
    (HERE / "ab-results.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps([{k: row[k] for k in ("label", "biosSha256", "performance")} for row in rows], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
