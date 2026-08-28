import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src")]
from aoe2.sld import LAYER_PLAYERCOLOR,parse_sld,serialize_sld
BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"/"player-color-diagnostic";MOD=BASE/"ROME2AOE2_PLAYER_COLOR_DIAGNOSTIC"
class Tests(unittest.TestCase):
 def test_package_and_layers(self):
  self.assertTrue((MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat").is_file())
  self.assertFalse((MOD/"mod"/"resources").exists())
  report=json.loads((BASE/"player-color-diagnostic.json").read_text());self.assertEqual(len({u["unit_id"] for u in report["units"]}),5);self.assertEqual(len({u["graphic_id"] for u in report["units"]}),5)
  for u in report["units"]:
   for zoom,canvas,hotspot in (("x1",200,(100,100)),("x2",400,(200,200))):
    path=MOD/"resources"/"_common"/"drs"/"graphics"/f"{u['stem']}_{zoom}.sld";raw=path.read_bytes();s=parse_sld(raw);self.assertEqual(serialize_sld(s),raw);self.assertEqual(len(s.frames),16);self.assertEqual([f.frame_index for f in s.frames],list(range(16)))
    for f in s.frames:self.assertEqual((f.canvas_width,f.canvas_height),(canvas,canvas));self.assertEqual((f.center_x,f.center_y),hotspot);self.assertIn(LAYER_PLAYERCOLOR,[l.layer_type for l in f.layers])
if __name__=="__main__":unittest.main()
