"""Regression checks for the approved native Hastati attack checkpoint."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "src/blender/build_hastati_native_animation.py"
RENDER = ROOT / "scripts/render_hastati_native_attack.ps1"
BUILD = ROOT / "scripts/build_hastati_native_attack_test.ps1"
PACKAGE = ROOT / "src/aoe2/package_hastati_idle_walk_sld.py"
SLD = ROOT / "src/aoe2/generate_hastati_animation_sld.py"
INSTALL = ROOT / "scripts/install_hastati_test.ps1"


class HastatiAttackCheckpointTests(unittest.TestCase):
    def test_attack_uses_native_gltf_action_route(self):
        builder = BUILDER.read_text(encoding="utf-8")
        render = RENDER.read_text(encoding="utf-8")
        self.assertIn("bpy.ops.import_scene.gltf", builder)
        self.assertIn("armature.animation_data.action = native_action", builder)
        self.assertNotIn("create_action", builder)
        self.assertIn("sws_sync_atk_005.gltf", render)
        self.assertIn("--frames native-keys", render)

    def test_attack_sld_is_27_by_16_main_plus_shadow_without_player_colour(self):
        build = BUILD.read_text(encoding="utf-8")
        sld = SLD.read_text(encoding="utf-8")
        self.assertIn("--animation attack --frames 27", build)
        self.assertIn("--frame-duration (1.3 / 27)", build)
        self.assertIn("for direction in range(16)", sld)
        self.assertIn("LAYER_MAIN | LAYER_SHADOW", sld)
        self.assertIn('"player_colour": False', sld)
        self.assertNotIn("LAYER_PLAYERCOLOR", sld)

    def test_package_freezes_idle_walk_attack_mapping_and_timing(self):
        package = PACKAGE.read_text(encoding="utf-8")
        self.assertIn("clone.standing_sprite_id1 = clone.standing_sprite_id2 = idle.id", package)
        self.assertIn("clone.walking_graphic_id = walk.id", package)
        self.assertIn("clone.attack_graphic_id = attack.id", package)
        self.assertIn('"sws_sync_atk_005"', package)
        self.assertIn("args.attack_cycle_duration / 27", package)
        self.assertIn('"impact_sample_index": 10', package)

    def test_build_and_installer_require_both_attack_zoom_assets(self):
        build = BUILD.read_text(encoding="utf-8")
        install = INSTALL.read_text(encoding="utf-8")
        for stem in ("hastati-attack_x1.sld", "hastati-attack_x2.sld"):
            self.assertIn(stem, build)
        for stem in ("hastati_attack_x1.sld", "hastati_attack_x2.sld"):
            self.assertIn(stem, install)


if __name__ == "__main__":
    unittest.main()
