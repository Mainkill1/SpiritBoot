#!/usr/bin/env python3
"""Run the pinned Conker XDVDFS shape trace through Xemu-Test-Runner."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[5]
WORKSPACE = ROOT.parents[2]
GAME = WORKSPACE / ".scratch/spiritboot-game-profile-20261015"
sys.path.insert(0, str(WORKSPACE / "xemu-test-runner-mesa-review/scripts"))
from runner_transport import RunnerApi, job_url  # type: ignore  # noqa: E402
from runner_workflows import Workflows  # type: ignore  # noqa: E402

RUNNER = "http://10.0.7.1:9368"
JOB_ID = "spiritboot-conker-xdvdfs-shape-release64-20261016-v2"
REUSE_JOB = "sbprof-conker-s-p-46-20261015-v1"
HERE = Path(__file__).resolve().parent
OUTPUT = HERE.parent / "windows-trace-v2"

FILES = {
    "flash.bin": ROOT / ".scratch/advanced-all-safe-release64-r2/flash.bin",
    "native-launch.exe": GAME / "launcher/host-bin/native-launch.exe",
    "qemu.exe": WORKSPACE / ".scratch/forza-api-native-20261013/forza-trace-xemu.exe",
    "state/eeprom.bin": WORKSPACE / ".scratch/doa-crash-20261015/prepared/payload/state/eeprom.bin",
    "xdvdfs_trace_plugin.dll": HERE / "xdvdfs_trace_plugin.dll",
    "xemu.toml": GAME / "xemu.toml",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def file_record(name: str, path: Path) -> dict[str, object]:
    return {
        "Path": name,
        "Length": path.stat().st_size,
        "Sha256": sha256(path),
        "Executable": path.suffix == ".exe",
    }


def make_request() -> dict[str, object]:
    files = [file_record(name, path) for name, path in sorted(FILES.items())]
    job = {
        "id": JOB_ID,
        "targetOs": "windows",
        "executable": "native-launch.exe",
        "expectedExecutableSha256": sha256(FILES["native-launch.exe"]),
        "arguments": [
            "-config_path", "{packageDir}/xemu.toml", "-m", "64",
            "-device", "lpc47m157", "-serial", "file:{resultDir}/serial.log",
            "-no-shutdown", "-plugin",
            (
                "{packageDir}/xdvdfs_trace_plugin.dll,"
                "output={resultDir}/xdvdfs-request-facts.tsv,"
                "report={resultDir}/xdvdfs-trace-report.json,pc=0x8404840c"
            ),
        ],
        "environment": {
            "PR248_NATIVE_PACKAGE": "{packageDir}",
            "PR248_NATIVE_EVIDENCE": "{resultDir}",
            "SB_GAME": "conker",
            "SB_BIOS_ARM": "spiritboot",
            "SB_MODE": "profile",
            "SB_SAMPLE_SECONDS": "60",
            "XEMU_FRAME_LOG": "{resultDir}/guest-frames.log",
            "XEMU_FLIP_LOG": "{resultDir}/guest-flips.log",
            "DISABLE_RTSS_LAYER": "1",
            "DISABLE_VULKAN_OBS_CAPTURE": "1",
        },
        "workingDirectory": ".",
        "launchMode": "direct",
        "timeoutSeconds": 360,
        "startPaused": False,
        "requireInput": False,
        "requiredFiles": [row["Path"] for row in files],
        "inputs": [
            {
                "path": row["Path"],
                "hash": True,
                "expectedSha256": row["Sha256"],
                "role": "emulator" if row["Path"] == "qemu.exe" else "diagnostic-input",
            }
            for row in files
        ],
        "tags": [
            "spiritboot-real-game-profile", "conker", "release64",
            "diagnostic-xdvdfs-request-shape", "rust-model-input",
        ],
        "operations": {
            "mode": "diagnostic",
            "allowDiagnostics": False,
            "allowManualInput": False,
            "allowPauseResume": False,
            "allowPreview": False,
            "allowBulkTransfers": True,
        },
        "diagnostics": [],
        "plan": [
            {
                "type": "wait_for_artifact",
                "condition": {
                    "path": "performance.json", "scope": "result", "mustExist": True,
                },
                "pollIntervalMs": 500,
                "timeoutMs": 300000,
            },
            {"type": "wait", "delayMs": 1000},
            {"type": "quit"},
        ],
        "runtimeState": {
            "enabled": True,
            "files": [
                {
                    "source": "state/eeprom.bin",
                    "destination": "eeprom.bin",
                    "expectedSha256": sha256(FILES["state/eeprom.bin"]),
                }
            ],
            "diskAssets": [
                {
                    "assetId": "pr256-clean-fatx-compat010-v1",
                    "destination": "hdd.qcow2",
                    "expectedSha256": "78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b",
                    "retention": "deleteAfterEvidence",
                }
            ],
            "keepOnSuccess": False,
            "keepOnFailure": True,
            "isolation": {
                "cacheMode": "cold",
                "cacheShaders": False,
                "driverCache": "uncontrolled",
                "allowUncontrolledDriverCache": True,
                "requirePrivateGuestState": True,
                "maximumBytes": 536870912,
                "maximumFiles": 8192,
                "deadlineSeconds": 30,
                "readOnlyAssets": [
                    {
                        "field": "bootrom_path",
                        "assetId": "devbox-mcpx10-readonly-v1",
                        "expectedSha256": "e99e3a772bf5f5d262786aee895664eb96136196e37732fe66e14ae062f20335",
                    },
                    {
                        "field": "dvd_path",
                        "assetId": "conker-usa-readonly-v1",
                        "expectedSha256": "9f9f4e20224865436d96664198d56559ed1f5762cf29410343bdcec4e70692ba",
                    },
                ],
            },
        },
        "workload": {
            "requirePlanCompletion": True,
            "evidenceRequirements": [
                {
                    "name": "request-facts", "scope": "result",
                    "path": "xdvdfs-request-facts.tsv", "mustExist": True,
                    "minimumBytes": 1,
                },
                {
                    "name": "trace-report", "scope": "result",
                    "path": "xdvdfs-trace-report.json", "mustExist": True,
                    "minimumBytes": 20,
                },
            ],
        },
        "experiment": {
            "id": "conker-xdvdfs-shape-20261016",
            "variant": "release64-scalar-trace",
            "variedFactors": ["diagnostic-plugin"],
            "controlledFactors": ["bios", "kernel", "game", "hdd", "host"],
            "requireCorrectnessPass": True,
            "requireCompleteEvidence": True,
            "allowOperatorIntervention": False,
            "allowDiagnostics": True,
        },
    }
    return {"id": JOB_ID, "files": files, "job": job}


def main() -> int:
    request = make_request()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "request.json").write_text(json.dumps(request, indent=2) + "\n")
    api = RunnerApi(RUNNER, timeout=120)
    workflows = Workflows(api, operation_seconds=900, progress=False)
    state = api.json("/api/v1/status")
    if state.get("CurrentJob") or state["Queue"]["Pending"] or state["Queue"]["Testing"]:
        raise RuntimeError(f"runner is not idle: {state}")
    api.json("/api/v1/jobs", "POST", request)
    api.json(job_url(JOB_ID) + "/reuse", "POST", {"sourceJobId": REUSE_JOB})
    workflows.operation(JOB_ID)
    available = {row["path"]: row for row in api.json(job_url(JOB_ID) + "/files")}
    for row in request["files"]:
        status = available.get(row["Path"], {}).get("status", {})
        if not status.get("complete") or available[row["Path"]].get("sha256") != row["Sha256"]:
            api.upload_path(
                job_url(JOB_ID) + "/files/" + row["Path"],
                FILES[row["Path"]], row["Length"], row["Sha256"],
            )
    workflows.submit_draft(JOB_ID)
    while True:
        state = workflows.wait(JOB_ID, 45)
        print(json.dumps({"state": state.get("state"), "runId": state.get("runId")}), flush=True)
        if state.get("state") == "tested":
            break
        if state.get("blocker") or state.get("state") in {
            "draft", "held", "blocked", "unavailable", "cancelled",
        }:
            raise RuntimeError(state)
    receipt = workflows.collect(JOB_ID, OUTPUT / "evidence", [], True)
    (OUTPUT / "collection.json").write_text(json.dumps(receipt, indent=2) + "\n")
    results = list((OUTPUT / "evidence").glob("*/result.json"))
    if len(results) != 1:
        raise RuntimeError("expected one collected result.json")
    result = json.loads(results[0].read_text())
    if (result.get("status") != "completed" or
            result.get("evidenceStatus") != "complete"):
        raise RuntimeError(
            f"trace rejected: {result.get('status')}/"
            f"{result.get('evidenceStatus')}: {result.get('detail')}")
    print(json.dumps(receipt), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
