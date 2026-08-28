import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
AUDIT=ROOT/"build/local-integration/rome2/runtime-parity-proof/skin-integration-audit/report.json"
RENDER=ROOT/"build/local-integration/rome2/runtime-parity-proof"


class SkinIntegrationAuditTests(unittest.TestCase):
    def test_structural_bug_is_corrected(self):
        report=json.loads(AUDIT.read_text())
        self.assertEqual(report["verdict"],"INTEGRATION BUG FOUND")
        self.assertEqual(report["routing_pixel_counts"]["roman_body1"],19745)
        grey=next(q for q in report["traces"] if q["label"]=="grey_blue_leg")
        required=grey["material_output"]["skin_mask_required"]
        buggy=grey["material_output"]["skin_mask_current_buggy_aov"]
        actual=grey["material_output"]["skin_mask_actual_corrected_aov"]
        self.assertEqual(required,actual)
        self.assertLess(buggy[0],required[0])
        self.assertGreater(grey["current_render_rgb"][2],grey["current_render_rgb"][0])
        self.assertGreater(grey["corrected_render_rgb"][0],grey["corrected_render_rgb"][2])

    def test_diagnostics_exist(self):
        for name in ("debug-skin-family-routing.png","skin-light-contribution-sheet.png",
                     "skin-mask-fix-before-after.png","runtime-parity-f03.png"):
            self.assertTrue((RENDER/name).is_file(),name)


if __name__=="__main__":unittest.main()
