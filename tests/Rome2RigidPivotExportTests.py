import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.rome2.rmv2_rigid_pivot import (
    asset_editor_gltf_translation,
    blender_import_translation,
    compose_translation,
)


class Rome2RigidPivotExportTests(unittest.TestCase):
    def test_zero_pivot_is_unchanged(self):
        self.assertEqual(asset_editor_gltf_translation((0, 0, 0)), (0, 0, 0))
        self.assertEqual(blender_import_translation((0, 0, 0)), (0, 0, 0))

    def test_nonzero_pivot_survives_asset_editor_and_blender(self):
        source = (0.125, -0.25, 0.5)
        gltf = asset_editor_gltf_translation(source)
        blender = blender_import_translation(gltf)
        reconstructed = (-blender[0], blender[2], -blender[1])
        self.assertLess(math.dist(source, reconstructed), 1e-12)

    def test_known_gladius_pivot(self):
        source = (0.2467492, -0.0004839785, -5.401671e-8)
        self.assertEqual(asset_editor_gltf_translation(source), (-0.2467492, -0.0004839785, -5.401671e-8))

    def test_known_feather_pivot(self):
        source = (0.008174144, 0.1027770, 0.01105482)
        self.assertEqual(blender_import_translation(asset_editor_gltf_translation(source)),
                         (-0.008174144, -0.01105482, 0.1027770))

    def test_pivot_is_inside_attachment_transform(self):
        attachment = (10.0, 20.0, 30.0)
        pivot = blender_import_translation(asset_editor_gltf_translation((0.25, 0.5, 0.75)))
        self.assertEqual(compose_translation(attachment, pivot), (9.75, 19.25, 30.5))

    def test_rigid_child_local_is_stable_while_parent_animates(self):
        pivot = blender_import_translation(asset_editor_gltf_translation((0.25, 0.5, 0.75)))
        worlds = [compose_translation(parent, pivot) for parent in ((0, 0, 0), (1, 2, 3), (-4, 5, 6))]
        recovered = [tuple(world[i] - parent[i] for i in range(3)) for world, parent in zip(worlds, ((0, 0, 0), (1, 2, 3), (-4, 5, 6)), strict=True)]
        self.assertTrue(all(value == pivot for value in recovered))


if __name__ == "__main__":
    unittest.main()
