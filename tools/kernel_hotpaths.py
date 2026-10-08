"""Symbol-resolved TB frequency, not retired instructions, calls or CPU time."""

import argparse
from bisect import bisect_right
import hashlib
import json
from pathlib import Path
import re
import subprocess


def natural(value, positive=False):
    if type(value) is not int or not int(positive) <= value <= 2**64 - 1:
        raise ValueError("invalid nonnegative integer counter")
    return value


def parse_capture(text):
    try:
        entries = [json.loads(line) for line in text.splitlines() if line.strip()]
        if not entries or entries[0].get("type") != "header" or entries[0].get("schema") != 1:
            raise ValueError("unsupported capture header")
        if entries[-1].get("type") != "complete":
            raise ValueError("capture incomplete: no successful exit footer")
        limit = natural(entries[0]["max_records"], True)
        if limit > 131072:
            raise ValueError("unsupported producer record budget")
        rows = entries[1:-1]
        if len(rows) > limit:
            raise ValueError("record budget exceeded")
        seen = set()
        for row in rows:
            if row.get("type") != "tb":
                raise ValueError("unexpected capture record")
            pc = int(row["pc"], 16)
            if not 0 <= pc <= 0xffffffff:
                raise ValueError("invalid i386 PC")
            digest = row["code_sha256"]
            if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("invalid code identity")
            for field in ("instructions", "translations", "executions"):
                natural(row[field], field != "executions")
            key = (pc, row["instructions"], digest)
            if key in seen:
                raise ValueError("duplicate TB identity")
            seen.add(key)
        footer = entries[-1]
        for field in ("dropped_translations", "untracked_executions", "untracked_weight"):
            natural(footer[field])
        dropped, executions, weight = (footer[x] for x in
                                       ("dropped_translations", "untracked_executions", "untracked_weight"))
        if (not dropped and (executions or weight)) or (dropped and len(rows) != limit):
            raise ValueError("inconsistent overflow coverage")
        if (not executions and weight) or weight < executions:
            raise ValueError("inconsistent untracked instruction weight")
        return rows, footer
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError(f"malformed capture: {error}") from error


def parse_sections(text):
    """Read objdump -h executable PE sections, including INIT and PAGE."""
    lines = text.splitlines()
    sections = []
    for index, line in enumerate(lines[:-1]):
        match = re.match(r"\s*\d+\s+(\S+)\s+([\da-fA-F]+)\s+([\da-fA-F]+)\s", line)
        if match and "CODE" in lines[index + 1]:
            name, size, address = match.groups()
            start = int(address, 16)
            sections.append((name, start, start + int(size, 16)))
    if not sections:
        raise ValueError("no executable image sections")
    return sections


def parse_symbols(text, sections):
    """Approximate function extents by next named symbol within the same section.

    PE nm does not provide function sizes. Attribution is explicitly an address
    interval estimate; local assembler labels and section symbols are excluded.
    """
    grouped = {}
    for line in text.splitlines():
        match = re.fullmatch(r"([\da-fA-F]+)\s+[Tt]\s+(\S+)", line.strip())
        if not match:
            continue
        address, name = match.groups()
        if name.startswith("."):
            continue
        address = int(address, 16)
        if any(start <= address < end for _, start, end in sections):
            grouped.setdefault(address, set()).add(name)
    symbols = []
    for section, start, end in sections:
        addresses = sorted(address for address in grouped if start <= address < end)
        for index, address in enumerate(addresses):
            symbols.append({"start": address, "end": addresses[index + 1] if index + 1 < len(addresses) else end,
                            "section": section, "symbols": sorted(grouped[address])})
    return sorted(symbols, key=lambda entry: entry["start"])


def rank(rows, symbols, meta):
    starts = [item["start"] for item in symbols]
    functions = {}
    unknown = 0
    total = meta["untracked_weight"]
    for row in rows:
        pc = int(row["pc"], 16)
        weight = row["instructions"] * row["executions"]
        total += weight
        index = bisect_right(starts, pc) - 1
        if index < 0 or pc >= symbols[index]["end"]:
            unknown += weight
            continue
        symbol = symbols[index]
        entry = functions.setdefault(symbol["start"], {**symbol, "tb_executions": 0,
                                    "weighted_instructions": 0, "tb_variants": 0})
        entry["tb_executions"] += row["executions"]
        entry["weighted_instructions"] += weight
        entry["tb_variants"] += 1
    return {"schema": 1, "measurement": "TB-entry frequency weighted by translated instruction count",
            "attribution": "TB start PC; next-symbol interval estimate within executable PE section",
            "limitations": ["Not retired instructions, function calls or CPU time",
                            "TBs may exit early; attribution may include padding or cross-function instructions",
                            "Outside the pinned image remains unknown, not automatically title or boot code"],
            "complete_coverage": meta["dropped_translations"] == 0,
            "capture": meta, "total_weighted_instructions": total,
            "unknown_weighted_instructions": unknown,
            "functions": sorted(functions.values(), key=lambda x: (-x["weighted_instructions"], x["start"]))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture", required=True, type=Path)
    parser.add_argument("--kernel", required=True, type=Path, help="Exact unstripped PE used to build captured BIOS")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rows, meta = parse_capture(args.capture.read_text())
    sections = parse_sections(subprocess.check_output(["objdump", "-h", str(args.kernel)], text=True))
    symbols = parse_symbols(subprocess.check_output(["nm", "-n", "--defined-only", str(args.kernel)], text=True), sections)
    if not symbols:
        raise ValueError("no named executable symbols")
    result = rank(rows, symbols, meta)
    result["inputs"] = {name: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                        for name, path in (("capture", args.capture), ("kernel", args.kernel))}
    # Never overwrite an earlier report or claim completion from a crashed run.
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    for item in result["functions"][:20]:
        print(f'{item["weighted_instructions"]:>16}  {item["tb_executions"]:>12}  {" / ".join(item["symbols"])}')
    print("Coverage:", "complete" if result["complete_coverage"] else "LIMITED: record budget reached")


if __name__ == "__main__":
    main()
