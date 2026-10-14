#!/usr/bin/env python3
"""Analyze integrity-clean owned pool audit checkpoints; never infer lifetimes."""
import argparse
import hashlib
import itertools
import json
import re
from collections import Counter
from pathlib import Path

CURRENT = (32, 64, 128, 256, 512, 1024, 2048)
SEED = (96, 192, 384, 768, 1536)
PHASES = ("boot", "threads32", "threads_retired", "irp64", "io_retired", "ladder_live", "ladder_retired", "churn_retired")


def capacity(request, classes):
    return next(c for c in classes if c >= max(request, 1) + 8)


def packing(entries, classes):
    """Optimistic packing lower bound, excluding empty or stranded pages."""
    counts = Counter()
    payload = block_bytes = 0
    for entry in entries:
        if entry["bin"] > 255:
            continue
        request = entry["bin"] * 8
        count = entry["live"]
        block = capacity(request, classes)
        counts[block] += count
        payload += request * count
        block_bytes += block * count
    pages = sum((n + 4096 // c - 1) // (4096 // c) for c, n in counts.items())
    return {"packed_lower_bound_pages": pages, "live_block_bytes": block_bytes,
            "request_upper_bound_bytes": payload,
            "live_allocations_by_class": dict(sorted(counts.items()))}


def parse(path):
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8", errors="replace")
    if re.search(r"^not ok\b", text, re.M) or "failures=0" not in text:
        raise ValueError("capture lacks clean terminal TAP")
    result = {p: {"entries": [], "pages": [], "histogram": {}} for p in PHASES}
    for line in text.splitlines():
        match = re.search(r"\b(pool_census|pool_bin|pool_pages|pool_scan|pool_scan_hist|pool_memory)\s+(.+)$", line)
        if not match:
            continue
        kind = match[1]
        values = dict(field.split("=", 1) for field in match[2].split())
        phase = values.pop("phase")
        if phase not in result:
            raise ValueError(f"unknown phase {phase}")
        record = {k: int(v, 16 if k == "tag" else 10) for k, v in values.items()}
        current = result[phase]
        if kind == "pool_bin":
            current["entries"].append(record)
        elif kind == "pool_pages":
            current["pages"].append(record)
        elif kind == "pool_scan_hist":
            if record["bucket"] in current["histogram"]:
                raise ValueError("duplicate histogram row")
            current["histogram"][record["bucket"]] = record["count"]
        else:
            name = kind.removeprefix("pool_")
            if name in current:
                raise ValueError(f"duplicate {kind} checkpoint")
            current[name] = record
    for phase, record in result.items():
        if not all(k in record for k in ("census", "scan", "memory")):
            raise ValueError(f"incomplete phase {phase}")
        census, scan = record["census"], record["scan"]
        if sum(e["live"] for e in record["entries"]) != census["alloc"] - census["free"]:
            raise ValueError(f"live allocation conservation failed at {phase}")
        if sum(p["active"] + p["empty"] for p in record["pages"]) != census["bucket"]:
            raise ValueError(f"bucket page conservation failed at {phase}")
        if scan["calls"] != scan["head_hits"] + scan["hits"] + scan["misses"]:
            raise ValueError(f"scan result conservation failed at {phase}")
        if sum(record["histogram"].values()) != scan["calls"]:
            raise ValueError(f"scan histogram conservation failed at {phase}")
        if scan["calls"] * 4096 >= 2**32:
            raise ValueError("32-bit diagnostic total cannot be proved free of overflow")
    return raw, result


def analyze(path):
    raw, records = parse(path)
    alternatives = {"current": CURRENT, "seed": tuple(sorted(CURRENT + SEED))}
    for count in range(1, 5):
        for extra in itertools.combinations(SEED, count):
            alternatives["add_" + "_".join(map(str, extra))] = tuple(sorted(CURRENT + extra))
    measured = sorted({((e["bin"] * 8 + 8 + 15) // 16) * 16
                       for r in records.values() for e in r["entries"]
                       if e["bin"] <= 255 and e["live"]})
    measured = [c for c in measured if c not in CURRENT and c <= 2048]
    boot = records["boot"]["entries"]
    old_boot = packing(boot, CURRENT)
    for count in range(1, 5):
        best = None
        for extra in itertools.combinations(measured, count):
            classes = tuple(sorted(CURRENT + extra))
            result = packing(boot, classes)
            score = (old_boot["packed_lower_bound_pages"] - result["packed_lower_bound_pages"],
                     old_boot["live_block_bytes"] - result["live_block_bytes"])
            if best is None or score > best[0]:
                best = (score, classes)
        alternatives[f"automatic_{count}_extra"] = best[1]
    scores = []
    for name, classes in alternatives.items():
        phases = {}
        for phase, record in records.items():
            item = packing(record["entries"], classes)
            old = packing(record["entries"], CURRENT)
            item["packed_page_gain_vs_current"] = old["packed_lower_bound_pages"] - item["packed_lower_bound_pages"]
            item["nominal_block_bytes_saved"] = old["live_block_bytes"] - item["live_block_bytes"]
            phases[phase] = item
        scores.append({"name": name, "classes": classes, "phases": phases})
    scan = records["churn_retired"]["scan"]
    return {"schema": 1, "serial_sha256": hashlib.sha256(raw).hexdigest(),
            "scope": "Owned native checkpoints only. Packing is an optimistic lower bound; it does not replay allocation order, lifetimes, or fragmentation, and cannot establish a production saving.",
            "measured_class_candidates": measured,
            "reuse_scan": {"full_negative_page_checks": (scan["fallback"] - scan["hits"]) * 4096,
                           "positive_page_checks": scan["examined"] - (scan["fallback"] - scan["hits"]) * 4096,
                           "steady_churn_added_fallbacks": scan["fallback"] - records["ladder_retired"]["scan"]["fallback"]},
            "capture": records, "alternatives": scores}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serial", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(analyze(args.serial), indent=2) + "\n")
