#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Fail-closed validation for release-only, fresh-process title jobs."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _pick(row: dict[str, Any], name: str, default: Any = None) -> Any:
    return row.get(name, row.get(name[0].upper() + name[1:], default))


def _asset_tuple(row: dict[str, Any]) -> tuple[Any, Any]:
    return _pick(row, "assetId"), _pick(row, "expectedSha256")


def validate_release_job(job: dict[str, Any], spec: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    firmware = spec.get("firmware_sha256")
    if not isinstance(firmware, str) or not SHA256.fullmatch(firmware):
        errors.append("firmware hash is unresolved")
    elif firmware in set(spec.get("rejected_firmware_sha256", [])):
        errors.append("firmware hash is explicitly rejected")

    if _pick(job, "launchMode") != "direct":
        errors.append("launchMode must be direct")
    if _pick(job, "startPaused") is not False:
        errors.append("startPaused must be false")
    if _pick(job, "snapshotName") is not None:
        errors.append("snapshotName must be null")
    arguments = [str(x) for x in _pick(job, "arguments", [])]
    if not any(arguments[i] == "-m" and i + 1 < len(arguments) and arguments[i + 1] == "64"
               for i in range(len(arguments))):
        errors.append("job must pin 64 MiB")
    if any(x.lower() in ("-s", "--debug", "-gdb", "--gdb") for x in arguments):
        errors.append("release job contains a debugger argument")

    runtime = _pick(job, "runtimeState", {}) or {}
    isolation = _pick(runtime, "isolation", {}) or {}
    if _pick(runtime, "enabled") is not True:
        errors.append("runtime state must be enabled")
    if _pick(isolation, "requirePrivateGuestState") is not True:
        errors.append("private guest state is required")
    if str(_pick(isolation, "cacheMode", "")).lower() != "cold":
        errors.append("application cache must be cold")

    disks = list(_pick(runtime, "diskAssets", []) or [])
    expected_hdd = spec.get("hdd", {})
    if len(disks) != 1 or _asset_tuple(disks[0]) != (
            expected_hdd.get("id"), expected_hdd.get("sha256")):
        errors.append("HDD asset differs from the frozen contract")
    elif _pick(disks[0], "retention") != expected_hdd.get("retention", "deleteAfterEvidence"):
        errors.append("HDD retention must be " + expected_hdd.get("retention", "deleteAfterEvidence"))

    readonly = list(_pick(isolation, "readOnlyAssets", []) or [])
    dvd = next((x for x in readonly if _pick(x, "field") == "dvd_path"), None)
    expected_disc = spec.get("disc", {})
    if dvd is None or _asset_tuple(dvd) != (expected_disc.get("id"), expected_disc.get("sha256")):
        errors.append("disc asset differs from the frozen contract")
    flash = next((x for x in readonly if _pick(x, "field") == "flashrom_path"), None)
    if firmware and SHA256.fullmatch(str(firmware)):
        if flash is None or _pick(flash, "expectedSha256") != firmware:
            errors.append("runtime firmware differs from the frozen contract")

    inputs = list(_pick(job, "inputs", []) or [])
    flash_input = next((x for x in inputs if _pick(x, "path") == "flash.bin"), None)
    if firmware and SHA256.fullmatch(str(firmware)):
        if flash_input is None or _pick(flash_input, "expectedSha256") != firmware:
            errors.append("package firmware differs from the frozen contract")
    xemu_input = next((x for x in inputs if _pick(x, "path") == "xemu.exe"), None)
    if xemu_input is None or _pick(xemu_input, "expectedSha256") != spec.get("xemu_sha256"):
        errors.append("xemu differs from the frozen release build")

    if _pick(job, "plan", []) != spec.get("plan"):
        errors.append("job plan differs from the frozen route")
    operations = _pick(job, "operations", {}) or {}
    if _pick(operations, "allowManualInput") is not False:
        errors.append("manual input must be disabled")
    experiment = _pick(job, "experiment", {}) or {}
    if _pick(experiment, "allowOperatorIntervention") is not False:
        errors.append("operator intervention must be disabled")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job", type=Path)
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    failures = validate_release_job(json.loads(args.job.read_text()),
                                    json.loads(args.spec.read_text()))
    print(json.dumps({"pass": not failures, "errors": failures}, indent=2))
    raise SystemExit(1 if failures else 0)
