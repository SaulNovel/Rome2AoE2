import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src"), str(ROOT / "build/python-deps/pillow")]
from PIL import Image
from rome2.build_corpse_ground_occlusion_prototype import aperture_clip, ease


class CorpseGroundOcclusionPrototypeTests(unittest.TestCase):
    def test_binary_aperture_preserves_start_and_clears_end(self):
        source = Image.new("RGBA", (200, 200))
        for x in range(30, 170):
            for y in range(70, 145):
                source.putpixel((x, y), (120, 80, 30, 255))
        first, _ = aperture_clip(source, 0)
        final, _ = aperture_clip(source, 96)
        self.assertEqual(source.tobytes(), first.tobytes())
        self.assertIsNone(final.getchannel("A").getbbox())
        self.assertEqual({0, 255}, set(aperture_clip(source, 48)[0].getchannel("A").get_flattened_data()))

    def test_approved_timing_spatial_density(self):
        offsets = [round(96 * ease(i / 52)) for i in range(53)]
        deltas = [b - a for a, b in zip(offsets, offsets[1:])]
        self.assertEqual((53, 52, 96), (len(offsets), len(deltas), offsets[-1]))
        self.assertAlmostEqual(96 / 52, sum(deltas) / len(deltas))
        self.assertEqual(3, max(deltas))


if __name__ == "__main__":
    unittest.main()
