#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Candidate-neutral, release-only plans for the final real-title gates.

The runner supplies a fresh process and private HDD materialization for each
plan. Firmware, disc, HDD, EEPROM, xemu, and launcher hashes belong in the job
envelope, never in these input-only route descriptions.
"""
from __future__ import annotations

from typing import Any


def step(kind: str, **kwargs: Any) -> dict[str, Any]:
    row = {
        "type": kind,
        "delayMs": 0,
        "button": None,
        "durationMs": 100,
        "name": None,
        "diagnosticId": None,
        "condition": None,
        "timeoutMs": 10_000,
        "pollIntervalMs": 100,
    }
    row.update(kwargs)
    return row


PGR2_SCENES: dict[str, tuple[str, tuple[float, float, float, float], int]] = {
    # Difference hashes cover small, static UI regions.  The values were
    # selected from independent captures of the same states so moving menu
    # backgrounds cannot advance the route and no game image is redistributed.
    "press": ("8000275773133b00", (.20, .82, .20, .06), 2),
    "create": ("00006036ae2e2604", (.50, .82, .15, .06), 2),
    "name": ("99b89b99b38ea6ae", (.20, .45, .20, .10), 5),
    "plate": ("66626a2662626262", (.40, .25, .30, .06), 2),
    "license": ("4a4a2c0a2a133662", (.60, .45, .15, .20), 3),
    "helmet": ("c3db9a9a9acacb9a", (.30, .25, .15, .10), 5),
    "main": ("eded65442813171a", (.40, .45, .30, .06), 2),
    "current": ("ada9c2c0d956646c", (.20, .78, .20, .10), 6),
    "single": ("9ece57ce7616190b", (.40, .18, .15, .10), 5),
    "series": ("a22a0001594dddd5", (.30, .65, .15, .06), 5),
    "event": ("2b0b872137cf458d", (.50, .25, .20, .14), 10),
    "car": ("1e77cb4b83938361", (.50, .45, .20, .20), 10),
    "transmission": ("739e48989cacd85c", (.40, .45, .40, .10), 6),
    "difficulty": ("84972e5797bb4c6c", (.60, .35, .20, .50), 6),
    "prerace": ("9d95999989cbc6c7", (.20, .45, .15, .06), 6),
}


def pgr2_scene(state: str, name: str, timeout_ms: int = 30_000) -> dict[str, Any]:
    fingerprint, (x, y, width, height), distance = PGR2_SCENES[state]
    return step(
        "wait_for_scene", name=name, timeoutMs=timeout_ms, pollIntervalMs=250,
        condition={
            "name": f"{name}-scene",
            "scope": "result",
            "path": f"screenshots/{name}.png",
            "imageRegion": {"x": x, "y": y, "width": width, "height": height},
            "expectedImageDHash": fingerprint,
            "maximumImageHammingDistance": distance,
        })


def halo2_scene(state: str, name: str) -> dict[str, Any]:
    scenes = {
        # The profile selector is opaque and stable.  Halo 2's main-menu
        # backdrop moves, so its bounded tolerance was measured over nine
        # independent menu captures while remaining separated from the profile
        # selector by at least 25 bits.
        "profile": ("1ded7f7f7c15346b", (.30, .35, .15, .06), 5),
        "main": ("161e321717321e16", (.30, .65, .40, .14), 16),
    }
    fingerprint, (x, y, width, height), distance = scenes[state]
    return step(
        "wait_for_scene", name=name, timeoutMs=30_000, pollIntervalMs=250,
        condition={
            "name": f"{name}-scene",
            "scope": "result",
            "path": f"screenshots/{name}.png",
            "imageRegion": {"x": x, "y": y, "width": width, "height": height},
            "expectedImageDHash": fingerprint,
            "maximumImageHammingDistance": distance,
        })


def build_pgr2_profile_create_plan() -> list[dict[str, Any]]:
    """Create a profile under the candidate BIOS and leave its HDD retained.

    This is the profile-authoring half of the cold-reload gate.  It starts from
    the pinned clean HDD, follows the route that produced the proven candidate
    profile, waits after the final confirmation so pending writes can drain,
    and makes no gameplay-performance claim.
    """
    plan = [pgr2_scene("press", "pgr2-press-start", 120_000),
            step("wait", delayMs=500),
            step("button", button="A", durationMs=25)]
    for state, name in (("create", "pgr2-create-menu"),
                        ("name", "pgr2-name-ready")):
        plan += [pgr2_scene(state, name), step("wait", delayMs=500)]
        if name == "pgr2-name-ready":
            plan.append(step("diagnostic", diagnosticId="pgr2-profile-write-before"))
        plan.append(step("button", button="A", durationMs=25))
    for state, name in (("plate", "pgr2-plate-style"),
                        ("license", "pgr2-license-plate"),
                        ("helmet", "pgr2-helmet")):
        plan += [pgr2_scene(state, name), step("wait", delayMs=500),
                 step("button", button="A", durationMs=25)]
    plan.append(pgr2_scene("main", "pgr2-created-main"))
    plan += [step("diagnostic", diagnosticId="pgr2-profile-write-after"),
             step("wait", delayMs=5_000), step("quit")]
    return plan


def build_pgr2_cold_race_plan() -> list[dict[str, Any]]:
    """Reload a candidate-authored profile and retain a 25-second race window.

    The HDD must have been authored by the same firmware and EEPROM in an
    earlier process. A accepts the current profile and each default career
    choice. The final A leaves the pre-race menu; only then does the 17-second
    loading interval begin.
    """
    plan = [pgr2_scene("press", "pgr2-press-start", 120_000),
            step("wait", delayMs=500),
            step("button", button="A", durationMs=25)]
    for state, name in (("current", "pgr2-profile-confirm"),
                        ("main", "pgr2-mode"),
                        ("single", "pgr2-car-right"),
                        ("series", "pgr2-car-confirm"),
                        ("event", "pgr2-event"),
                        ("car", "pgr2-track"),
                        ("transmission", "pgr2-options"),
                        ("difficulty", "pgr2-grid")):
        plan += [pgr2_scene(state, name), step("wait", delayMs=500),
                 step("button", button="A", durationMs=25)]
    plan += [
        pgr2_scene("prerace", "pgr2-race-confirm"),
        step("wait", delayMs=500),
        step("button", button="A", durationMs=25),
        step("wait", delayMs=17_000),
        step("screenshot", name="pgr2-race-start"),
        step("wait", delayMs=10_000),
        step("screenshot", name="pgr2-race-10s"),
        step("wait", delayMs=15_000),
        step("screenshot", name="pgr2-race-25s"),
        step("quit"),
    ]
    return plan


def build_halo2_menu_plan() -> list[dict[str, Any]]:
    """Enter Halo 2's main menu, then observe its completeness and stability."""
    return [
        step("wait", delayMs=60_000),
        step("button", button="Start", durationMs=25),
        halo2_scene("profile", "halo2-profile-select"),
        step("button", button="DPadDown", durationMs=25),
        step("wait", delayMs=1_000),
        step("button", button="A", durationMs=25),
        halo2_scene("main", "halo2-menu-entry"),
        step("wait", delayMs=15_000),
        step("screenshot", name="halo2-menu-15s"),
        step("wait", delayMs=15_000),
        step("screenshot", name="halo2-menu-30s"),
        step("quit"),
    ]


