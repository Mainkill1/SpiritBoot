#!/usr/bin/env python3
"""Execute the PR #248 Windows 50x ABBA campaign through Xemu-Test-Runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runner", default="http://10.0.7.1:9368")
    parser.add_argument(
        "--runner-tools",
        type=Path,
        required=True,
        help="Xemu-Test-Runner scripts directory at commit 0ba533ed89c8bb3cf530c4bfff8dbb190b3f08be",
    )
    parser.add_argument("--candidate-bios", type=Path, required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--campaign", type=Path, default=PACKAGE / "campaign.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--job-suffix",
        default="",
        help="Optional suffix for rerunning the frozen jobs on a runner where the original IDs exist",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sys.path.insert(0, str(args.runner_tools.resolve()))
    from runner_transport import RunnerApi, job_url  # type: ignore
    from runner_workflows import Workflows  # type: ignore

    campaign = json.loads(args.campaign.read_text(encoding="utf-8"))
    reference = PACKAGE / campaign["referenceResults"]
    if sha256(reference) != campaign["referenceResultsSha256"]:
        raise RuntimeError("reference-results hash does not match campaign.json")
    if sha256(args.candidate_bios) != campaign["candidateBios"]["sha256"]:
        raise RuntimeError("candidate BIOS hash does not match campaign.json")
    fixture_hash = "10ca07f227ae4e1d03510fcc1d3237304ff4291741d4c552ab33991e71de1738"
    if sha256(args.fixture) != fixture_hash:
        raise RuntimeError("XISO fixture hash does not match the frozen campaign")

    api = RunnerApi(args.runner, timeout=60)
    workflows = Workflows(api, operation_seconds=2400, progress=False)
    api.require("payloadReuse", "artifactPages", "runStateLedger", "diskAssets")
    status = api.json("/api/v1/status")
    queue = status["Queue"]
    if status.get("CurrentJob") or queue["Pending"] or queue["Testing"]:
        raise RuntimeError("runner is not idle")
    if status["Workstation"].get("RenderingRisk"):
        raise RuntimeError("runner reports a rendering-risk workstation state")

    output = args.output.resolve()
    results = []
    suffix = args.job_suffix.strip()
    if suffix and not suffix.startswith("-"):
        suffix = "-" + suffix

    for row in campaign["runs"]:
        request_path = PACKAGE / row["request"]
        if sha256(request_path) != row["requestSha256"]:
            raise RuntimeError(f"request hash mismatch: {request_path}")
        request = json.loads(request_path.read_text(encoding="utf-8"))
        job_id = request["id"] + suffix
        request["id"] = job_id
        request["job"]["id"] = job_id
        run_dir = output / "runs" / f"{row['index']:02d}-{row['arm']}-{row['label'].lower()}"
        run_dir.mkdir(parents=True, exist_ok=True)

        write_json(run_dir / "create-receipt.json", api.json("/api/v1/jobs", "POST", request))
        current = workflows.status(job_id)
        if current["state"] == "busy":
            write_json(run_dir / "create-operation.json", workflows.operation(job_id))
            current = workflows.status(job_id)
        if current["state"] != "draft":
            raise RuntimeError(current)

        write_json(
            run_dir / "reuse-started.json",
            api.json(job_url(job_id) + "/reuse", "POST", {"sourceJobId": row["reuseJob"]}),
        )
        write_json(run_dir / "reuse-operation.json", workflows.operation(job_id))

        uploads = {
            "fixture.iso": args.fixture,
            "reference-results.json": reference,
        }
        if row["arm"] == "candidate":
            uploads["flash.bin"] = args.candidate_bios
        for name, path in uploads.items():
            expected = next(item for item in request["files"] if item["Path"] == name)
            actual = (path.stat().st_size, sha256(path))
            frozen = (expected["Length"], expected["Sha256"])
            if actual != frozen:
                raise RuntimeError(f"frozen input mismatch for {name}: {actual} != {frozen}")
            api.upload_path(job_url(job_id) + "/files/" + name, path, *actual)

        write_json(run_dir / "submitted.json", workflows.submit_draft(job_id))
        while True:
            current = workflows.wait(job_id, 45)
            print(json.dumps({"jobId": job_id, "state": current["state"], "runId": current.get("runId")}), flush=True)
            if current["state"] == "tested":
                break
            if current.get("blocker") or current["state"] in {
                "draft", "held", "blocked", "unavailable", "cancelled"
            }:
                raise RuntimeError(current)
        write_json(run_dir / "tested-summary.json", current)
        collection = workflows.collect(job_id, run_dir / "evidence", [], True)
        write_json(run_dir / "collection.json", collection)
        results.append(
            {
                "index": row["index"],
                "arm": row["arm"],
                "jobId": job_id,
                "runId": current.get("runId"),
                "summary": current,
            }
        )
        write_json(output / "execution-receipt.json", {"status": "running", "completed": results})

    write_json(output / "execution-receipt.json", {"status": "runs-complete", "order": "ABBA", "runs": results})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
