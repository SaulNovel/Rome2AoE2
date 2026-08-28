import json
import math
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/local-integration/rome2/runtime-parity-proof"

class LightingYawSweepTests(unittest.TestCase):
    def test_complete_coherent_sweep(self):
        report=json.loads((OUT/"lighting-yaw-report.json").read_text())
        self.assertEqual([q["yaw"] for q in report["candidates"]],list(range(0,360,45)))
        self.assertEqual(report["environment_rotation"]["ambient"],"Nenv=N@Renv")
        self.assertEqual(report["environment_rotation"]["cubemap"],"reflected@Renv@transform")
        for yaw in range(0,360,45):
            self.assertTrue((OUT/f"lighting-yaw-{yaw:03d}.png").exists())
        lengths=[math.sqrt(sum(v*v for v in q["sun_direction"])) for q in report["candidates"]]
        for value in lengths:self.assertAlmostEqual(value,1,places=5)

    def test_all_scene_controls_frozen(self):
        frozen=json.loads((OUT/"lighting-yaw-report.json").read_text())["frozen"]
        self.assertTrue(all(frozen.values()))

if __name__=="__main__":unittest.main()
