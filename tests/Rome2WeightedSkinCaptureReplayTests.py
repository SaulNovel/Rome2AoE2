import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPLAY=ROOT/"build/local-integration/rome2/runtime-shader-recovery/weighted-skin-capture-replay/report.json"
RENDER=ROOT/"build/local-integration/rome2/runtime-parity-proof/report.json"


class WeightedSkinCaptureReplayTests(unittest.TestCase):
    def test_capture_replay_validation(self):
        report=json.loads(REPLAY.read_text())
        self.assertEqual(report["status"],"VALIDATED")
        by={row["component"]:row for row in report["results"]}
        self.assertGreaterEqual(by["body"]["gbuffer_pixels_within_2_codes"],100)
        self.assertGreaterEqual(by["head"]["gbuffer_pixels_within_2_codes"],500)
        self.assertGreaterEqual(by["head"]["interior_stencil3_lighting_candidates"],100)
        self.assertLessEqual(by["head"]["validation"]["midtone_bright_max_hdr_relative_error"],.10)
        self.assertLessEqual(by["head"]["validation"]["midtone_bright_max_display_absolute_error"],.03)

    def test_generic_render_route_and_outputs(self):
        report=json.loads(RENDER.read_text())
        self.assertIn("WeightedSkinDirtmap",report["material_paths"])
        self.assertEqual(report["material_lighting_routes"]["WeightedSkinDirtmap"],"event-1926 skin")
        self.assertNotIn("WeightedSkinDirtmap",report["unsupported_paths"])
        out=RENDER.parent
        self.assertTrue((out/report["output"]).is_file())
        self.assertTrue((out/"skin-before-after.png").is_file())


if __name__=="__main__": unittest.main()
