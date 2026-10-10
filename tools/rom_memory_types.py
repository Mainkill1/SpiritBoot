"""Read-only Intel memory-type interpretation for the optional ROM diagnostic.

Intel SDM vol. 3A tables 11-7 and 11-11 define these public architectural
relationships. No physical latency is inferred from the effective type.
Unsupported/ambiguous configurations remain UNKNOWN.
"""
import argparse
import json
from pathlib import Path

TYPES = {0: "UC", 1: "WC", 4: "WT", 5: "WP", 6: "WB", 7: "UC-"}
PAT_ORDER = ("UC", "UC-", "WC", "WT", "WB", "WP")
COMBINATIONS = {
    "UC": ("UC", "UC", "WC", "UC", "UC", "UC"),
    "WC": ("UC", "WC", "WC", "UC", "WC", "UC"),
    "WT": ("UC", "UC", "WC", "WT", "WT", "WP"),
    "WB": ("UC", "UC", "WC", "WT", "WB", "WP"),
    "WP": ("UC", "WC", "WC", "WT", "WP", "WP"),
}


def mtrr_type(physical, default, ranges, bits):
    if not 32 <= bits <= 52 or not 0 <= physical < (1 << bits):
        return "UNKNOWN"
    if not default & 0x800:
        return "UC"
    if physical < 0x100000 and default & 0x400:
        return "UNKNOWN"  # Fixed-range MSRs need a separate implementation.
    address_mask = ((1 << bits) - 1) & ~0xFFF
    found = set()
    for base, mask in ranges:
        if mask & 0x800 and (physical & mask & address_mask) == (base & mask & address_mask):
            found.add(TYPES.get(base & 0xFF, "UNKNOWN"))
    if not found:
        return TYPES.get(default & 0xFF, "UNKNOWN")
    if "UC" in found:
        return "UC"
    if found == {"WB", "WT"}:
        return "WT"
    return found.pop() if len(found) == 1 else "UNKNOWN"


def pat_type(pat, entry, large=False):
    bit = 12 if large else 7
    index = ((entry >> 3) & 1) | (((entry >> 4) & 1) << 1) | (((entry >> bit) & 1) << 2)
    return TYPES.get((pat >> (index * 8)) & 0xFF, "UNKNOWN")


def effective_type(mtrr, pat, cr0):
    if cr0 & ((1 << 30) | (1 << 29)) or mtrr not in COMBINATIONS or pat not in PAT_ORDER:
        return "UNKNOWN"
    return COMBINATIONS[mtrr][PAT_ORDER.index(pat)]


def parse_capture(text):
    begin = "== rom-memory-types BEGIN schema=1 =="
    end = "== rom-memory-types END schema=1 status=PASS =="
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(end) < text.index(begin):
        raise ValueError("A single complete PASS capture is required")
    lines = text[text.index(begin) + len(begin):text.index(end)].splitlines()
    cpu, control, msrs, pages, samples = None, None, {}, [], []
    for line in lines:
        words = line.split()
        if len(words) < 2 or words[0] != "#":
            continue
        values = dict(word.split("=", 1) for word in words[2:])
        kind = words[1]
        if kind == "CPU":
            if cpu is not None:
                raise ValueError("Duplicate CPU record")
            cpu = values
        elif kind == "CONTROL":
            if control is not None:
                raise ValueError("Duplicate control record")
            control = {key: int(value, 16) for key, value in values.items()}
        elif kind == "MSR":
            index = int(values["index"], 16)
            if index in msrs:
                raise ValueError("Duplicate MSR record")
            msrs[index] = int(values["value"], 16)
        elif kind == "PAGE":
            pages.append(values)
        elif kind == "SAMPLE":
            samples.append(values)
    if cpu is None or control is None or not pages:
        raise ValueError("Missing CPU, control or page records")
    features = int(cpu["edx"], 16)
    required_features = (1 << 4) | (1 << 5) | (1 << 12) | (1 << 16)
    if features & required_features != required_features:
        raise ValueError("CPU lacks required diagnostic capabilities")
    if not 32 <= int(cpu["phys_bits"]) <= 52:
        raise ValueError("Unsupported physical address width")
    if set(control) != {"cr0", "cr3", "cr4"} or any(not 0 <= v < 2**32 for v in control.values()):
        raise ValueError("Invalid control register readback")
    if not control["cr0"] & (1 << 31) or control["cr4"] & (1 << 5):
        raise ValueError("Only paged non-PAE captures supported")
    if len(pages) != 4 or {p.get("label") for p in pages} != {"kernel", "ram", "ram-cross", "ram-cross-next"}:
        raise ValueError("Four unique diagnostic pages required")
    if len(samples) != 17 or [int(s["round"]) for s in samples] != list(range(17)):
        raise ValueError("Complete ordered rounds 0 through 16 required")
    tick_fields = {"overhead", "kernel", "ram", "cross", "table_kernel", "table_ram"}
    for sample in samples:
        if int(sample["calls"]) != 32768 or sample["checksum"] != "da090000":
            raise ValueError("Unexpected workload or checksum")
        if any(not 0 <= int(sample[key]) < 2**64 for key in tick_fields):
            raise ValueError("Invalid timestamp interval")
    required = {0xFE, 0x2FF, 0x277}
    if not required <= msrs.keys():
        raise ValueError("Missing capability/default/PAT MSRs")
    count = msrs[0xFE] & 0xFF
    if count > 16:
        raise ValueError("Unsupported variable MTRR count")
    required |= set(range(0x200, 0x200 + 2 * count))
    if not required <= msrs.keys():
        raise ValueError("Incomplete variable MTRR readback")
    ranges = [(msrs[0x200 + i * 2], msrs[0x201 + i * 2]) for i in range(count)]
    result = []
    for page in pages:
        va, pa, entry = (int(page[key], 16) for key in ("va", "pa", "entry"))
        if any(not 0 <= value < 2**32 for value in (va, pa, entry)) or page["large"] not in ("0", "1"):
            raise ValueError("Invalid page readback")
        large = page["large"] == "1"
        if not entry & 1:
            raise ValueError("Non-present measured page")
        if large:
            if not control["cr4"] & 0x10 or not entry & 0x80 or entry & 0x3FE000:
                raise ValueError("Unsupported or contradictory large-page entry")
            translated = (entry & 0xFFC00000) | (va & 0x3FFFFF)
        else:
            translated = (entry & 0xFFFFF000) | (va & 0xFFF)
        if pa != translated:
            raise ValueError("Physical address disagrees with page walk")
        mtrr = mtrr_type(pa, msrs[0x2FF], ranges, int(cpu["phys_bits"]))
        pat = pat_type(msrs[0x277], entry, large=large)
        result.append({**page, "mtrr_type": mtrr, "pat_type": pat,
                       "effective_type": effective_type(mtrr, pat, control["cr0"])})
    by_label = {page["label"]: page for page in result}
    ram = int(by_label["ram"]["va"], 16)
    if ram & 4095 or int(by_label["ram-cross"]["va"], 16) != ram + 4094 or int(by_label["ram-cross-next"]["va"], 16) != ram + 4096:
        raise ValueError("RAM control addresses disagree with diagnostic layout")
    return {"schema": 1, "cpu": cpu, "control": control, "msrs": msrs,
            "pages": result, "samples": samples,
            "limitation": "TCG timing is not physical flash latency; no game performance claim."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    print(json.dumps(parse_capture(args.capture.read_text()), indent=2))


if __name__ == "__main__":
    main()
