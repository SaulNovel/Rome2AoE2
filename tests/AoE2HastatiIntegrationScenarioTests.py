"""Focused tests for the complete 15-vs-15 Hastati integration milestone."""

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src/aoe2/generate_hastati_integration_scenario.py"
VERIFY = ROOT / "src/aoe2/verify_hastati_integration_install.py"
INSTALL = ROOT / "scripts/build_and_install_hastati_integration_test.ps1"


class HastatiIntegrationScenarioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("hastati_integration_scenario", MODULE)
        cls.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.module
        spec.loader.exec_module(cls.module)

    def test_layout_is_fifteen_per_player_in_three_formations(self):
        placements = self.module.placements()
        self.assertEqual(30, len(placements))
        for player in (1, 2):
            owned = [item for item in placements if item["player"] == player]
            self.assertEqual(15, len(owned))
            self.assertEqual({1, 2, 3}, {item["group"] for item in owned})
            self.assertEqual({2081}, {item["unit_id"] for item in owned})

    def test_layout_has_multiple_facings_and_clear_opposing_sides(self):
        placements = self.module.placements()
        self.assertGreaterEqual(len({item["rotation"] for item in placements}), 5)
        p1_x = [item["x"] for item in placements if item["player"] == 1]
        p2_x = [item["x"] for item in placements if item["player"] == 2]
        self.assertLess(max(p1_x), min(p2_x))

    def test_verifier_freezes_dat_assets_and_exact_install_paths(self):
        text = VERIFY.read_text(encoding="utf-8")
        self.assertIn('{"idle": 17068, "walk": 17069, "attack": 17070, "death": 17071}', text)
        self.assertIn("unit.dead_unit_id != 152", text)
        self.assertIn("for zoom in (\"x1\", \"x2\")", text)
        self.assertIn("installed_hash != sha256(source)", text)
        self.assertIn("Rome2AoE2 Hastati Dev Test", text)
        self.assertIn("Rome2AoE2HastatiDevTest.aoe2scenario", text)

    def test_install_rejects_any_preexisting_asset_hash_change(self):
        text = INSTALL.read_text(encoding="utf-8")
        self.assertIn("$before[$name]", text)
        self.assertIn("Approved installed asset hash changed", text)
        self.assertNotIn("build_hastati_native", text)
        self.assertNotIn("generate_hastati_animation_sld", text)


if __name__ == "__main__":
    unittest.main()
