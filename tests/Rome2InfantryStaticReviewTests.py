import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rome2aoe2.capabilities import CAPABILITIES, conversion_capabilities  # noqa: E402


class Rome2InfantryStaticReviewTests(unittest.TestCase):
    def test_review_profile_is_frozen_hastati_oracle_configuration(self):
        profile = json.loads((ROOT / "config/render_profiles/infantry_static_review_v1.json").read_text())
        self.assertEqual(profile["status"], "VALIDATED")
        self.assertEqual(profile["camera"]["azimuth_degrees"], 112.5)
        self.assertEqual(profile["camera"]["elevation_degrees"], 18.0)
        self.assertEqual(profile["camera"]["orthographic_span_multiplier"], 1.12)
        self.assertEqual(profile["lighting"]["backend"], "rome2_exact_material_backend")

    def test_required_generic_capabilities_are_validated(self):
        result = conversion_capabilities(["DefaultMaterial", "Weighted", "WeightedDirtmap",
                                          "WeightedSkinDirtmap", "DecalDirtmap"])
        self.assertEqual({row["status"] for rows in result.values() for row in rows}, {"VALIDATED"})
        self.assertIn(("ATTACHMENT", "one_handed_blade/weapon_02"), CAPABILITIES)
        self.assertIn(("RENDER", "infantry_static_review_v1"), CAPABILITIES)

    def test_exporter_preserves_rmv_pivot_as_source_gltf_transform(self):
        source = (ROOT / "third_party/rpfm/rpfm_extensions/src/gltf/mod.rs").read_text()
        self.assertIn("translation: Some([-pivot.x, pivot.y, pivot.z])", source)
        helper = (ROOT / "tools/rome2_pack/src/main.rs").read_text()
        self.assertIn('"gltf_translation"', helper)

    def test_assembler_preserves_imported_rigid_transform(self):
        source = (ROOT / "src/blender/assemble_manifest_static.py").read_text()
        self.assertIn("source_local = mesh.matrix_basis.copy()", source)
        self.assertIn("mesh.matrix_basis = source_local", source)
        self.assertNotIn('if unit == "Rom_Principes"', source)
        self.assertNotIn('if unit == "Rom_Hastati"', source)

    def test_grip_solver_is_geometry_socket_and_class_driven(self):
        source = (ROOT / "src/blender/weapon_grip.py").read_text()
        self.assertIn("np.linalg.svd", source)
        self.assertIn("posed_right_hand_weighted_surface_to_grip_distance", source)
        self.assertIn("RMV v_pivot preserved", source)
        self.assertNotIn("roman_gladius_rotation", source)
        self.assertNotIn("Rom_Principes", source)

    def test_static_report_records_validated_source_grip(self):
        report_path = ROOT / "build/conversions/rom_principes/bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6/static-assembly-report.json"
        if not report_path.is_file():
            self.skipTest("rendered acceptance output is not present")
        report = json.loads(report_path.read_text())
        grip = report["attachments"]["melee_weapon"]["grip_solver"]
        self.assertTrue(grip["validated"])
        self.assertLess(grip["grip_axis_distance"], .001)
        self.assertLess(grip["posed_right_hand_weighted_surface_to_grip_distance"], .02)
        self.assertGreater(grip["blade_length"], grip["handle_length"] * 4)
        self.assertEqual(report["studio"]["profile"], "infantry_static_review_v1")


if __name__ == "__main__":
    unittest.main()
