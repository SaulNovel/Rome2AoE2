"""Freeze the approved Asset Editor-native idle/walk production route."""

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "src/blender/build_hastati_native_animation.py"
RENDERER = ROOT / "src/blender/render_final_hastati_idle.py"
SHADOW = ROOT / "src/blender/render_hastati_shadow_proof.py"


class NativeAnimationPipelineTests(unittest.TestCase):
    def test_builder_imports_gltf_and_reuses_native_action_and_slot(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn("bpy.ops.import_scene.gltf", text)
        self.assertIn("armature.animation_data.action = native_action", text)
        self.assertIn("armature.animation_data.action_slot = native_slot", text)
        self.assertNotIn("create_action", text)
        self.assertNotIn("world_matrix", text)

    def test_joint_action_is_fingerprinted_but_never_keyed(self):
        tree = ast.parse(BUILDER.read_text(encoding="utf-8"))
        keyframe_receivers = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "keyframe_insert":
                if isinstance(node.func.value, ast.Name):
                    keyframe_receivers.append(node.func.value.id)
        self.assertEqual(["center"], keyframe_receivers)

    def test_outer_hierarchy_and_vertical_preservation_are_explicit(self):
        text = BUILDER.read_text(encoding="utf-8")
        self.assertIn('"Rome2AoE2_FacetRoot"', text)
        self.assertIn('"Rome2AoE2_LocomotionCenter"', text)
        self.assertIn("center.location = (reference[1] - x, reference[2] - y, 0.0)", text)
        self.assertIn('"joint_action_byte_equivalent"', text)

    def test_renderer_rotates_existing_facet_root_and_samples_native_keys(self):
        text = RENDERER.read_text(encoding="utf-8")
        self.assertIn('bpy.data.objects.get("Rome2AoE2_FacetRoot")', text)
        self.assertIn('args.frames == "native-keys"', text)
        self.assertIn("unit_root.rotation_euler[2]", text)

    def test_shadow_pipeline_uses_same_root_key_times_and_is_parallel_safe(self):
        text = SHADOW.read_text(encoding="utf-8")
        self.assertIn("action_keyframes(action)", text)
        self.assertIn("create_unit_root(armature, meshes)", text)
        self.assertIn("os.getpid()", text)


if __name__ == "__main__":
    unittest.main()
