import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
from aoe2.activate_local_test_mod import activate
from aoe2.scenario_validation import validate_scenario
class Units:
 def exists(self,index):return index==2113
class Workspace:unit_manager=Units()
KNOWN=ROOT/"build/dev-test/rome2aoe2/rom_principes/611db84c371e707b/Rome2AoE2PrincipesDevTest.aoe2scenario"
class ScenarioDevIntegrationTests(unittest.TestCase):
 def test_known_good_topology_and_ids_validate(self):
  result=validate_scenario(KNOWN,Workspace(),(2113,));self.assertEqual(30,result["total_objects"]);self.assertEqual([2113],result["placed_unit_ids"]);self.assertEqual((15,15),(result["players"][1]["count"],result["players"][2]["count"]));self.assertTrue(result["all_object_ids_resolve"])
 def test_missing_expected_or_dat_unit_fails(self):
  with self.assertRaises(RuntimeError):validate_scenario(KNOWN,Workspace(),(9999,))
  with self.assertRaises(RuntimeError):validate_scenario(KNOWN,type("W",(),{"unit_manager":type("U",(),{"exists":lambda self,index:False})()})(),(2113,))
 def test_activation_enables_target_and_disables_conflict(self):
  path=ROOT/"build/tmp/scenario-test-mod-status.json";path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps({"Mods":[{"Title":"Base","Enabled":True},{"Title":"Target","Enabled":False},{"Title":"Other","Enabled":True}]}))
  try:result=activate(path,"Target",("Base",));mods={m["Title"]:m["Enabled"] for m in json.loads(path.read_text())["Mods"]};self.assertEqual({"Base":False,"Target":True,"Other":True},mods);self.assertTrue(result["enabled"])
  finally:path.unlink(missing_ok=True)
 def test_builder_requires_byte_identical_reuse_and_semantic_validation(self):
  source=(ROOT/"src/aoe2/build_fast_corpse_dev_integration.py").read_text();self.assertIn("validate_scenario(scenario,written",source);self.assertIn("byte-identical",source);self.assertIn("conflicting_mod_titles",source)
 def test_installer_activates_before_verification(self):
  source=(ROOT/"scripts/install_fast_corpse_test.ps1").read_text();self.assertLess(source.index("activate_local_test_mod.py"),source.index("verify_manifest_dev_install.py"))
if __name__=="__main__":unittest.main()
