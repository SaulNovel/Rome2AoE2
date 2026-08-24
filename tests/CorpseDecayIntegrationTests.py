import hashlib,json,sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"build/python-deps/pillow")]
from PIL import Image
from aoe2.dat_integration import apply_generated_corpse_contract,resolve_allocation,resolve_corpse_allocation,validate_generated_corpse_contract
from aoe2.sld import parse_sld,serialize_sld
from aoe2.sld_authoring import author_facet_animation
from rome2aoe2.corpse_decay import GENERATED,generate_decay_images,resolve_corpse_policy,transform_frame

class Manager:
 def __init__(self,occupied):self.occupied=set(occupied)
 def exists(self,index):return index in self.occupied
class Workspace:
 def __init__(self):self.unit_manager=Manager(set(range(2081))|set(range(2082,2113)));self.graphic_manager=Manager(set(range(17068)));self.dat=SimpleNamespace(civilizations=[SimpleNamespace(units=[None]*2701)],sprites=[None]*18000)
class Unit:
 def __init__(self,id):self.id=id;self.standing_sprite_id1=1103;self.standing_sprite_id2=-1;self.walking_graphic_id=-1;self.running_graphic_id=-1;self.attack_graphic_id=-1;self.attack_graphic2=-1;self.dying_sprite_id=-1;self.undead_sprite_id=-1;self.dead_unit_id=152

class CorpseDecayIntegrationTests(unittest.TestCase):
 def setUp(self):self.registry=json.loads((ROOT/"config/aoe2/integration_allocations.json").read_text());self.key=next(k for k in self.registry["allocations"] if k.endswith(":infantry_melee_visual_test_v1"));self.manifest_hash=self.key.split(":")[0]
 def test_default_optional_and_timing(self):
  self.assertEqual("inherit_template",resolve_corpse_policy()["mode"]);p=resolve_corpse_policy({"mode":GENERATED});self.assertEqual((10,20,15,35),(p["corpse_fps"],round(p["corpse_linger_seconds"]*p["corpse_fps"]),round(p["corpse_sink_seconds"]*p["corpse_fps"]),35))
 def test_final_composition_anchor_sink_fade_and_shadow(self):
  main=Image.new("RGBA",(40,40));main.putpixel((7,8),(200,10,10,255));main.putpixel((30,9),(180,180,180,255));shadow=Image.new("RGBA",(40,40));shadow.putpixel((8,10),(0,0,0,128));frames=generate_decay_images(main,shadow,{"mode":GENERATED,"corpse_fps":2,"corpse_linger_seconds":1,"corpse_sink_seconds":1,"sink_pixels_x2":4})
  self.assertEqual(main.tobytes(),frames[0][0].tobytes());self.assertEqual((7,8),frames[0][0].getchannel("A").getbbox()[:2]);self.assertEqual((7,12),transform_frame(main,4,1).getchannel("A").getbbox()[:2]);self.assertTrue(all(f[2]["y_offset"]>=0 for f in frames));self.assertTrue(all(f[2]["shadow_alpha"]<=1 for f in frames));self.assertIsNotNone(frames[-1][2]["clip_y"]);self.assertEqual(0,frames[-1][2]["alpha"]);self.assertEqual(0,frames[-1][2]["shadow_alpha"])
 def test_generated_allocation_is_deterministic_and_default_has_no_extra(self):
  default=resolve_allocation(Workspace(),self.registry,self.manifest_hash,"infantry_melee_visual_test_v1");self.assertNotIn("corpse_unit_id",default);a=resolve_allocation(Workspace(),self.registry,self.manifest_hash,"infantry_melee_visual_test_v1",GENERATED);b=resolve_allocation(Workspace(),self.registry,self.manifest_hash,"infantry_melee_visual_test_v1",GENERATED);self.assertEqual(a,b);self.assertEqual((2114,17076),(a["corpse_unit_id"],a["corpse_graphic_id"]))
 def test_contract_remaps_only_generated_path_and_rejects_militia_graphic(self):
  live,corpse=Unit(2113),Unit(2114);apply_generated_corpse_contract(live,corpse,17076);audit=validate_generated_corpse_contract(live,corpse,17076,(1103,));self.assertEqual(2114,live.dead_unit_id);self.assertFalse(audit["retained"])
 def test_sld_repeat_is_deterministic_and_readable(self):
  main=Image.new("RGBA",(40,40),(100,40,20,255));shadow=Image.new("RGBA",(40,40),(0,0,0,64));frames=[(main,shadow,None)]*16;payload=serialize_sld(author_facet_animation(frames,(20,24),16,1));self.assertEqual(hashlib.sha256(payload).digest(),hashlib.sha256(serialize_sld(author_facet_animation(frames,(20,24),16,1))).digest());self.assertEqual(16,len(parse_sld(payload).frames))
 def test_builder_is_generic_and_separate(self):
  source=(ROOT/"src/aoe2/build_fast_corpse_dev_integration.py").read_text();self.assertNotIn("2113",source);self.assertNotIn("17076",source);self.assertIn("FAST Corpse Test",source);self.assertIn("dead_unit_not_152",source)

if __name__=="__main__":unittest.main()
