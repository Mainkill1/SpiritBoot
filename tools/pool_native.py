#!/usr/bin/env python3
"""Validate seven owned matched triplets and report every native timing sample."""
import argparse
import hashlib
import json
import math
import re
import statistics
import tomllib
from fractions import Fraction
from pathlib import Path

if __package__:
    from .pool_audit import PHASES, CURRENT
else:
    from pool_audit import PHASES, CURRENT

ROMS = {
    "baseline": "be180279642478d59bdd484abbaa3004d3efaf95a31194c838596341894c6827",
    "classes": "01150f76b3f71c2a597ff392e86799a54903d4013a88b74f7c925a7328dfb15f",
    "count": "ec2af59cfed4bc0782e9c7877ec9249f26dcfc6ea1dfca1e4d0e92f3547bc4e7",
}
ISO = "7478e1ecc3fb8e7fbbafc48a981f3ac7f6710fe028d0133e196411ec8490a7d2"
SIZES = (0, 1, 8, 16, 24, 32, 64, 96, 128, 192, 256, 384, 512, 768, 1024, 1536, 2040, 2384)


def require(value, message):
    if not value:
        raise ValueError(message)


def fields(line):
    return dict(v.split("=", 1) for v in line.split()[2:])


def read_run(path, side):
    serial = (path / "serial.log").read_bytes()
    text = serial.decode("utf-8").replace("\r", "")
    launch = json.loads((path / "launch.json").read_text())
    inputs = json.loads((path / "inputs.json").read_text())
    result = json.loads((path / "result.json").read_text())
    require(result["exited"] and result["exitCode"] == 0, "failed emulator exit")
    require(launch["biosSha256"].lower() == ROMS[side], "wrong ROM")
    require(launch["probeSha256"].lower() == ISO, "wrong guest image")
    require(inputs["memoryMiB"] == 64, "wrong RAM capacity")
    require(not re.search(r"^not ok\b", text, re.M), "failed TAP check")
    require(re.findall(r"^ok (\d+)\b", text, re.M) == [str(n) for n in range(1, 698)], "missing/duplicate TAP checks")
    require(re.findall(r"^1\.\.(\d+)$", text, re.M) == ["697"], "wrong TAP plan")
    require(re.findall(r"# checks=(\d+) failures=(\d+)", text) == [("697", "0")], "missing clean terminal")
    memory, capacities, costs = {}, {}, {64: {}, 200: {}, 280: {}}
    for line in text.splitlines():
        if line.startswith("# pool_memory "):
            row = fields(line)
            phase = row.pop("phase")
            require(phase not in memory, "duplicate memory checkpoint")
            memory[phase] = {k: int(v) for k, v in row.items()}
        elif line.startswith("# pool_capacity "):
            row = {k: int(v) for k, v in fields(line).items()}
            n = row["request"]
            require(n not in capacities, "duplicate capacity")
            classes = tuple(sorted(CURRENT + (272, 320))) if side == "classes" else CURRENT
            expected = ((n + 4095) // 4096) * 4096 if n > 2040 else next(c for c in classes if c >= max(n, 1) + 8) - 8
            require(row["usable"] == expected and row["mm_query"] == 0, "public capacity or MmQueryAllocationSize mismatch")
            capacities[n] = row
        elif line.startswith("# pool_cost "):
            row = {k: int(v) for k, v in fields(line).items()}
            n, round_number = row["request"], row["round"]
            require(n in costs and round_number not in costs[n], "unknown or duplicate timing")
            require(row["pairs"] == 32768 and row["frequency"] > 0 and row["ticks"] > 0, "invalid timing interval")
            costs[n][round_number] = row
    require(tuple(memory) == PHASES and tuple(capacities) == SIZES, "missing/extra/reordered checkpoints")
    require(all(sorted(rows) == list(range(5)) for rows in costs.values()), "incomplete five-round timing")
    config = tomllib.loads((path / "launch-xemu.toml").read_text())
    for key in ("flashrom_path", "hdd_path", "eeprom_path"):
        config["sys"]["files"].pop(key)
    return {"directory": path.name, "serial_sha256": hashlib.sha256(serial).hexdigest(),
            "launch": launch, "inputs": inputs, "result": result,
            "config_invariants": config, "memory": memory,
            "capacities": capacities, "costs": costs}


def analyze(root):
    runs = {}
    for path in root.glob("*pool-seven-*"):
        match = re.search(r"pool-seven-(\d+)-(baseline|classes|count)-", path.name)
        require(match is not None, "unexpected triplet directory")
        pair, side = int(match[1]), match[2]
        require(side not in runs.setdefault(pair, {}), "duplicate triplet side")
        runs[pair][side] = read_run(path, side)
    require(sorted(runs) == list(range(7)), "exactly seven triplets required")
    reference = runs[0]["baseline"]
    for pair, group in runs.items():
        require(set(group) == set(ROMS), "incomplete triplet")
        for side, run in group.items():
            require(run["launch"]["exeSha256"] == reference["launch"]["exeSha256"], "changed emulator")
            require(run["config_invariants"] == reference["config_invariants"], "changed emulator settings")
            for key in ("backingSha256", "backingLength", "backingModified", "bootromSha256", "eepromSha256"):
                require(run["inputs"][key] == reference["inputs"][key], "changed boot/disk/EEPROM input")
            for phase in PHASES:
                before, after = group["baseline"]["memory"][phase], run["memory"][phase]
                gain = (1 if phase == "boot" else 2) if side == "classes" else 0
                require(before["pool"] - after["pool"] == gain and after["available"] - before["available"] == gain, "physical-page saving mismatch")
                require(all(before[k] == after[k] for k in ("stack", "image", "cache")), "changed other page owner")
    comparisons = {}
    for side in ("classes", "count"):
        comparisons[side] = {}
        for size in (64, 200, 280):
            deltas = []
            for pair in range(7):
                before, after = runs[pair]["baseline"]["costs"][size], runs[pair][side]["costs"][size]
                require(len({r["frequency"] for r in list(before.values()) + list(after.values())}) == 1, "different performance-counter frequencies")
                a = statistics.median(r["ticks"] for r in before.values())
                b = statistics.median(r["ticks"] for r in after.values())
                deltas.append(Fraction(100 * (b - a), a))
            positive, negative = sum(v > 0 for v in deltas), sum(v < 0 for v in deltas)
            n = positive + negative
            pvalue = min(Fraction(1), Fraction(2 * sum(math.comb(n, k) for k in range(min(positive, negative) + 1)), 2**n))
            comparisons[side][size] = {"paired_percent_deltas": [float(v) for v in deltas],
                                      "median_percent": float(statistics.median(deltas)),
                                      "range_percent": [float(min(deltas)), float(max(deltas))],
                                      "two_sided_sign_test_p": float(pvalue)}
    return {"schema": 1, "checks": 21 * 697, "runs": runs, "comparisons": comparisons,
            "conclusion": "Classes save one boot page and two later pages in all seven runs. Latency is inconclusive; retain every sample and claim no speedup. The empty-count filter regresses 64/280 in every pair and fails the common-path gate."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(analyze(args.results), indent=2) + "\n")
