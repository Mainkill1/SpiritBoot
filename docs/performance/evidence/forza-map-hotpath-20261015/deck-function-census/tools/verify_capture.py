#!/usr/bin/env python3
"""Verify the bundled marked-phase census without access to the source workspace."""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path


def digest_stream(stream) -> tuple[str, int]:
    value = hashlib.sha256()
    size = 0
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        value.update(block)
        size += len(block)
    return value.hexdigest(), size


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return digest_stream(stream)[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bundle", nargs="?", default=Path(__file__).resolve().parents[1], type=Path)
    args = parser.parse_args()
    root = args.bundle.resolve()
    manifest = json.loads((root / "MANIFEST.json").read_text())

    checksum_failures = []
    for line in (root / "SHA256SUMS").read_text().splitlines():
        expected, relative = line.split("  ", 1)
        actual = digest(root / relative)
        if actual != expected:
            checksum_failures.append({"path": relative, "expected": expected, "actual": actual})
    assert not checksum_failures, checksum_failures

    events = [json.loads(line) for line in (root / "evidence/phase-profile.ndjson").read_text().splitlines()]
    header, start, end, complete = events[0], events[1], events[2], events[-1]
    assert header["type"] == "header" and header["entries"] == 1685
    assert start["type"] == "phase_start" and end["type"] == "phase_end"
    assert complete["type"] == "complete"
    assert complete["completed_windows"] == 1 and complete["clock_errors"] == 0
    entries = [event for event in events if event["type"] == "entry"]
    assert len(entries) == 191
    totals = {
        key: sum(row[key] for row in entries)
        for key in ("hits", "tb_executions", "weighted_instructions", "attributed_thread_cpu_ns")
    }
    expected_totals = manifest["capture"]
    assert totals["hits"] == expected_totals["exact_entry_hits"]
    assert totals["weighted_instructions"] == expected_totals["weighted_guest_instructions"]
    assert sum(row["tb_executions"] for row in entries) == complete["kernel_callbacks"]

    ledger = list(csv.DictReader((root / "results/executed-kernel-function-ledger.csv").open()))
    assert len(ledger) == len(entries) == manifest["capture"]["executed_ledger_rows"]
    allowed = {"optimize", "required_hardware", "correctness", "emulator", "diagnostic"}
    exact = range_only = 0
    for raw, row in zip(entries, ledger, strict=True):
        assert row["pc"] == raw["pc"] and row["label"] == raw["label"]
        for key in ("hits", "tb_executions", "weighted_instructions", "attributed_thread_cpu_ns"):
            assert int(row[key]) == raw[key]
            expected = 100.0 * raw[key] / totals[key] if totals[key] else 0.0
            assert abs(float(row[key + "_share_percent"]) - expected) < 1e-12
        assert row["primary_review_category"] in allowed
        for key in ("category_optimize", "category_required_hardware", "category_correctness",
                    "category_emulator", "category_diagnostic"):
            assert row[key] in {"yes", "no"}
        assert row["category_emulator"] == "no"
        if raw["hits"]:
            exact += 1
        elif raw["tb_executions"]:
            range_only += 1
            assert row["primary_review_category"] == "diagnostic"
    assert exact == 190 and range_only == 1

    compressed = (
        ("evidence/serial.log.gz", "raw_serial_uncompressed"),
        ("evidence/perf-20642.map.gz", "jit_perf_map_uncompressed"),
    )
    for relative, identity in compressed:
        with gzip.open(root / relative, "rb") as stream:
            actual_hash, actual_size = digest_stream(stream)
        expected = manifest["identities"][identity]
        assert actual_hash == expected["sha256"] and actual_size == expected["bytes"]

    print(json.dumps({
        "status": "pass",
        "checksummed_files": len((root / "SHA256SUMS").read_text().splitlines()),
        "loaded_entries": header["entries"],
        "executed_rows": len(ledger),
        "exact_entry_rows": exact,
        "range_only_rows": range_only,
        "totals": totals,
        "overflow": manifest["counter_integrity"]["overflow"],
        "lost_or_dropped_records": manifest["counter_integrity"]["lost_or_dropped_records"],
    }, indent=2))


if __name__ == "__main__":
    main()
