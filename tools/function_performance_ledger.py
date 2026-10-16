#!/usr/bin/env python3
"""Merge a complete kernel entry list with a marker-bounded function census."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


OUTPUT_FIELDS = (
    "pc", "label", "forza_marker_observed", "attribution_kind", "hits",
    "weighted_instructions", "weighted_instructions_share_percent",
    "primary_review_category", "primary_disposition", "optimized_in_batch",
    "required_hardware_correctness_path", "next_candidate",
    "performance_treatment", "evidence_limit",
)


def aliases(label: str) -> frozenset[str]:
    return frozenset(label.split("|"))


def load_entries(path: Path) -> list[tuple[str, str]]:
    entries = []
    seen = set()
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        try:
            pc, label = raw.split(maxsplit=1)
            address = int(pc, 16)
        except (ValueError, TypeError) as error:
            raise ValueError(f"malformed function entry at line {number}") from error
        if address in seen or not label:
            raise ValueError(f"duplicate/empty function entry at line {number}")
        seen.add(address)
        entries.append((f"0x{address:08x}", label))
    if not entries:
        raise ValueError("empty function entry list")
    return entries


def build(entries_path: Path, executed_path: Path,
          renames_path: Path | None = None) -> list[dict[str, str]]:
    executed = list(csv.DictReader(executed_path.open(newline="")))
    required = {"pc", "label", "attribution_kind", "hits",
                "weighted_instructions", "weighted_instructions_share_percent",
                "primary_review_category", "primary_disposition",
                "optimized_in_batch", "required_hardware_correctness_path",
                "next_candidate", "next_step"}
    if not executed or not required.issubset(executed[0]):
        raise ValueError("executed ledger is empty or missing required fields")

    renames = {}
    if renames_path:
        renames = json.loads(renames_path.read_text())
        if (not isinstance(renames, dict) or
                not all(isinstance(key, str) and
                        (isinstance(value, str) or value is None)
                        for key, value in renames.items())):
            raise ValueError("renames values must be a final label or null for a retired entry")

    by_alias: dict[str, dict[str, str]] = {}
    retired = set()
    for row in executed:
        for name in aliases(row["label"]):
            name = renames.get(name, name)
            if name is None:
                retired.add(id(row))
                continue
            prior = by_alias.setdefault(name, row)
            if prior is not row and prior["pc"] != row["pc"]:
                raise ValueError(f"ambiguous executed alias: {name}")

    rows = []
    matched = set()
    for pc, label in load_entries(entries_path):
        found = {id(by_alias[name]): by_alias[name]
                 for name in aliases(label) if name in by_alias}
        if len(found) > 1:
            raise ValueError(f"function aliases map to multiple rows: {label}")
        if found:
            source = next(iter(found.values()))
            matched.add(id(source))
            row = {
                "pc": pc,
                "label": label,
                "forza_marker_observed": "yes",
                "attribution_kind": source["attribution_kind"],
                "hits": source["hits"],
                "weighted_instructions": source["weighted_instructions"],
                "weighted_instructions_share_percent":
                    source["weighted_instructions_share_percent"],
                "primary_review_category": source["primary_review_category"],
                "primary_disposition": source["primary_disposition"],
                "optimized_in_batch": source["optimized_in_batch"],
                "required_hardware_correctness_path":
                    source["required_hardware_correctness_path"],
                "next_candidate": source["next_candidate"],
                "performance_treatment": source["next_step"],
                "evidence_limit":
                    "first marker-bounded 1024-read Forza replay pass",
            }
        else:
            row = {
                "pc": pc,
                "label": label,
                "forza_marker_observed": "no",
                "attribution_kind": "not_observed",
                "hits": "0",
                "weighted_instructions": "0",
                "weighted_instructions_share_percent": "0",
                "primary_review_category": "unmeasured",
                "primary_disposition": "requires_relevant_workload",
                "optimized_in_batch": "no",
                "required_hardware_correctness_path": "unknown",
                "next_candidate": "no",
                "performance_treatment":
                    "Exercise under the corresponding full-XISO leaf or game "
                    "path; change only after release before/after measurement "
                    "and behavioral equivalence checks.",
                "evidence_limit":
                    "not executed in this Forza marker window; no performance "
                    "claim is permitted",
            }
        rows.append(row)

    unmatched = [row["label"] for row in executed
                 if id(row) not in matched and id(row) not in retired]
    if unmatched:
        raise ValueError("executed rows absent from function list: " +
                         ", ".join(unmatched))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--functions", required=True, type=Path)
    parser.add_argument("--executed", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--renames", type=Path)
    args = parser.parse_args()
    rows = build(args.functions, args.executed, args.renames)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    main()
