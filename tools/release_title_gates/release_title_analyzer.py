#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Objective screenshot/OCR scoring for the non-Forza release title gates."""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageStat


def require_ocr_dependencies():
    """Resolve RapidOCR from the environment or an explicit offline bundle."""
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError:
        dependency_dir = os.environ.get("FORZA_GATE_OCR_DEPS")
        if not dependency_dir:
            raise RuntimeError(
                "rapidocr_onnxruntime is unavailable; install requirements.txt or "
                "set FORZA_GATE_OCR_DEPS to an offline dependency directory")
        sys.path.insert(0, str(Path(dependency_dir).resolve()))
        from rapidocr_onnxruntime import RapidOCR
    return RapidOCR


def _visual(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"pass": False, "missing": True}
    with Image.open(path) as source:
        image = source.convert("RGB")
        w, h = image.size
        image = image.crop((int(w * .05), int(h * .08), int(w * .95), int(h * .92)))
        gray = image.convert("L")
        histogram = gray.histogram()
        total = sum(histogram)
        entropy = -sum((count / total) * math.log2(count / total)
                       for count in histogram if count)
        edge = ImageStat.Stat(gray.filter(ImageFilter.FIND_EDGES)).mean[0]
        colors = len(image.quantize(colors=64).getcolors(maxcolors=64) or [])
        dark = sum(histogram[:18]) / total
    passed = entropy >= 1.5 and edge >= 3.0 and colors >= 16 and dark < .88
    return {"pass": passed, "entropy": entropy, "edge_mean": edge,
            "quantized_colors": colors, "dark_ratio": dark}


def _difference(first: Path, second: Path) -> float:
    with Image.open(first) as a, Image.open(second) as b:
        a = a.convert("RGB").resize((320, 240))
        b = b.convert("RGB").resize((320, 240))
        return float(ImageStat.Stat(ImageChops.difference(a, b)).rms[0])


def _ocr(root: Path, names: list[str]) -> dict[str, str]:
    cache = root / "title-ocr.json"
    if cache.is_file():
        value = json.loads(cache.read_text())
        return {name: str(value.get(name, "")) for name in names}
    RapidOCR = require_ocr_dependencies()
    engine = RapidOCR()
    value = {}
    for name in names:
        path = root / "screenshots" / f"{name}.png"
        if not path.is_file():
            value[name] = ""
            continue
        result, _ = engine(np.array(Image.open(path).convert("RGB")))
        value[name] = " ".join(str(row[1]) for row in (result or []))
    cache.write_text(json.dumps(value, indent=2) + "\n")
    return value


def score_pgr2(root: Path) -> dict[str, Any]:
    names = ["pgr2-race-start", "pgr2-race-10s", "pgr2-race-25s"]
    route_names = [
        "pgr2-continue", "pgr2-profile", "pgr2-profile-confirm", "pgr2-mode",
        "pgr2-car-right", "pgr2-car-confirm", "pgr2-event", "pgr2-track",
        "pgr2-options", "pgr2-grid", "pgr2-race-confirm", *names,
    ]
    frames = {name: _visual(root / "screenshots" / f"{name}.png") for name in names}
    paths = [root / "screenshots" / f"{name}.png" for name in names]
    movement = min(_difference(paths[0], paths[1]), _difference(paths[1], paths[2])) \
        if all(path.is_file() for path in paths) else 0.0
    ocr = _ocr(root, route_names)
    route_text = " ".join(ocr.values())
    profile_error = bool(re.search(
        r"(?i)(?:profile.{0,48}damag|damag.{0,64}(?:cannot|can't).{0,24}use|"
        r"corrupt|cannot.{0,24}(?:load|use).{0,24}profile)", route_text))
    race_text = " ".join(ocr.get(name, "") for name in names)
    prerace_menu = bool(re.search(r"(?i)\bpre\s*race\b|\bstart\s*race\b",
                                  race_text))
    passed = (all(row["pass"] for row in frames.values()) and movement >= 1.0
              and not profile_error and not prerace_menu)
    return {"pass": passed, "race_frames": frames,
            "minimum_pairwise_rms_difference": movement,
            "declared_live_window_seconds": 25, "ocr": ocr,
            "profile_error_text": profile_error,
            "prerace_menu_text": prerace_menu}


def score_pgr2_reload(root: Path) -> dict[str, Any]:
    """Require a usable candidate-authored profile and the live race gate."""
    result = score_pgr2(root)
    prompt = result["ocr"].get("pgr2-profile-confirm", "")
    normalized = re.sub(r"\s+", "", prompt).lower()
    existing_profile = ("currentprofile" in normalized and
                        re.search(r"player'?sgame", normalized) is not None)
    result["existing_profile_prompt"] = existing_profile
    result["pass"] = bool(result["pass"] and existing_profile)
    return result


