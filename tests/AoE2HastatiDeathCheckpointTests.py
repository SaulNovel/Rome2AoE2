"""Regression checks for the approved native Hastati death production route."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "src/blender/build_hastati_native_animation.py"
RENDER = ROOT / "scripts/render_hastati_native_death.ps1"
BUILD = ROOT / "scripts/build_hastati_native_death_test.ps1"
PACKAGE = ROOT / "src/aoe2/package_hastati_idle_walk_sld.py"
INSTALL = ROOT / "scripts/install_hastati_test.ps1"


class HastatiDeathCheckpointTests(unittest.TestCase):
    def test_death_uses_native_action_without_locomotion_centering(self):
        builder = BUILDER.read_text(encoding="utf-8")
        render = RENDER.read_text(encoding="utf-8")
        self.assertIn("bpy.ops.import_scene.gltf", builder)
        self.assertIn("armature.animation_data.action = native_action", builder)
        self.assertIn("--motion-policy preserve-native", render)
        self.assertIn("sws_cr_death_missile_004.gltf", render)
        self.assertIn("--frames native-keys", render)
        self.assertNotIn("--remove-root-motion", render)

    def test_death_sld_is_33_by_16_at_native_cadence(self):
        build = BUILD.read_text(encoding="utf-8")
        self.assertIn("--animation death --frames 33", build)
        self.assertIn("--frame-duration (1.0 / 15.0)", build)
        self.assertIn("--death-frame-duration (1.0 / 15.0)", build)
        self.assertIn("--directions $Directions", RENDER.read_text(encoding="utf-8"))

    def test_package_preserves_existing_mappings_and_adds_dying_graphic(self):
        package = PACKAGE.read_text(encoding="utf-8")
        self.assertIn("clone.standing_sprite_id1 = clone.standing_sprite_id2 = idle.id", package)
        self.assertIn("clone.walking_graphic_id = walk.id", package)
        self.assertIn("clone.attack_graphic_id = attack.id", package)
        self.assertIn("clone.dying_sprite_id = death.id", package)
        self.assertIn("written_clone.dead_unit_id != militia.dead_unit_id", package)
        self.assertIn('"sws_cr_death_missile_004"', package)

    def test_death_runtime_contract_is_inherited_and_reported(self):
        package = PACKAGE.read_text(encoding="utf-8")
        self.assertIn('report["death_graphic_id"] = death.id', package)
        self.assertIn('"sequence_type": death_reference.sequence_type', package)
        self.assertIn('"mirroring_mode": death_reference.mirroring_mode', package)
        self.assertIn('"render_layer": death_reference.layer', package)
        self.assertIn('"dead_unit_id": written_clone.dead_unit_id', package)
        self.assertIn("APPROVED_GRAPHIC_IDS = (17068, 17069, 17070, 17071)", package)
        self.assertIn("APPROVED_CORPSE_UNIT_ID = 152", package)
        self.assertIn("(11, 6, 20, 0, 0)", package)
        self.assertIn("for field in RUNTIME_FIELDS", package)

    def test_installer_requires_both_death_zoom_assets(self):
        install = INSTALL.read_text(encoding="utf-8")
        self.assertIn("rome2aoe2_hastati_death_x1.sld", install)
        self.assertIn("rome2aoe2_hastati_death_x2.sld", install)


if __name__ == "__main__":
    unittest.main()
