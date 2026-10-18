#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Pin one release64 BIOS and materialize the automated title-gate jobs."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from rclass_gate import build_forza_plan
from release_job_validator import SHA256, validate_release_job
from release_title_routes import (
    build_doa_create_plan,
    build_doa_reload_plan,
    build_halo2_menu_plan,
    build_pgr2_profile_create_plan,
    build_pgr2_cold_race_plan,
)

TITLE_ORDER = ("pgr2-create", "forza", "halo2-a", "halo2-b", "doa-create")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_contract(contract: dict[str, Any], candidate_id: str,
                     firmware_sha256: str) -> dict[str, Any]:
    if not SAFE_ID.fullmatch(candidate_id):
        raise ValueError("candidate id must match [a-z0-9][a-z0-9-]{0,31}")
    if not SHA256.fullmatch(firmware_sha256):
        raise ValueError("firmware SHA-256 must be 64 lowercase hexadecimal digits")
    result = copy.deepcopy(contract)
    result["state"] = "resolved"
    result["common"]["firmware_asset"] = {
        "id": f"spiritboot-release64-{candidate_id}-{firmware_sha256[:12]}",
        "sha256": firmware_sha256,
    }
    return result


def _require_asset(row: Any, label: str) -> dict[str, str]:
    if not isinstance(row, dict) or not row.get("id") or not SHA256.fullmatch(str(row.get("sha256", ""))):
        raise ValueError(f"{label} is unresolved; register and pin the managed runner asset first")
    return row


def _replace_firmware(value: Any, old_sha: str, new_sha: str) -> Any:
    if isinstance(value, str):
        return value.replace(old_sha, new_sha)
    if isinstance(value, list):
        return [_replace_firmware(item, old_sha, new_sha) for item in value]
    if isinstance(value, dict):
        return {key: _replace_firmware(item, old_sha, new_sha)
                for key, item in value.items()}
    return value


def _shot_checks(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "name": f"{row['name']}-visible",
        "scope": "result",
        "path": f"screenshots/{row['name']}.png",
        "mustExist": True,
        "minimumBytes": 1000,
        "minimumNonBlackPixelRatio": 0.01,
        "nonBlackPixelThreshold": 96,
        "imageRegion": None,
        "expectedSha256": None,
        "containsText": None,
        "equalsText": None,
    } for row in plan if row.get("type") == "screenshot"]


def _title_definition(contract: dict[str, Any], title: str) -> tuple[list[dict[str, Any]], dict, dict, str, int]:
    titles = contract["titles"]
    if title == "pgr2-create":
        row = titles["pgr2"]
        return build_pgr2_profile_create_plan(), row["hdd_seed"], row["disc"], "keep", 180
    if title == "pgr2-reload":
        row = titles["pgr2"]
        return build_pgr2_cold_race_plan(), row["phase_two_hdd"], row["disc"], "deleteAfterEvidence", 210
    if title == "forza":
        row = titles["forza"]
        return build_forza_plan(), row["hdd"], row["disc"], "deleteAfterEvidence", 330
    if title in ("halo2-a", "halo2-b"):
        row = titles["halo2"]
        return build_halo2_menu_plan(), row["hdd"], row["disc"], "deleteAfterEvidence", 120
    if title == "doa-create":
        row = titles["doa"]
        return build_doa_create_plan(), row["hdd_seed"], row["disc"], "keep", 190
    if title == "doa-reload":
        row = titles["doa"]
        return build_doa_reload_plan(), row["phase_two_hdd"], row["disc"], "deleteAfterEvidence", 130
    raise ValueError("unknown title gate: " + title)


