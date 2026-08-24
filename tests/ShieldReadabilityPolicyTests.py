import inspect
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rome2aoe2.production import production_identity, resolve_production_profile
from rome2aoe2.shield_readability import (
    DIFFUSE_DOMINANT_CALIBRATION,
    classify_material_response,
    resolve_shield_readability,
)

V3 = "aoe2-infantry-animation-production-v3-weapon-forward"
V4 = "aoe2-infantry-animation-production-v4-shield-readability"
SCUTUM = {"specular_luminance": 0.1099, "smoothness": 0.1358, "reflectivity": 0.1150}
CELTIC = {"specular_luminance": 0.0614, "smoothness": 0.0837, "reflectivity": 0.1675}
HOPLON = {"specular_luminance": 0.1503, "smoothness": 0.1155, "reflectivity": 0.1780}


class ShieldReadabilityPolicyTests(unittest.TestCase):
    def test_role_alone_does_not_enable_floor(self):
        result = resolve_shield_readability("shield", SCUTUM)
        self.assertFalse(result["enabled"])
        self.assertEqual("none", result["treatment"])

    def test_diffuse_response_and_direct_diffuse_collapse_enable_calibration(self):
        for response in (SCUTUM, CELTIC):
            result = resolve_shield_readability(
                "shield", response, dark_tail_cause="direct_diffuse_collapse")
            self.assertTrue(result["enabled"])
            self.assertEqual(DIFFUSE_DOMINANT_CALIBRATION["floor"], result["floor"])
            self.assertEqual(DIFFUSE_DOMINANT_CALIBRATION["transition_width"], result["transition_width"])

    def test_mixed_and_reflective_responses_default_to_none(self):
        mixed = {"specular_luminance": 0.135, "smoothness": 0.12, "reflectivity": 0.14}
        self.assertEqual("mixed", classify_material_response(mixed))
        self.assertFalse(resolve_shield_readability(
            "shield", mixed, "direct_diffuse_collapse")["enabled"])
        self.assertEqual("strongly_specular_reflective", classify_material_response(HOPLON))
        self.assertFalse(resolve_shield_readability(
            "shield", HOPLON, "direct_diffuse_collapse")["enabled"])

    def test_non_shield_pixels_never_enable_including_melee_weapon(self):
        for role in ("body", "skin", "weighted_armour", "melee_weapon"):
            self.assertFalse(resolve_shield_readability(
                role, SCUTUM, "direct_diffuse_collapse")["enabled"])

    def test_dispatch_has_no_asset_faction_or_unit_name_conditions(self):
        source = inspect.getsource(sys.modules[resolve_shield_readability.__module__]).casefold()
        for forbidden in ("scutum", "hoplon", "principes", "roman_", "celtic", "hastati"):
            self.assertNotIn(forbidden, source)

    def test_v4_profile_is_versioned_and_v3_remains_unchanged(self):
        v3 = resolve_production_profile(V3)
        v4 = resolve_production_profile(V4)
        self.assertEqual(3, v3["version"])
        self.assertNotIn("render_capabilities", v3)
        capability = v4["render_capabilities"]["shield_readability"]
        self.assertEqual("shield_readability_v1", capability["capability"])
        self.assertEqual(2.7, capability["response_dispatch"]["diffuse_dominant"]["floor"])
        self.assertEqual(0.15, capability["response_dispatch"]["diffuse_dominant"]["transition_width"])
        self.assertEqual("none", capability["response_dispatch"]["mixed"]["treatment"])
        self.assertEqual("none", capability["response_dispatch"]["strongly_specular_reflective"]["treatment"])
        self.assertEqual(v3["main_illumination"], v4["main_illumination"])
        self.assertEqual(v3["attachment_capabilities"], v4["attachment_capabilities"])

    def test_new_profile_has_separate_production_identity(self):
        record = {"resolved_asset": "asset.anim", "asset_sha256": "a" * 64}
        old = production_identity("b" * 64, "idle", record, V3)
        new = production_identity("b" * 64, "idle", record, V4)
        self.assertNotEqual(old, new)

    def test_runtime_floor_is_pre_albedo_and_does_not_mutate_fsr(self):
        source = (ROOT / "src/blender/render_hastati_runtime_parity.py").read_text()
        self.assertIn("floor_policies.append((shield_pixels", source)
        self.assertIn("equipment_shadow_fill[policy_pixels]=D[policy_pixels]*delta", source)
        self.assertIn("diffuse_lighting+=equipment_shadow_fill", source)
        self.assertNotIn("F[equipment_pixels]=", source)
        self.assertNotIn("S[equipment_pixels]=", source)
        self.assertNotIn("R[equipment_pixels]=", source)

    def test_weapon_metric_uses_visible_semantic_ownership(self):
        source = (ROOT / "src/blender/diagnose_native_production_lighting.py").read_text()
        self.assertIn('semantic_roles[..., 1] > .5', source)
        self.assertNotIn('weapon_mask = component_mask(scene, texture_root, "melee_weapon")', source)


if __name__ == "__main__":
    unittest.main()