def build_doa_create_plan() -> list[dict[str, Any]]:
    """Create the first DOAXBV save with defaults and prove HDD writes occurred.

    The retained private HDD from this process is the sole input to the reload
    phase. Scene/OCR analysis rejects a route that did not reach the vacation
    menu, and block statistics reject a route that caused no HDD write.
    """
    return [
        step("wait", delayMs=50_000),
        step("screenshot", name="doa-title"),
        step("diagnostic", diagnosticId="doa-save-write-before"),
        step("button", button="Start"),
        step("wait", delayMs=4_000),
        step("screenshot", name="doa-slot-list"),
        step("button", button="A"),
        step("wait", delayMs=8_000),
        step("screenshot", name="doa-slot-selected"),
        step("button", button="A"),
        step("wait", delayMs=8_000),
        step("screenshot", name="doa-character"),
        step("button", button="A"),
        step("wait", delayMs=50_000),
        step("button", button="A"),
        step("wait", delayMs=10_000),
        step("screenshot", name="doa-vacation-menu"),
        step("diagnostic", diagnosticId="doa-save-write-after"),
        step("quit"),
    ]


def build_doa_reload_plan() -> list[dict[str, Any]]:
    """Cold launch the exact retained create-phase HDD and load its first slot."""
    return [
        step("wait", delayMs=50_000),
        step("screenshot", name="doa-reload-title"),
        step("button", button="Start"),
        step("wait", delayMs=4_000),
        step("screenshot", name="doa-reload-slots"),
        step("button", button="A"),
        step("wait", delayMs=40_000),
        step("screenshot", name="doa-slot-loaded"),
        step("quit"),
    ]
