# SPDX-License-Identifier: GPL-2.0-or-later
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from release_title_routes import (
    build_doa_create_plan,
    build_doa_reload_plan,
    build_halo2_menu_plan,
    build_pgr2_profile_create_plan,
    build_pgr2_cold_race_plan,
)


class ReleaseTitleRouteTests(unittest.TestCase):
    def test_pgr2_create_route_authors_candidate_profile_without_claiming_race(self):
        plan = build_pgr2_profile_create_plan()
        self.assertEqual(plan[-1]["type"], "quit")
        self.assertIn("LStickRight", [row.get("button") for row in plan])
        self.assertIn("pgr2-profile-confirm", [row.get("name") for row in plan])
        self.assertIn("pgr2-race-confirm", [row.get("name") for row in plan])
        self.assertNotIn("pgr2-race-25s", [row.get("name") for row in plan])
        self.assertLess(sum(row.get("delayMs", 0) for row in plan), 180_000)

    def test_pgr2_cold_route_is_bounded_and_keeps_25_second_race_window(self):
        plan = build_pgr2_cold_race_plan()
        self.assertEqual(plan[-1]["type"], "quit")
        self.assertEqual(sum(row.get("delayMs", 0) for row in plan), 129_000)
        self.assertIn("pgr2-race-start", [row.get("name") for row in plan])
        self.assertIn("pgr2-race-25s", [row.get("name") for row in plan])
        start = next(i for i, row in enumerate(plan) if row.get("name") == "pgr2-race-start")
        end = next(i for i, row in enumerate(plan) if row.get("name") == "pgr2-race-25s")
        self.assertEqual(sum(row.get("delayMs", 0) for row in plan[start:end + 1]), 25_000)
        prerace = next(i for i, row in enumerate(plan)
                       if row.get("name") == "pgr2-race-confirm")
        self.assertEqual(plan[prerace + 1]["type"], "button")
        self.assertEqual(plan[prerace + 1]["button"], "A")
        self.assertFalse(any(row.get("button") == "LStickRight" for row in plan))
        self.assertFalse(any(row["type"] == "diagnostic" for row in plan))

    def test_halo2_menu_route_has_three_cold_launch_observations_and_no_input(self):
        plan = build_halo2_menu_plan()
        shots = [row["name"] for row in plan if row["type"] == "screenshot"]
        self.assertEqual(shots, ["halo2-menu-45s", "halo2-menu-60s", "halo2-menu-75s"])
        self.assertFalse(any(row["type"] in ("button", "diagnostic") for row in plan))
        self.assertEqual(plan[-1]["type"], "quit")

    def test_doa_create_and_reload_are_separate_fresh_process_plans(self):
        create = build_doa_create_plan()
        reload = build_doa_reload_plan()
        self.assertEqual(create[-1]["type"], "quit")
        self.assertEqual(reload[-1]["type"], "quit")
        self.assertIn("doa-save-write-before", [x.get("diagnosticId") for x in create])
        self.assertIn("doa-save-write-after", [x.get("diagnosticId") for x in create])
        self.assertIn("doa-slot-loaded", [x.get("name") for x in reload])
        self.assertLess(sum(x.get("delayMs", 0) for x in create), 240_000)
        self.assertLess(sum(x.get("delayMs", 0) for x in reload), 180_000)


if __name__ == "__main__":
    unittest.main()
