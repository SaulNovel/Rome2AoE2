import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];MR=ROOT/"build"/"local-integration"/"rome2"/"material-reconstruction"
class Tests(unittest.TestCase):
 def test_semantics_and_outputs(self):
  md=(MR/"rome2-faction-shader-semantics.md").read_text();self.assertIn("lerp(D",md);self.assertIn("normal.r * normal.a",md);self.assertIn("1 - gloss.r * gloss.r",md)
  src=(ROOT/"src"/"blender"/"render_material_reconstruction_v1.py").read_text();self.assertNotIn("max(R,G,B)",src);self.assertIn('exact_tint',src);self.assertIn('packed_normal',src)
  for n in ("faction-channel-semantics.png","decal-before-after.png","normal-before-after.png","material-reconstruction-v1.png","material-reconstruction-v1-gameplay-scale.png","player-color-v2.png"):self.assertGreater((MR/n).stat().st_size,1000)
if __name__=="__main__":unittest.main()
