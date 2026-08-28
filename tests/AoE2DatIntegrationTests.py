import json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT)]
from aoe2.dat_integration import LIVE_GRAPHIC_FIELDS,allocation_key,category_stem,resolve_allocation
class Manager:
 def __init__(self,occupied):self.occupied=set(occupied)
 def exists(self,index):return index in self.occupied
class Workspace:
 def __init__(self):
  self.unit_manager=Manager(set(range(2081))|set(range(2082,2113)));self.graphic_manager=Manager(set(range(17068)))
  self.dat=type("Dat",(),{"civilizations":[type("Civ",(),{"units":[None]*2701})()],"sprites":[None]*17068})()
class IntegrationTests(unittest.TestCase):
 def setUp(self):self.registry=json.loads((ROOT/"config/aoe2/integration_allocations.json").read_text());self.manifest=json.loads((ROOT/"config/manifests/rom_principes-explicit-animations-v2.json").read_text())
 def test_collision_safe_and_deterministic_allocation(self):
  key=next(key for key in self.registry["allocations"] if key.endswith(":infantry_melee_visual_test_v1"));manifest_hash=key.split(":")[0];a=resolve_allocation(Workspace(),self.registry,manifest_hash,"infantry_melee_visual_test_v1");b=resolve_allocation(Workspace(),self.registry,manifest_hash,"infantry_melee_visual_test_v1");self.assertEqual(a,b);self.assertEqual(2113,a["unit_id"]);self.assertEqual({17072,17073,17074,17075},set(a["graphic_ids"].values()))
 def test_fresh_allocation_skips_source_and_registry_collisions(self):
  registry={**self.registry,"allocations":{"frozen_hastati_integration":self.registry["allocations"]["frozen_hastati_integration"]}};allocation=resolve_allocation(Workspace(),registry,"new-manifest","infantry_melee_visual_test_v1");self.assertEqual(2113,allocation["unit_id"]);self.assertEqual([17072,17073,17074,17075],[allocation["graphic_ids"][key] for key in ("idle","walk","attack","death")])
 def test_hastati_reservation_cannot_collide(self):
  allocation=resolve_allocation(Workspace(),self.registry,"611db84c371e707bbf8c14626402077a8974f7d8c14af1941b0f38905f39625b","infantry_melee_visual_test_v1");frozen=self.registry["allocations"]["frozen_hastati_integration"];self.assertNotEqual(frozen["unit_id"],allocation["unit_id"]);self.assertFalse(set(frozen["graphic_ids"].values())&set(allocation["graphic_ids"].values()))
 def test_variable_manifest_timing_is_data(self):
  expected={"idle":(43,15),"walk":(23,20),"attack":(27,20),"death":(33,15)};self.assertEqual(expected,{category:(row["frame_count"],row["fps"]) for category,row in self.manifest["animations"].items()})
 def test_logical_names_are_generic(self):self.assertEqual("rome2aoe2_roman_legionary_walk",category_stem("Roman Legionary","walk"))
 def test_attack_return_selector_is_part_of_visual_contract(self):self.assertEqual("idle",LIVE_GRAPHIC_FIELDS["idle_attack_graphic_id"])
 def test_builder_has_no_unit_conditionals(self):
  source=(ROOT/"src/aoe2/build_manifest_dev_integration.py").read_text();self.assertNotIn('if unit_name == "Rom_Principes"',source);self.assertNotIn('if unit_name == "Rom_Hastati"',source);self.assertIn("clone.dead_unit_id",source);self.assertIn("attack_timing_adjustment",source);self.assertIn("source_dat_unchanged",source)
 def test_profile_is_explicitly_visual_only(self):
  profile=json.loads((ROOT/"config/aoe2/integration_profiles/infantry_melee_visual_test_v1.json").read_text());self.assertEqual(74,profile["template_unit_id"]);self.assertEqual(152,profile["expected_template_corpse_unit_id"]);self.assertIn("not final balance",profile["purpose"])
if __name__=="__main__":unittest.main()
