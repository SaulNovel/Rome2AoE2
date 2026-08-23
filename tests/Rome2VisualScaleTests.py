import io
import json
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rome2aoe2.cli import choose_visual_scale
from rome2aoe2.conversion import load_and_validate_manifest, manifest_digest
from rome2aoe2.errors import ConverterError, ErrorCode
from rome2aoe2.native_assembly import static_assembly_identity
from rome2aoe2.production import production_identity
from rome2aoe2.visual_scale import (
    CANONICAL_ORTHOGRAPHIC_SCALE,
    VISUAL_SCALE_DEFAULT,
    VISUAL_SCALE_MAX,
    VISUAL_SCALE_MIN,
    appearance_record,
    canvas_edge_contact,
    confirm_canvas_bounds,
    effective_orthographic_scale,
    outside_alpha_metrics,
    overscan_camera,
    validate_canvas_bounds,
    validate_visual_scale,
    visual_scale_from_manifest,
)


class Rome2VisualScaleTests(unittest.TestCase):
    def test_range_boundaries_and_default(self):
        self.assertEqual(.9, validate_visual_scale(.9))
        self.assertEqual(1.0, validate_visual_scale(1.0))
        self.assertEqual(1.1, validate_visual_scale(1.1))
        self.assertEqual(1.0, visual_scale_from_manifest({}))
        self.assertEqual((.9, 1.1, 1.0),
                         (VISUAL_SCALE_MIN, VISUAL_SCALE_MAX, VISUAL_SCALE_DEFAULT))

    def test_invalid_values_are_structured_and_never_clamped(self):
        for value in (.899999, 1.100001, 0, -1, math.nan, math.inf, -math.inf, "1.0", True):
            with self.subTest(value=value), self.assertRaises(ConverterError) as caught:
                validate_visual_scale(value)
            self.assertEqual(ErrorCode.VISUAL_SCALE_OUT_OF_RANGE, caught.exception.code)
            self.assertEqual(.9, caught.exception.context["minimum"])
            self.assertEqual(1.1, caught.exception.context["maximum"])
            self.assertIn("requested", caught.exception.context)

    def test_manifest_record_is_numeric_stable_and_deterministic(self):
        manifest = {"appearance": appearance_record(1.04, explicit=True)}
        encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":"))
        reloaded = json.loads(encoded)
        self.assertEqual(1.04, visual_scale_from_manifest(reloaded))
        self.assertEqual("explicit", reloaded["appearance"]["visual_scale"]["mode"])
        self.assertEqual(manifest_digest(manifest), manifest_digest(reloaded))

    def test_frozen_manifest_missing_field_resolves_to_exact_baseline(self):
        manifest = json.loads((ROOT/"config/manifests/rom_principes-explicit-animations-v2.json").read_text())
        self.assertNotIn("appearance", manifest)
        self.assertEqual(1.0, visual_scale_from_manifest(manifest))
        loaded = load_and_validate_manifest(
            ROOT/"config/manifests/rom_principes-explicit-animations-v2.json")
        self.assertEqual(1.0, visual_scale_from_manifest(loaded.manifest))

    def test_camera_equation_and_image_space_relationship(self):
        baseline = effective_orthographic_scale(1.0)
        self.assertEqual(CANONICAL_ORTHOGRAPHIC_SCALE, baseline)
        self.assertAlmostEqual(CANONICAL_ORTHOGRAPHIC_SCALE/1.04,
                               effective_orthographic_scale(1.04), places=14)
        self.assertAlmostEqual(1.04, baseline/effective_orthographic_scale(1.04), places=14)
        self.assertAlmostEqual(.96, baseline/effective_orthographic_scale(.96), places=14)

    def test_production_identity_varies_but_native_identity_does_not(self):
        record = {"resolved_asset": "fixture.anim", "asset_sha256": "a"*64}
        identities = {production_identity("b"*64, "idle", record,
                                          "aoe2-infantry-animation-production-v3-weapon-forward", value)
                      for value in (.96, 1.0, 1.04)}
        self.assertEqual(3, len(identities))
        manifest = {"schema_version": 2, "source": {}, "components": {},
                    "animation": {}, "animations": {}, "appearance": appearance_record(.96)}
        other = json.loads(json.dumps(manifest)); other["appearance"] = appearance_record(1.04)
        capability = "one_handed_blade_v3_source_frame_forward_corrected"
        self.assertEqual(static_assembly_identity(manifest, capability),
                         static_assembly_identity(other, capability))

    def test_assembly_identity_normalizes_only_visual_scale(self):
        capability = "one_handed_blade_v3_source_frame_forward_corrected"
        base = {"schema_version": 2, "source": {}, "components": {},
                "animation": {}, "animations": {}, "appearance": appearance_record(.96)}
        scale_only = json.loads(json.dumps(base))
        scale_only["appearance"] = appearance_record(1.04)
        assembly_affecting = json.loads(json.dumps(base))
        assembly_affecting["appearance"]["future_geometry_semantic"] = "variant-b"
        self.assertEqual(static_assembly_identity(base, capability),
                         static_assembly_identity(scale_only, capability))
        self.assertNotEqual(static_assembly_identity(base, capability),
                            static_assembly_identity(assembly_affecting, capability))

    def test_animation_freezing_keeps_semantic_appearance_data(self):
        from rome2aoe2.native_assembly import static_visual_manifest
        manifest = {"schema_version": 2, "source": {}, "components": {},
                    "animation": {}, "animations": {}, "appearance": appearance_record(1.04)}
        static = static_visual_manifest(manifest)
        self.assertEqual(1.04, visual_scale_from_manifest(static))

    def test_canvas_interior_passes_without_overscan(self):
        result = validate_canvas_bounds(1.1, "attack", 12, 4, [1, 1, 799, 799], [800, 800])
        self.assertFalse(result["edge_contact"])
        self.assertFalse(result["overscan_performed"])
        self.assertFalse(result["confirmed_overflow"])

    def test_exclusive_edge_contact_requires_confirmation_but_is_not_overflow(self):
        result = validate_canvas_bounds(1.0, "walk", 5, 3,
                                        [129, 216, 243, 400], [400, 400])
        self.assertTrue(result["edge_contact"])
        self.assertFalse(result["confirmed_overflow"])
        for bounds in ([0, 1, 399, 399], [1, 0, 399, 399],
                       [1, 1, 400, 399], [1, 1, 399, 400]):
            self.assertTrue(canvas_edge_contact(bounds, [400, 400]))

    def test_zero_outside_alpha_confirms_safe_edge_contact(self):
        spec = overscan_camera([4, 4], 8.0)
        alpha = [0.0] * (spec["resolution"][0] * spec["resolution"][1])
        outside = outside_alpha_metrics(alpha, spec["resolution"], spec["production_crop"])
        result = confirm_canvas_bounds(1.0, "walk", 5, 3, "shadow",
                                       [1, 1, 3, 4], [4, 4], spec, outside)
        self.assertTrue(result["edge_contact"])
        self.assertTrue(result["overscan_performed"])
        self.assertEqual(0, result["outside_nonzero_count"])
        self.assertFalse(result["confirmed_overflow"])

    def test_any_outside_alpha_is_structured_confirmed_overflow(self):
        spec = overscan_camera([400, 400], CANONICAL_ORTHOGRAPHIC_SCALE)
        alpha = [0.0] * (528 * 528)
        alpha[464 * 528 + 200] = 1.0 / 255.0
        outside = outside_alpha_metrics(alpha, spec["resolution"], spec["production_crop"])
        self.assertEqual(1, outside["outside_nonzero_count"])
        with self.assertRaises(ConverterError) as caught:
            confirm_canvas_bounds(1.04, "death", 8, 31, "main",
                                  [0, 17, 780, 800], [800, 800], spec, outside)
        self.assertEqual(ErrorCode.VISUAL_SCALE_CANVAS_OVERFLOW, caught.exception.code)
        self.assertEqual(1, caught.exception.context["outside_nonzero_count"])
        self.assertEqual("main", caught.exception.context["pass"])

    def test_overscan_camera_preserves_pixel_density(self):
        spec = overscan_camera([400, 400], CANONICAL_ORTHOGRAPHIC_SCALE)
        self.assertEqual([528, 528], spec["resolution"])
        self.assertEqual([64, 64, 464, 464], spec["production_crop"])
        self.assertEqual(400 / CANONICAL_ORTHOGRAPHIC_SCALE,
                         528 / spec["orthographic_scale"])

    def test_configuration_presets_and_custom_value_freeze_numbers(self):
        self.assertEqual((1.0, False), choose_visual_scale(io.StringIO("A\n"), io.StringIO()))
        self.assertEqual((.96, True), choose_visual_scale(io.StringIO("1\n"), io.StringIO()))
        self.assertEqual((1.04, True), choose_visual_scale(io.StringIO("4\n1.04\n"), io.StringIO()))

    def test_rendering_is_camera_only_and_main_shadow_share_one_value(self):
        api = (ROOT/"rome2aoe2/production.py").read_text()
        main = (ROOT/"src/blender/render_manifest_native_production.py").read_text()
        shadow = (ROOT/"src/blender/render_manifest_native_shadow.py").read_text()
        native = (ROOT/"rome2aoe2/native_assembly.py").read_text()
        self.assertIn('"--visual-scale", str(visual_scale)', api)
        self.assertIn("camera(scene,visual_scale,canonical_scale)", main)
        self.assertIn("camera(scene,visual_scale,canonical_scale)", shadow)
        self.assertIn("data.ortho_scale=effective_orthographic_scale", main)
        self.assertIn('"--canonical-orthographic-scale", str(canonical_ortho)', api)
        self.assertNotIn("visual_scale", native.split("def assemble_native", 1)[1])
        for forbidden in ("Rom_Principes", "roman_gladius", "object.scale", "armature.scale"):
            self.assertNotIn(forbidden, main + shadow)

    def test_main_and_shadow_share_edge_confirmation_without_replacing_outputs(self):
        main = (ROOT/"src/blender/render_manifest_native_production.py").read_text()
        shadow = (ROOT/"src/blender/render_manifest_native_shadow.py").read_text()
        for source in (main, shadow):
            self.assertIn('canvas_validation["edge_contact"]', source)
            self.assertIn("confirm_canvas_bounds", source)
            self.assertIn('"validation/overscan/', source)
        self.assertIn('master=a.output_root/"main/master"/stem', main)
        self.assertIn('x2=a.output_root/"shadow/x2"/stem', shadow)
        policy = (ROOT/"rome2aoe2/visual_scale.py").read_text()
        self.assertIn("if alpha > 0.0", policy)
        self.assertNotIn("alpha_threshold", policy)


if __name__ == "__main__":
    unittest.main()