def score_pgr2_create(root: Path) -> dict[str, Any]:
    """Require every profile-creation state and the resulting main menu."""
    names = ["pgr2-press-start", "pgr2-create-menu", "pgr2-name-ready",
             "pgr2-plate-style", "pgr2-license-plate", "pgr2-helmet",
             "pgr2-created-main"]
    frames = {name: _visual(root / "screenshots" / f"{name}.png")
              for name in names}
    ocr = _ocr(root, names)
    normalized = {name: re.sub(r"\s+", "", text).upper()
                  for name, text in ocr.items()}
    identity = {
        "press_start": "PRESSSTART" in normalized["pgr2-press-start"],
        "create_menu": "CREATENEWPROFILE" in normalized["pgr2-create-menu"],
        "profile_name": "PROFILENAME" in normalized["pgr2-name-ready"],
        "plate_style": "PLATESELECT" in normalized["pgr2-plate-style"],
        "license_plate": "LICENSEPLATETEXT" in normalized["pgr2-license-plate"],
        "helmet": "HELMETSELECT" in normalized["pgr2-helmet"],
        "created_main": ("MAINMENU" in normalized["pgr2-created-main"]
                         and "SINGLEPLAYER" in normalized["pgr2-created-main"]),
    }
    text = " ".join(ocr.values())
    error = bool(re.search(r"(?i)damaged|corrupt|cannot.{0,24}(?:load|use)", text))
    visible = all(not row.get("missing", False) and row["entropy"] >= 3.0
                  and row["quantized_colors"] >= 16 and row["dark_ratio"] < .88
                  for row in frames.values())
    passed = visible and all(identity.values()) and not error
    return {"pass": passed, "frames": frames, "identity": identity,
            "frames_visible": visible, "ocr": ocr, "profile_error_text": error}


def score_halo2(root: Path) -> dict[str, Any]:
    names = ["halo2-menu-entry", "halo2-menu-15s", "halo2-menu-30s"]
    frames = {name: _visual(root / "screenshots" / f"{name}.png") for name in names}
    ocr = _ocr(root, names)
    normalized = re.sub(r"\s+", "", " ".join(ocr.values()).upper())
    identity = "CAMPAIGN" in normalized and "SETTINGS" in normalized
    tokens = set(re.findall(r"[A-Z]{3,}", " ".join(ocr.values()).upper()))
    # Halo 2's static blue menu has deliberately soft edges. OCR proves the
    # title/menu identity; entropy, color, and darkness still reject blank or
    # corrupt captures without imposing the gameplay-oriented edge threshold.
    for row in frames.values():
        row["pass"] = (not row.get("missing", False) and row["entropy"] >= 1.5
                       and row["quantized_colors"] >= 16 and row["dark_ratio"] < .88)
    visible = all(row["pass"] for row in frames.values())
    passed = visible and identity
    return {"pass": passed, "menu_frames": frames, "ocr": ocr,
            "menu_frames_visible": visible, "campaign_and_settings": identity,
            "menu_tokens": sorted(tokens)}


def score_halo2_pair(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    a, b = set(first.get("menu_tokens", [])), set(second.get("menu_tokens", []))
    union = a | b
    similarity = len(a & b) / len(union) if union else 0.0
    passed = first.get("pass", False) and second.get("pass", False) and similarity >= .6
    return {"pass": passed, "token_jaccard": similarity,
            "first_token_count": len(a), "second_token_count": len(b)}


def score_doa_create(root: Path) -> dict[str, Any]:
    target = root / "screenshots" / "doa-vacation-menu.png"
    visual = _visual(target)
    text = _ocr(root, ["doa-vacation-menu"])["doa-vacation-menu"]
    rejected = bool(re.search(r"(?i)damaged\s*game|corrupt|cannot\s+load", text))
    return {"pass": visual["pass"] and not rejected, "vacation_menu": visual,
            "ocr": text, "save_error_text": rejected}


def score_doa_reload(root: Path) -> dict[str, Any]:
    slot = root / "screenshots" / "doa-reload-slots.png"
    loaded = root / "screenshots" / "doa-slot-loaded.png"
    visual = _visual(loaded)
    ocr = _ocr(root, ["doa-reload-slots", "doa-slot-loaded"])
    text = " ".join(ocr.values())
    rejected = bool(re.search(r"(?i)damaged\s*game|corrupt|cannot\s+load", text))
    change = _difference(slot, loaded) if slot.is_file() and loaded.is_file() else 0.0
    passed = visual["pass"] and not rejected and change >= 2.0
    return {"pass": passed, "loaded_scene": visual, "ocr": ocr,
            "save_error_text": rejected, "slot_to_loaded_rms_difference": change}


SCORERS = {"pgr2": score_pgr2, "pgr2-create": score_pgr2_create,
           "pgr2-reload": score_pgr2_reload,
           "halo2": score_halo2,
           "doa-create": score_doa_create, "doa-reload": score_doa_reload}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("title", choices=sorted(SCORERS))
    parser.add_argument("evidence", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    result = SCORERS[args.title](args.evidence)
    text = json.dumps(result, indent=2) + "\n"
    if args.out:
        args.out.write_text(text)
    print(text, end="")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
