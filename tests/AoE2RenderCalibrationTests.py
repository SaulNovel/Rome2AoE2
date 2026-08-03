import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "blender"))
from aoe2_render_profile import (alpha_bounds, camera_location, deterministic_json,
                                 direction_angles, internal_dimensions, load_profile,
                                 output_filename, representative_frames, sample_blender_frame,
                                 scaled_anchor, shadow_filename, stable_canvas)
from downsample_rgba import downsample_rgba


PROFILE = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v1.json"
PROFILE_V2 = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v2.json"
PROFILE_V3 = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v3_candidate.json"


class AoE2RenderCalibrationTests(unittest.TestCase):
    def write_profile(self, data, name):
        directory = ROOT / "build" / "test-render-calibration"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_profile_parses(self):
        self.assertEqual(load_profile(PROFILE)["name"], "aoe2_de_infantry_v1")

    def test_profile_versioning_and_migration(self):
        profile = load_profile(PROFILE_V2)
        self.assertEqual(profile["version"], 2)
        self.assertEqual(profile["inherits"], "aoe2_de_infantry_v1")

    def test_visual_candidate_profile_preserves_camera_geometry(self):
        v2, candidate=load_profile(PROFILE_V2),load_profile(PROFILE_V3)
        self.assertEqual(3,candidate["version"]); self.assertEqual("in_game_visual_candidate",candidate["status"])
        self.assertEqual(v2["camera"],candidate["camera"])

    def test_missing_required_settings(self):
        data = json.loads(PROFILE.read_text())
        del data["camera"]
        with self.assertRaisesRegex(ValueError, "missing"):
            load_profile(self.write_profile(data, "missing.json"))

    def test_direction_angles_are_deterministic(self):
        self.assertEqual(direction_angles(load_profile(PROFILE)), [45, 0, 315, 270, 225, 180, 135, 90])

    def test_source_sample_selection(self):
        self.assertEqual(sample_blender_frame(42, 15, 60), 169)

    def test_camera_placement(self):
        x, y, z = camera_location(45, 30, 10)
        self.assertAlmostEqual(x, y)
        self.assertAlmostEqual(z, 5)

    def test_stable_canvas(self):
        self.assertEqual(stable_canvas(load_profile(PROFILE))["anchor_pixels"], [100, 100])

    def test_internal_scale_dimensions_and_anchor(self):
        profile = load_profile(PROFILE_V2)
        self.assertEqual(internal_dimensions(profile), (800, 800))
        self.assertEqual(scaled_anchor(profile), [400, 400])

    def test_invalid_render_scale(self):
        data = json.loads(PROFILE_V2.read_text())
        data["render"]["internal_render_scale"] = 3
        with self.assertRaisesRegex(ValueError, "internal_render_scale"):
            load_profile(self.write_profile(data, "invalid-scale.json"))

    def test_deterministic_filter_selection(self):
        data = json.loads(PROFILE_V2.read_text())
        data["render"]["downsample_method"] = "nearest"
        with self.assertRaisesRegex(ValueError, "downsample"):
            load_profile(self.write_profile(data, "invalid-filter.json"))

    def test_alpha_correct_downsample_preserves_output_and_alpha(self):
        pixels = [1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        result = downsample_rgba(pixels, 2, 2, 1, 1, "bicubic")
        self.assertEqual(len(result), 4)
        self.assertGreater(result[3], 0)
        self.assertGreater(result[0], 0.9)

    def test_alpha_bounds(self):
        self.assertEqual(alpha_bounds(2, 2, [0, 1, 1, 0]), [0, 0, 2, 2])

    def test_output_filename(self):
        self.assertEqual(output_filename("sws_stand.anim", 0, 7), "sws_stand-sample-0000-direction-07-color.png")

    def test_shadow_filename(self):
        self.assertEqual(shadow_filename("sws_stand.anim", 0, 7), "sws_stand-sample-0000-direction-07-shadow.png")

    def test_representative_frames_are_stable(self):
        frames = representative_frames()
        self.assertEqual([item["source_sample"] for item in frames], [0, 21, 22, 30])
        self.assertEqual(deterministic_json({"frames": frames}), deterministic_json({"frames": representative_frames()}))

    def test_manifest_determinism(self):
        self.assertEqual(deterministic_json({"b": 2, "a": 1}), '{\n  "a": 1,\n  "b": 2\n}\n')

    def test_invalid_direction_count(self):
        data = json.loads(PROFILE.read_text())
        data["directions"]["count"] = 7
        with self.assertRaisesRegex(ValueError, "direction"):
            load_profile(self.write_profile(data, "invalid-directions.json"))

    def test_unsupported_render_engine(self):
        data = json.loads(PROFILE.read_text())
        data["render"]["engine"] = "WORKBENCH"
        with self.assertRaisesRegex(ValueError, "engine"):
            load_profile(self.write_profile(data, "invalid-engine.json"))

    def test_reports_need_no_absolute_paths(self):
        text = deterministic_json({"output": output_filename("idle.anim", 0, 0)})
        self.assertNotIn(str(ROOT), text)


if __name__ == "__main__":
    unittest.main()
