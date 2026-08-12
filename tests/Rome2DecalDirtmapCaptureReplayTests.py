import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPLAY=ROOT/"build/local-integration/rome2/runtime-shader-recovery/decal-dirtmap-capture-replay/report.json"
RENDER=ROOT/"build/local-integration/rome2/runtime-parity-proof/report.json"


class DecalDirtmapCaptureReplayTests(unittest.TestCase):
    def test_capture_replay_validation(self):
        report=json.loads(REPLAY.read_text())
        self.assertEqual(report["event"],1099)
        self.assertEqual(report["instance"],0)
        self.assertEqual(report["deferred_lighting_family"],"StandardLighting1915")
        self.assertEqual(report["validation"]["status"],"VALIDATED")
        self.assertGreaterEqual(report["gbuffer_error_cumulative_population"]["2"],4000)
        self.assertGreaterEqual(report["interior_surviving_lighting_candidates"],3000)
        self.assertLessEqual(report["validation"]["meaningful_hdr_relative_error_after_captured_shadow_fit"],.10)
        self.assertLessEqual(report["validation"]["midtone_bright_max_display_absolute_error"],.03)

    def test_generic_render_route_and_outputs(self):
        report=json.loads(RENDER.read_text())
        self.assertIn("DecalDirtmap",report["material_paths"])
        self.assertEqual(report["material_lighting_routes"]["DecalDirtmap"],"event-1915 standard")
        self.assertNotIn("DecalDirtmap",report["unsupported_paths"])
        self.assertTrue((RENDER.parent/report["output"]).is_file())
        self.assertTrue((RENDER.parent/"shield-before-after.png").is_file())


if __name__=="__main__": unittest.main()
