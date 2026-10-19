#!/usr/bin/env python3
"""Join fixed-BIOS Forza diagnostic events without retaining guest memory bytes.

Input is a raw `forza_io` log or the normalized JSONL(.gz) produced by --export.
Addresses/layouts belong to the exact binding in the accompanying evidence.
This analyzes a diagnostic capture; it does not qualify uninstrumented speed.
"""
from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
from collections import Counter, defaultdict
import gzip
import json
import math
from pathlib import Path
import statistics


FIELDS = {
    "_XeNtReadFile@32": "returning esp ret a4 a5 a7 p8 p8hi eax",
    "fatx_dispatch": "iosb name",
    "native_submit": "iosb irp",
    "io_complete": "irp status info",
    "io_apc_delivery": "iosb",
    "title_apc_dispatch": "a1 a2",
    "world_completion_callback": "a1 a2 a3",
    "delay_thread": "a1 a2",
    "memory_statistics_query": "",
}


def normalize(line):
    if not line.startswith("forza_io "):
        return None
    fields = dict(token.split("=", 1) for token in line.split()[1:] if "=" in token)
    kind = fields["kind"]
    if kind not in FIELDS:
        return None
    row = {key: fields[key] for key in
           ("kind host_ns virtual_ns thread free_pages " + FIELDS[kind]).split()}
    if kind == "delay_thread":
        # The interval sometimes points into the eight captured stack arguments.
        # Only label it zero when BOTH 32-bit halves were captured and are zero.
        slot = (int(fields["a3"], 16) - int(fields["esp"], 16)) // 4
        aligned = (int(fields["a3"], 16) - int(fields["esp"], 16)) % 4 == 0
        row["zero_interval"] = (aligned and 1 <= slot <= 7 and
                                fields[f"a{slot}"] == "00000000" and
                                fields[f"a{slot + 1}"] == "00000000")
    return row


