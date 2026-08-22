import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.production import CAMERA_TARGET_Z,EXPECTED_DIRECTIONS,ORTHOGRAPHIC_SCALE,PROFILE,frozen_candidate,production_identity
class ProductionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.request=load_and_validate_manifest(ROOT/"config/manifests/rom_principes-explicit-animations-v2.json")
 def test_frozen_manifest_only(self):
  self.assertEqual("611db84c371e707bbf8c14626402077a8974f7d8c14af1941b0f38905f39625b",self.request.manifest_hash)
  self.assertTrue(all(v["mode"]=="explicit" for v in self.request.manifest["animations"].values()))
 def test_direction_and_scale_profile(self):
  self.assertEqual([(292.5-22.5*i)%360 for i in range(16)],EXPECTED_DIRECTIONS);self.assertEqual(7.27480212108078,ORTHOGRAPHIC_SCALE);self.assertEqual(0.8503072261810303,CAMERA_TARGET_Z)
 def test_exact_frozen_candidate_mapping(self):
  for category,row in self.request.manifest["animations"].items():
   candidate=frozen_candidate(category,row);self.assertEqual(row["resolved_asset"],candidate.resolved_asset);self.assertEqual(row["frame_count"],candidate.frame_count)
 def test_deterministic_output_identity_and_cross_animation_isolation(self):
  rows=self.request.manifest["animations"];a=production_identity(self.request.manifest_hash,"idle",rows["idle"]);self.assertEqual(a,production_identity(self.request.manifest_hash,"idle",rows["idle"]));self.assertNotEqual(a,production_identity(self.request.manifest_hash,"walk",rows["walk"]))
 def test_renderer_contract(self):
  source=(ROOT/"src/blender/render_manifest_native_production.py").read_text();assembly=(ROOT/"src/blender/assemble_native_basis_animation.py").read_text()
  self.assertIn("Rome2AoE2_FacetRoot",source);self.assertIn("exact.exact_render",source);self.assertIn("action_fingerprint_after",source);self.assertNotIn("Rom_Principes",source);self.assertNotIn("Rom_Hastati",source);self.assertIn('doc["category"] in {"walk","death"}',assembly)
  self.assertNotIn("static weighted",source.casefold())
  shadow=(ROOT/"src/blender/render_manifest_native_shadow.py").read_text();self.assertIn("fixed-global-cast-shadow-v1",shadow);self.assertIn("soldier_yaw_degrees",shadow);self.assertIn("action_fingerprint_after",shadow)
 def test_frame_parity_and_review_contract(self):
  source=(ROOT/"src/rome2/build_production_review.py").read_text();self.assertIn("for direction in range(16)",source);self.assertIn("x1_x2_parity",source);self.assertIn("main_shadow_parity",source);self.assertIn("alpha_bounds_sane",source);self.assertIn("loop_seam_rgba_mae",source)
  self.assertNotIn("rom_principes",source.casefold());self.assertNotIn("rom_hastati",source.casefold())
if __name__=="__main__":unittest.main()