def build_title_job(base_job: dict[str, Any], contract: dict[str, Any], title: str,
                    candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    firmware = _require_asset(contract["common"]["firmware_asset"], "common.firmware_asset")
    plan, hdd, disc, retention, timeout = _title_definition(contract, title)
    hdd = _require_asset(hdd, f"{title}.hdd")
    disc = _require_asset(disc, f"{title}.disc")

    old_flash = next(row["expectedSha256"] for row in base_job["inputs"]
                     if row["path"] == "flash.bin")
    job = _replace_firmware(copy.deepcopy(base_job), old_flash, firmware["sha256"])
    job["id"] = f"sb-{candidate_id}-{title}-release64"
    job["timeoutSeconds"] = timeout
    job["tags"] = ["SPIRITBOOT", "RELEASE64", "FRESH-PROCESS", "PRIVATE-HDD-COPY",
                   "COLD-APP-CACHE", title.upper()]
    job["plan"] = plan

    if title == "forza":
        diagnostics = job["diagnostics"]
    elif title == "doa-create":
        template = next(row for row in job["diagnostics"] if row.get("type") == "qmp")
        diagnostics = []
        for diagnostic_id in ("doa-save-write-before", "doa-save-write-after"):
            row = copy.deepcopy(template)
            row["id"] = diagnostic_id
            row["qmpCommand"] = "query-blockstats"
            diagnostics.append(row)
    else:
        diagnostics = []
    job["diagnostics"] = diagnostics

    runtime = job["runtimeState"]
    runtime["keepOnSuccess"] = title in ("pgr2-create", "doa-create")
    runtime["keepOnFailure"] = True
    runtime["diskAssets"] = [{
        "assetId": hdd["id"], "expectedSha256": hdd["sha256"],
        "destination": "hdd.qcow2", "retention": retention,
    }]
    readonly = runtime["isolation"]["readOnlyAssets"]
    for row in readonly:
        if row["field"] == "flashrom_path":
            row["assetId"], row["expectedSha256"] = firmware["id"], firmware["sha256"]
        elif row["field"] == "dvd_path":
            row["assetId"], row["expectedSha256"] = disc["id"], disc["sha256"]

    job["workload"] = {
        "correctnessChecks": _shot_checks(plan),
        "evidenceRequirements": [{
            "name": "qemu-log", "scope": "result", "path": "qemu.log",
            "mustExist": True, "minimumBytes": 0,
            "minimumNonBlackPixelRatio": None, "nonBlackPixelThreshold": 0,
            "imageRegion": None, "expectedSha256": None,
            "containsText": None, "equalsText": None,
        }],
        "reportedMetrics": [], "minimumMetricSamples": 0,
        "requirePlanCompletion": True,
    }
    job["experiment"] = {
        "id": f"spiritboot-release64-title-gate-{candidate_id}",
        "variant": title,
        "reference": None,
        "variedFactors": ["firmware"],
        "controlledFactors": [
            "release-xemu-" + contract["common"]["xemu"]["sha256"],
            "release64-firmware-" + firmware["sha256"],
            "disc-" + disc["sha256"], "fresh-process", "private-HDD-copy",
            "cold-application-cache", "64MiB",
        ],
        "requireCorrectnessPass": True, "requireCompleteEvidence": True,
        "allowOperatorIntervention": False, "allowDiagnostics": bool(diagnostics),
    }
    job["operations"]["allowDiagnostics"] = bool(diagnostics)
    job["operations"]["diagnosticsAllowed"] = bool(diagnostics)

    spec = {
        "firmware_sha256": firmware["sha256"],
        "xemu_sha256": contract["common"]["xemu"]["sha256"],
        "hdd": {"id": hdd["id"], "sha256": hdd["sha256"], "retention": retention},
        "disc": {"id": disc["id"], "sha256": disc["sha256"]},
        "plan": plan,
        "rejected_firmware_sha256": contract.get("rejected_firmware_sha256", []),
    }
    failures = validate_release_job(job, spec)
    if failures:
        raise ValueError(title + " job validation failed: " + "; ".join(failures))
    return job, spec


def _stage_package(base_package: Path, target: Path, flash: Path,
                   job: dict[str, Any], spec: dict[str, Any]) -> None:
    target.mkdir(parents=True)
    for source in sorted(base_package.rglob("*")):
        if not source.is_file() or source.name in ("job.json", "flash.bin"):
            continue
        relative = source.relative_to(base_package)
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        try:
            os.link(source, destination)
        except OSError:
            shutil.copy2(source, destination)
    shutil.copy2(flash, target / "flash.bin")
    (target / "job.json").write_text(json.dumps(job, indent=2) + "\n")
    (target / "validator-spec.json").write_text(json.dumps(spec, indent=2) + "\n")


def _verify_base_package(base_package: Path, base_job: dict[str, Any],
                         contract: dict[str, Any]) -> None:
    declared = {row["path"]: row["expectedSha256"] for row in base_job["inputs"]
                if row["path"] != "flash.bin"}
    missing = [name for name in base_job["requiredFiles"]
               if name != "flash.bin" and name not in declared]
    if missing:
        raise ValueError("base required files lack pinned input hashes: " + ", ".join(missing))
    for name, expected in declared.items():
        path = base_package / name
        if path.is_symlink() or not path.is_file():
            raise ValueError("base package input is missing or linked: " + name)
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(f"base package input hash mismatch for {name}: {actual}")
    common = contract["common"]
    checks = {
        "xemu.exe": common["xemu"]["sha256"],
        "native-launch.exe": common["launcher"]["sha256"],
        "state/eeprom.bin": common["eeprom_sha256"],
    }
    for name, expected in checks.items():
        if declared.get(name) != expected:
            raise ValueError(f"base package {name} differs from the contract")


def finalize(*, flash: Path, expected_sha256: str, candidate_id: str,
             contract_path: Path, base_package: Path, output: Path) -> dict[str, Any]:
    for path, label in ((flash, "flash"), (contract_path, "contract"),
                        (base_package / "job.json", "base package job")):
        if path.is_symlink() or not path.is_file():
            raise ValueError(label + " must be a regular, non-linked file")
    actual = sha256_file(flash)
    if actual != expected_sha256:
        raise ValueError(f"firmware hash mismatch: expected {expected_sha256}, got {actual}")
    if output.exists():
        raise ValueError("output already exists: " + str(output))
    contract = resolve_contract(json.loads(contract_path.read_text()), candidate_id, actual)
    base = json.loads((base_package / "job.json").read_text())
    _verify_base_package(base_package, base, contract)
    output.mkdir(parents=True)
    (output / "contract.resolved.json").write_text(json.dumps(contract, indent=2) + "\n")
    ready = []
    try:
        for title in TITLE_ORDER:
            job, spec = build_title_job(base, contract, title, candidate_id)
            _stage_package(base_package, output / "packages" / title, flash, job, spec)
            ready.append(title)
        pgr2_reload_template = {
            "candidate_id": candidate_id,
            "title": "pgr2-reload",
            "requires": "exact retained pgr2-create runtime hdd.qcow2 imported by the runner",
        }
        (output / "pgr2-reload.template.json").write_text(
            json.dumps(pgr2_reload_template, indent=2) + "\n")
        reload_template = {
            "candidate_id": candidate_id,
            "title": "doa-reload",
            "requires": "exact retained doa-create runtime hdd.qcow2 imported by the runner",
        }
        (output / "doa-reload.template.json").write_text(json.dumps(reload_template, indent=2) + "\n")
        report = {
            "schema_version": 1, "candidate_id": candidate_id,
            "firmware_asset_id": contract["common"]["firmware_asset"]["id"],
            "firmware_sha256": actual, "ready_jobs": ready,
            "pgr2_reload": "materialized automatically after pgr2-create",
            "doa_reload": "materialized automatically after doa-create",
        }
        (output / "finalization.json").write_text(json.dumps(report, indent=2) + "\n")
        return report
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--flash", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--base-package", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = finalize(flash=args.flash, expected_sha256=args.expected_sha256,
                      candidate_id=args.candidate_id, contract_path=args.contract,
                      base_package=args.base_package, output=args.output)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
