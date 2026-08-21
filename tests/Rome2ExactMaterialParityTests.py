import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ExactMaterialParityTests(unittest.TestCase):
    def test_shared_asset_harness_uses_required_materials(self):
        source = (ROOT / "src/blender/render_shared_material_parity.py").read_text(encoding="utf-8")
        for material in ("roman_body1", "roman_1_head", "roman_1_sandals",
                         "roman_1_eyes_teeth", "roman_early_scutum_lod1",
                         "roman_gladius_lod1", "roman_pilum_light_lod1"):
            self.assertIn(material, source)

    def test_oracle_and_generic_shared_outputs_are_pixel_identical(self):
        report = json.loads((ROOT / "build/validation/rome2aoe2/shared-material-parity/report.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(4, len(report["records"]))
        for row in report["records"]:
            self.assertGreater(row["legacy_maximum_absolute_rgb_difference"], 0.0)
            self.assertEqual(0.0, row["mean_absolute_rgb_difference"])
            self.assertEqual(0.0, row["maximum_absolute_rgb_difference"])

    def test_exact_backend_retains_frozen_oracle_equations(self):
        runtime = (ROOT / "src/blender/render_hastati_runtime_parity.py").read_text(encoding="utf-8")
        preparation = (ROOT / "src/rome2/runtime_material_preparation.py").read_text(encoding="utf-8")
        self.assertIn("prepare_weighted_skin_dirtmap", runtime)
        self.assertIn("prepare_decal_dirtmap", runtime)
        self.assertIn("prepare_weighted_dirtmap", runtime)
        self.assertIn("shield_faction_colours", runtime)
        self.assertIn("colours[[0, 2, 1]]", preparation)
        self.assertIn("tx*T + ty*B + tz*N", preparation)
        self.assertIn('"test_black" not in', runtime)


if __name__ == "__main__":
    unittest.main()
