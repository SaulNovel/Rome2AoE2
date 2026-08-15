"""Regression tests for the canonical AoE2 facet/yaw mapping."""

from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aoe2.facet_mapping import legacy_source_facet, soldier_yaw_degrees
from aoe2.reorder_sld_facets import reorder
from aoe2.sld import LAYER_MAIN, LAYER_SHADOW, SLDFile, SLDFrame, SLDLayer


class FacetMappingTests(unittest.TestCase):
    def test_legacy_proof_is_reversed_into_aoe_clockwise_order(self):
        self.assertEqual(
            [10, 9, 8, 7, 6, 5, 4, 3, 2, 1, 0, 15, 14, 13, 12, 11],
            [legacy_source_facet(i) for i in range(16)],
        )

    def test_runtime_yaw_is_complete_and_uniform(self):
        self.assertEqual(
            [292.5, 270.0, 247.5, 225.0, 202.5, 180.0, 157.5, 135.0,
             112.5, 90.0, 67.5, 45.0, 22.5, 0.0, 337.5, 315.0],
            [soldier_yaw_degrees(i) for i in range(16)],
        )

    def test_invalid_facet_is_rejected(self):
        for value in (-1, 16):
            with self.assertRaises(ValueError):
                legacy_source_facet(value)
            with self.assertRaises(ValueError):
                soldier_yaw_degrees(value)

    def test_facet_major_animation_reorder_keeps_layers_and_frames_together(self):
        frames = []
        for source_facet in range(16):
            for animation_frame in range(2):
                marker = source_facet * 10 + animation_frame
                frames.append(SLDFrame(
                    4, 4, 2, 2, LAYER_MAIN | LAYER_SHADOW,
                    frame_index=len(frames),
                    layers=[
                        SLDLayer(LAYER_MAIN, raw_content=bytes([marker])),
                        SLDLayer(LAYER_SHADOW, raw_content=bytes([marker])),
                    ],
                ))
        result = reorder(SLDFile(frames=frames, facet_count=16), 2)
        markers = [frame.layers[0].raw_content[0] for frame in result.frames]
        expected = [source * 10 + animation for source in
                    [legacy_source_facet(i) for i in range(16)] for animation in range(2)]
        self.assertEqual(expected, markers)
        self.assertEqual(list(range(32)), [frame.frame_index for frame in result.frames])
        self.assertTrue(all(frame.layers[0].raw_content == frame.layers[1].raw_content
                            for frame in result.frames))


if __name__ == "__main__":
    unittest.main()
