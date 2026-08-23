import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rome2aoe2.production import (PROFILE, production_identity,
                                  resolve_production_profile)
from rome2aoe2.native_assembly import static_assembly_identity


class Rome2ProductionVisualPolicyTests(unittest.TestCase):
    def test_v2_lighting_is_world_fixed_fill_and_keeps_shadow_contract(self):
        profile=json.loads((ROOT/"config/render_profiles/aoe2_infantry_animation_production_v2.json").read_text())
        self.assertEqual(profile["name"], "aoe2-infantry-animation-production-v2")
        self.assertEqual(profile["main_illumination"]["captured_environment_yaw_degrees"], 0.0)
        self.assertEqual(profile["main_illumination"]["readability_fill_linear"], 0.6)
        self.assertFalse(profile["main_illumination"]["material_equations_modified"])
        self.assertFalse(profile["shadow"]["modified"])

    def test_v1_is_addressable_and_v2_is_canonical(self):
        v1 = resolve_production_profile()
        v2 = resolve_production_profile("aoe2-infantry-animation-production-v2")
        self.assertEqual(PROFILE, v1["name"])
        self.assertEqual(0.0, v1["main_illumination"]["readability_fill_linear"])
        self.assertEqual("aoe2-infantry-animation-production-v2", v2["name"])
        self.assertNotEqual(v1["name"], v2["name"])

    def test_exact_backend_diagnostic_options_preserve_v1_defaults(self):
        source=(ROOT/"src/blender/render_hastati_runtime_parity.py").read_text()
        self.assertIn("illumination_yaw_offset_degrees=0.0", source)
        self.assertIn("readability_fill=0.0", source)
        self.assertIn("readability_diff=D*np.float32(readability_fill)", source)
        self.assertIn("diffuse_lighting=ambient_diff+direct_diff+readability_diff", source)
        self.assertIn("skin_direct_spec+readability_diff", source)

    def test_normal_production_passes_profile_lighting_to_exact_backend(self):
        api = (ROOT/"rome2aoe2/production.py").read_text()
        renderer = (ROOT/"src/blender/render_manifest_native_production.py").read_text()
        exact = (ROOT/"src/blender/assemble_manifest_static.py").read_text()
        self.assertIn('"--profile-name", profile["name"]', api)
        self.assertIn('profile=production_profile(a.profile_name)', renderer)
        self.assertIn('readability_fill=illumination["readability_fill_linear"]', renderer)
        self.assertIn("readability_fill=readability_fill", exact)
        self.assertNotIn("render_corrected_visual_proof", api + renderer)

    def test_full_frame_weapon_solver_never_invents_anatomical_roll(self):
        source=(ROOT/"src/blender/weapon_grip.py").read_text()
        self.assertIn("lateral_axis_local", source)
        self.assertIn("flat_axis_local", source)
        self.assertNotIn("rotation_difference", source)
        self.assertNotIn("Rom_Principes", source)
        self.assertNotIn("sws_sync_atk_005", source)
        self.assertIn('"rotation_correction": None', source)

    def test_cache_versions_separate_old_weapon_transform(self):
        source=(ROOT/"src/blender/weapon_grip.py").read_text()
        self.assertIn('"v2_full_source_frame"', source)
        profile=json.loads((ROOT/"config/render_profiles/aoe2_infantry_animation_production_v2.json").read_text())
        self.assertIn("profile and attachment capability versions", profile["cache_policy"])

    def test_v1_and_v2_production_identities_are_distinct(self):
        record = {"resolved_asset": "fixture.anim", "asset_sha256": "a" * 64}
        v1 = production_identity("b" * 64, "idle", record)
        v2 = production_identity("b" * 64, "idle", record,
                                 "aoe2-infantry-animation-production-v2")
        self.assertNotEqual(v1, v2)

    def test_v1_and_v2_static_attachment_caches_are_distinct(self):
        manifest = {"schema_version": 1, "components": {}}
        v1 = static_assembly_identity(manifest)
        v2 = static_assembly_identity(manifest, "one_handed_blade_v2_full_source_frame")
        self.assertNotEqual(v1, v2)

    def test_weapon_correction_is_assembly_local_and_not_per_frame(self):
        static = (ROOT/"src/blender/assemble_manifest_static.py").read_text()
        native = (ROOT/"src/blender/assemble_native_basis_animation.py").read_text()
        weapon = (ROOT/"src/blender/weapon_grip.py").read_text()
        self.assertEqual(1, static.count("solve_weapon_grip("))
        self.assertNotIn("solve_weapon_grip", native)
        self.assertNotIn("frame_set", weapon)
        self.assertIn("frame_orthogonality_error", weapon)
        self.assertIn("frame_handedness", weapon)
        self.assertIn("action_fingerprint_preserved", native)
        self.assertIn('doc["category"] in {"walk","death"}', native)
        for forbidden in ("weapon_full_frame_local_transform", "roman_gladius_rotation",
                          "Rom_Principes"):
            self.assertNotIn(forbidden, static + native + weapon)


if __name__ == "__main__":
    unittest.main()
