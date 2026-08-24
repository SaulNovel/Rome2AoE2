import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from rome2aoe2.production import category_output,production_identity
from rome2aoe2.render_modes import require_release_eligible,resolve_render_mode,sample_policy,sample_positions

class FastRenderModeTests(unittest.TestCase):
 def test_full_is_immutable_default(self):
  full=resolve_render_mode();self.assertEqual(800,full["master_resolution"]);self.assertEqual(["x1","x2"],full["output_scales"]);self.assertTrue(full["release_eligible"])
 def test_fast_is_direct_high_definition_x2_only(self):
  fast=resolve_render_mode("fast");self.assertEqual(400,fast["master_resolution"]);self.assertEqual(["x2"],fast["output_scales"]);self.assertFalse(fast["release_eligible"])
 def test_fast_identity_and_output_are_test_isolated(self):
  record={"resolved_asset":"clip","asset_sha256":"f"*64};base=("e"*64,"idle",record,"aoe2-infantry-animation-production-v5-equipment-readability",1.0)
  self.assertNotEqual(production_identity(*base),production_identity(*base,"fast"));self.assertIn("test-renders",category_output("Unit",*base,"fast").parts)
 def test_deterministic_half_sampling_and_duration(self):
  p=sample_policy(33,15,False);self.assertEqual(17,p["test_sample_count"]);self.assertEqual(p["source_duration"],p["test_duration"]);self.assertEqual([0,32],sample_positions(0,32,33,15,False,"fast")[::16])
 def test_loop_omits_duplicate_endpoint(self):
  positions=sample_positions(0,19,20,20,True,"fast");self.assertEqual(10,len(positions));self.assertEqual(0,positions[0]);self.assertLess(positions[-1],19)
 def test_release_authoring_rejects_fast(self):
  with self.assertRaises(RuntimeError):require_release_eligible({"render_mode":"fast","release_eligible":False})
  self.assertIn("require_release_eligible(production)",(ROOT/"src/aoe2/author_manifest_production_sld.py").read_text())
 def test_renderers_keep_16_directions_x2_and_action_guard(self):
  for relative in ("src/blender/render_manifest_native_production.py","src/blender/render_manifest_native_shadow.py"):
   source=(ROOT/relative).read_text();self.assertIn("list(range(16))",source);self.assertIn('a.render_mode=="full"',source);self.assertIn("action_fingerprint",source);self.assertIn("action_preserved",source)
  self.assertIn('"main/master" if a.render_mode=="full" else "main/x2"',(ROOT/"src/blender/render_manifest_native_production.py").read_text())
  self.assertIn("str(ROOT),str(ROOT/\"src\")",(ROOT/"src/blender/render_manifest_native_shadow.py").read_text())

if __name__=="__main__":unittest.main()
