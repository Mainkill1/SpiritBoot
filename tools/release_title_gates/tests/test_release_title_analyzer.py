import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from release_title_analyzer import (score_doa_reload, score_halo2,
                                    score_halo2_pair, score_pgr2,
                                    score_pgr2_reload)


class ReleaseTitleAnalyzerTests(unittest.TestCase):
    def _root(self, td):
        root = Path(td)
        (root / "screenshots").mkdir()
        return root

    def _image(self, root, name, shift=0):
        rng = np.random.default_rng(1234 + shift)
        pixels = rng.integers(24, 232, size=(240, 320, 3), dtype=np.uint8)
        Image.fromarray(pixels).save(root / "screenshots" / f"{name}.png")

    def test_pgr2_requires_three_complete_changing_race_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            for index, name in enumerate(("pgr2-race-start", "pgr2-race-10s",
                                          "pgr2-race-25s")):
                self._image(root, name, index)
            (root / "title-ocr.json").write_text("{}\n")
            self.assertTrue(score_pgr2(root)["pass"])
            (root / "screenshots" / "pgr2-race-25s.png").unlink()
            self.assertFalse(score_pgr2(root)["pass"])

    def test_pgr2_rejects_a_damaged_profile_dialog_before_the_race(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            for index, name in enumerate(("pgr2-race-start", "pgr2-race-10s",
                                          "pgr2-race-25s")):
                self._image(root, name, index)
            (root / "title-ocr.json").write_text(json.dumps({
                "pgr2-mode": "The profile 'Player' is damaged and cannot be used.",
                "pgr2-race-start": "",
                "pgr2-race-10s": "",
                "pgr2-race-25s": "",
            }))
            score = score_pgr2(root)
            self.assertFalse(score["pass"])
            self.assertTrue(score["profile_error_text"])

    def test_pgr2_rejects_animated_prerace_menu_frames(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            for index, name in enumerate(("pgr2-race-start", "pgr2-race-10s",
                                          "pgr2-race-25s")):
                self._image(root, name, index)
            (root / "title-ocr.json").write_text(json.dumps({
                "pgr2-race-start": "PRERACE Start Race",
                "pgr2-race-10s": "PRERACE Start Race",
                "pgr2-race-25s": "PRERACE Start Race",
            }))
            score = score_pgr2(root)
            self.assertFalse(score["pass"])
            self.assertTrue(score["prerace_menu_text"])

    def test_pgr2_reload_requires_the_existing_profile_prompt(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            for index, name in enumerate(("pgr2-race-start", "pgr2-race-10s",
                                          "pgr2-race-25s")):
                self._image(root, name, index)
            (root / "title-ocr.json").write_text(json.dumps({
                "pgr2-profile-confirm": "Use the current profile. Start Player's Game",
                "pgr2-race-start": "",
                "pgr2-race-10s": "",
                "pgr2-race-25s": "",
            }))
            self.assertTrue(score_pgr2_reload(root)["pass"])
            (root / "title-ocr.json").write_text(json.dumps({
                "pgr2-profile-confirm": "Create New Profile",
                "pgr2-race-start": "",
                "pgr2-race-10s": "",
                "pgr2-race-25s": "",
            }))
            self.assertFalse(score_pgr2_reload(root)["pass"])

    def test_halo2_requires_complete_identity_and_repeat_stability(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            names = ["halo2-menu-45s", "halo2-menu-60s", "halo2-menu-75s"]
            for index, name in enumerate(names):
                self._image(root, name, index)
            (root / "title-ocr.json").write_text(json.dumps({
                name: "CAMPAIGN SETTINGS MULTIPLAYER PROFILES" for name in names
            }))
            score = score_halo2(root)
            self.assertTrue(score["pass"])
            self.assertTrue(score_halo2_pair(score, score)["pass"])
            broken = dict(score, menu_tokens=["UNRELATED", "WORDS"])
            self.assertFalse(score_halo2_pair(score, broken)["pass"])

    def test_doa_reload_rejects_damaged_game(self):
        with tempfile.TemporaryDirectory() as td:
            root = self._root(td)
            self._image(root, "doa-reload-slots", 0)
            self._image(root, "doa-slot-loaded", 1)
            (root / "title-ocr.json").write_text(json.dumps({
                "doa-reload-slots": "SLOT 1", "doa-slot-loaded": "VACATION"
            }))
            self.assertTrue(score_doa_reload(root)["pass"])
            (root / "title-ocr.json").write_text(json.dumps({
                "doa-reload-slots": "DAMAGED GAME", "doa-slot-loaded": ""
            }))
            self.assertFalse(score_doa_reload(root)["pass"])


if __name__ == "__main__":
    unittest.main()
