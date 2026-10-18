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


def build_pgr2_profile_create_plan() -> list[dict[str, Any]]:
    """Create a profile under the candidate BIOS and leave its HDD retained.

    This is the profile-authoring half of the cold-reload gate.  It starts from
    the pinned clean HDD, follows the route that produced the proven candidate
    profile, waits after the final confirmation so pending writes can drain,
    and makes no gameplay-performance claim.
    """
    plan = [step("wait", delayMs=33_000), step("screenshot", name="pgr2-boot-33s")]
    for wait, button, name in (
        (0, "A", "pgr2-continue"),
        (12_000, "A", "pgr2-profile"),
        (4_000, "A", "pgr2-profile-confirm"),
        (4_000, "A", "pgr2-name-ready"),
    ):
        if wait:
            plan.append(step("wait", delayMs=wait))
        plan += [step("button", button=button), step("screenshot", name=name)]
    plan += [step("diagnostic", diagnosticId="pgr2-profile-write-before")]
    for name in ("pgr2-license-plate", "pgr2-helmet", "pgr2-created-main"):
        plan += [step("wait", delayMs=4_000), step("button", button="A"),
                 step("screenshot", name=name)]
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
    plan = [step("wait", delayMs=33_000), step("screenshot", name="pgr2-boot-33s")]
    for wait, button, name in (
        (0, "A", "pgr2-continue"),
        (12_000, "A", "pgr2-profile"),
        (4_000, "A", "pgr2-profile-confirm"),
        (4_000, "A", "pgr2-mode"),
        (4_000, "A", "pgr2-car-right"),
        (4_000, "A", "pgr2-car-confirm"),
        (4_000, "A", "pgr2-event"),
        (4_000, "A", "pgr2-track"),
        (4_000, "A", "pgr2-options"),
        (4_000, "A", "pgr2-grid"),
        (10_000, "A", "pgr2-race-confirm"),
    ):
        if wait:
            plan.append(step("wait", delayMs=wait))
        plan += [step("button", button=button), step("screenshot", name=name)]
    plan += [
        step("button", button="A"),
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
        step("wait", delayMs=45_000),
        step("button", button="Start", durationMs=25),
        step("wait", delayMs=8_000),
        step("button", button="DPadDown", durationMs=25),
        step("wait", delayMs=1_000),
        step("button", button="A", durationMs=25),
        step("wait", delayMs=10_000),
        step("screenshot", name="halo2-menu-entry"),
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
