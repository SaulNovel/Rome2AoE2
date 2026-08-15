from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_DEPS = ROOT / "build" / "python-deps" / "sld-authoring"
if LOCAL_DEPS.is_dir():
    sys.path.insert(0, str(LOCAL_DEPS))
sys.path.insert(0, str(ROOT / "src"))

from PIL import Image

from aoe2.generate_static_sld_quality_gate import compare


class StaticSLDQualityGateTests(unittest.TestCase):
    def test_metrics_use_binary_source_alpha_for_silhouette(self):
        source = Image.new("RGBA", (2, 1))
        source.putdata([(10, 20, 30, 127), (40, 50, 60, 128)])
        decoded = Image.new("RGBA", (2, 1))
        decoded.putdata([(0, 0, 0, 0), (40, 50, 60, 255)])
        result = compare(source, decoded)
        self.assertEqual(0, result["silhouette_error_pixels"])
        self.assertEqual(1.0, result["alpha_binary_equality_fraction"])
        self.assertEqual(float("inf"), result["opaque_rgb_psnr_db"])

    def test_metrics_detect_colour_and_silhouette_errors(self):
        source = Image.new("RGBA", (1, 1), (100, 100, 100, 255))
        decoded = Image.new("RGBA", (1, 1), (90, 110, 100, 0))
        result = compare(source, decoded)
        self.assertEqual(1, result["silhouette_error_pixels"])
        self.assertEqual(0, result["alpha_binary_equality_pixels"])


if __name__ == "__main__":
    unittest.main()
