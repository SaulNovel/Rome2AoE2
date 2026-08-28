import sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from aoe2.dat_integration import apply_visual_contract,reachable_graphics,validate_visual_contract
from rome2aoe2.corpse_decay import GENERATED,decay_frames,resolve_corpse_policy
from rome2aoe2.render_modes import render_identity,require_release_eligible,resolve_render_mode,sample_policy

class Unit:
 def __init__(self,base=100):
  self.standing_sprite_id1=base;self.standing_sprite_id2=base+1;self.walking_graphic_id=base+2;self.running_graphic_id=base+3;self.attack_graphic_id=base+4;self.attack_graphic2=base+5;self.dying_sprite_id=base+6;self.undead_sprite_id=-1
  task=SimpleNamespace(move_sprite_id=base+2,proceed_sprite_id=base+3,work_sprite_id=base+4,carry_sprite_id=base+5)
  self._unit=SimpleNamespace(task_info=SimpleNamespace(tasks=[task]))

class GenericFollowupCapabilitiesTests(unittest.TestCase):
 def test_visual_contract_replaces_alternate_recovery_and_task_graphics(self):
  source=Unit();clone=Unit();ids={"idle":1,"walk":2,"attack":3,"death":4};apply_visual_contract(clone,ids);audit=validate_visual_contract(clone,source,ids)
  self.assertFalse(audit["retained"]);self.assertEqual(set(reachable_graphics(clone).values()),set(ids.values()))
 def test_full_default_and_fast_isolated(self):
  self.assertEqual("full",resolve_render_mode()["render_mode"]);self.assertEqual(["x1","x2"],resolve_render_mode()["output_scales"]);fast=resolve_render_mode("fast");self.assertEqual(["x2"],fast["output_scales"]);self.assertEqual("x2/400x400 retained",fast["high_definition_output"]);self.assertEqual("x1/200x200 omitted",fast["low_definition_output"]);self.assertNotEqual(render_identity("full",asset="x"),render_identity("fast",asset="x"))
  with self.assertRaises(RuntimeError):require_release_eligible({"render_mode":"fast","release_eligible":False})
 def test_fast_sampler_preserves_duration_and_endpoints(self):
  p=sample_policy(33,15,False);self.assertEqual(17,p["test_sample_count"]);self.assertEqual(p["source_duration"],p["test_duration"]);self.assertEqual(0,p["times_seconds"][0]);self.assertEqual(p["source_duration"],p["times_seconds"][-1])
  loop=sample_policy(20,20,True);self.assertEqual(10,loop["test_sample_count"]);self.assertLess(loop["times_seconds"][-1],loop["source_duration"])
 def test_corpse_default_optional_anchor_and_equipment_source(self):
  self.assertEqual("inherit_template",resolve_corpse_policy()["mode"]);frames=decay_frames("final-death-main","final-death-shadow",10,{"mode":GENERATED,"corpse_linger_seconds":.2,"corpse_sink_seconds":.4})
  self.assertTrue(all(f["main"]=="final-death-main" and f["shadow"]=="final-death-shadow" for f in frames));self.assertEqual(0,frames[0]["y_offset"]);self.assertEqual(sorted(f["y_offset"] for f in frames),[f["y_offset"] for f in frames]);self.assertEqual(0,frames[-1]["alpha"])
if __name__=="__main__":unittest.main()
