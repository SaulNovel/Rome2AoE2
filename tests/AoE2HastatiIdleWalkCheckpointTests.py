"""Regression checks for the approved no-player-colour idle/walk package."""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SLD = ROOT / "src/aoe2/generate_hastati_animation_sld.py"
PACKAGE = ROOT / "src/aoe2/package_hastati_idle_walk_sld.py"
BUILD = ROOT / "scripts/build_hastati_native_walk_test.ps1"
INSTALL = ROOT / "scripts/install_hastati_test.ps1"


class IdleWalkCheckpointTests(unittest.TestCase):
    def test_walk_sld_is_main_plus_shadow_without_player_colour(self):
        text = SLD.read_text(encoding="utf-8")
        self.assertIn("LAYER_MAIN | LAYER_SHADOW", text)
        self.assertIn('"player_colour": False', text)
        self.assertNotIn("LAYER_PLAYERCOLOR", text)

    def test_package_keeps_idle_and_walk_as_distinct_graphics(self):
        text = PACKAGE.read_text(encoding="utf-8")
        self.assertIn("clone.standing_sprite_id1 = clone.standing_sprite_id2 = idle.id", text)
        self.assertIn("clone.walking_graphic_id = walk.id", text)
        self.assertIn('"sws_walk_162_cm"', text)
        self.assertIn("args.walk_cycle_duration / 23", text)

    def test_build_uses_native_directxtex_sld_route(self):
        text = BUILD.read_text(encoding="utf-8")
        self.assertIn("generate_hastati_animation_sld.py", text)
        self.assertIn("package_hastati_idle_walk_sld.py", text)
        self.assertIn("directxtex-may2026\\texconv.exe", text)
        self.assertNotIn("smx", text.lower())

    def test_installer_requires_both_idle_and_walk_zoom_pairs(self):
        text = INSTALL.read_text(encoding="utf-8")
        for stem in ("hastati_test_x1.sld", "hastati_test_x2.sld",
                     "hastati_walk_x1.sld", "hastati_walk_x2.sld"):
            self.assertIn(stem, text)


if __name__ == "__main__":
    unittest.main()