def read_events(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as source:
        for line in source:
            if line.startswith("{"):
                yield json.loads(line)
            else:
                row = normalize(line)
                if row is not None:
                    yield row


def stats(values):
    if not values:
        return {"n": 0}
    values = sorted(values)
    return {"n": len(values), "median": statistics.median(values),
            "p95": values[math.ceil(len(values) * .95) - 1], "max": max(values)}


def analyze(events, resource="FarmersLipShort.res"):
    records, parents, active_calls = {}, {}, {}
    waits = defaultdict(list)
    done, issues, counts = [], Counter(), Counter()
    previous_host = None
    for event in events:
        kind = event["kind"]
        counts[kind] += 1
        host, virtual = int(event["host_ns"]), int(event["virtual_ns"])
        if previous_host is not None and host < previous_host:
            raise ValueError("host clock moved backward; split the capture before analysis")
        previous_host = host
        if kind == "_XeNtReadFile@32":
            call = (event["thread"], event["esp"])
            if event["returning"] == "0":
                iosb = event["a5"]
                if iosb in records and "title" not in records[iosb]:
                    issues["iosb_reused_without_observed_callback"] += 1
                record = dict(iosb=iosb, thread=event["thread"], begin=host,
                              begin_v=virtual, caller=event["ret"], size=int(event["a7"], 16),
                              free_pages=int(event["free_pages"]))
                records[iosb] = record
                active_calls[call] = record
            elif call in active_calls:
                active_calls.pop(call).update(return_time=host, return_status=event["eax"])
            else:
                issues["unmatched_read_return"] += 1
        elif kind == "fatx_dispatch" and event["iosb"] in records:
            records[event["iosb"]]["file"] = event["name"]
        elif kind == "native_submit" and event["iosb"] in records:
            record = records[event["iosb"]]
            if "native" in record:
                issues["multiple_native_submissions_for_iosb"] += 1
            record["native_count"] = record.get("native_count", 0) + 1
            record["native"] = host
            parents[event["irp"]] = record
        elif kind == "io_complete" and event["irp"] in parents:
            # Retire the IRP immediately: addresses are reused by later requests.
            parents.pop(event["irp"]).update(done=host, done_v=virtual,
                                             status=event["status"], info=int(event["info"]))
        elif kind == "io_apc_delivery" and event["iosb"] in records:
            records[event["iosb"]]["kernel_apc"] = host
        elif kind == "title_apc_dispatch" and event["a2"] in records:
            record = records[event["a2"]]
            if "title" in record:
                issues["duplicate_title_dispatch"] += 1
            else:
                record.update(title=host, title_v=virtual)
                done.append(record)
        elif kind == "world_completion_callback" and event["a3"] in records:
            records[event["a3"]].update(actual_callback=host, callback_error=event["a1"],
                                        callback_bytes=int(event["a2"], 16))
        elif kind == "delay_thread" and event["a1"] == "00000001" and event["a2"] == "00000001":
            waits[event["thread"]].append((host, event["zero_interval"]))

    world = [r for r in done if resource in r.get("file", "") and "done" in r]
    distribution = Counter()
    first_wait_to_callback, missed_poll = [], 0
    wait_times = {thread: [time for time, _ in rows] for thread, rows in waits.items()}
    for record in world:
        if not record["begin"] <= record["native"] <= record["done"] <= record["title"]:
            raise ValueError("request lifecycle out of order")
        if record["title_v"] < record["done_v"]:
            raise ValueError("snapshot/clock rewind within a request; split capture")
        times = wait_times.get(record["thread"], [])
        left, right = bisect_right(times, record["done"]), bisect_left(times, record["title"])
        distribution[str(right - left)] += 1
        if left < right:
            first_wait_to_callback.append((record["title"] - times[left]) / 1e6)
        after_issue = bisect_right(times, record["begin"])
        if after_issue < len(times) and times[after_issue] < record["done"]:
            missed_poll += int(waits[record["thread"]][after_issue][1])

    return {
        "scope": "diagnostic replay; dispatcher entry is callback availability, not world publication",
        "world_reads_delivered": len(world),
        "native_ms": stats([(r["done"] - r["native"]) / 1e6 for r in world]),
        "done_to_title_ms": stats([(r["title"] - r["done"]) / 1e6 for r in world]),
        "done_to_title_virtual_ms": stats([(r["title_v"] - r["done_v"]) / 1e6 for r in world]),
        "first_alertable_entry_to_callback_ms": stats(first_wait_to_callback),
        "alertable_delay_entries_between_completion_and_callback": dict(distribution),
        "read_completed_after_first_zero_timeout_poll": missed_poll,
        "world_completion_statuses": dict(Counter(r["status"] for r in world)),
        "world_return_statuses": dict(Counter(r.get("return_status", "unobserved") for r in world)),
        "world_byte_count_mismatches": sum(r["size"] != r["info"] for r in world),
        "world_multiple_native_submissions": sum(r["native_count"] != 1 for r in world),
        "world_actual_callbacks": sum("actual_callback" in r for r in world),
        "world_callback_errors": sum(r.get("callback_error") != "00000000" for r in world),
        "world_callback_byte_count_mismatches": sum(r.get("callback_bytes") != r["size"] for r in world),
        "dispatcher_to_actual_callback_ms": stats([
            (r["actual_callback"] - r["title"]) / 1e6 for r in world if "actual_callback" in r]),
        "world_free_pages": stats([r["free_pages"] for r in world]),
        "memory_query_count": counts["memory_statistics_query"],
        "capture_join_notes_all_files": dict(issues),
        "events": dict(counts),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--export", type=Path, help="write metadata-only gzip JSONL")
    args = parser.parse_args()
    events = list(read_events(args.input))
    result = json.dumps(analyze(events), indent=2) + "\n"
    if args.output:
        args.output.write_text(result)
    else:
        print(result, end="")
    if args.export:
        with gzip.GzipFile(filename=str(args.export), mode="wb", mtime=0) as target:
            for event in events:
                target.write((json.dumps(event, separators=(",", ":")) + "\n").encode())


if __name__ == "__main__":
    main()
