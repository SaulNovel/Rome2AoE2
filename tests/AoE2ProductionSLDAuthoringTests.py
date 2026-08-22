import json,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"build/python-deps/pillow"),str(ROOT)]
from PIL import Image
from aoe2.sld import LAYER_MAIN,LAYER_PLAYERCOLOR,LAYER_SHADOW,parse_sld,serialize_sld
from aoe2.sld_authoring import author_sld_animation
from aoe2.sld_blocks import encode_bc1_block
from rome2aoe2.conversion import load_and_validate_manifest
class BasicAdapter:
 def prepare(self,image,threshold):pass
 def encode_at(self,tile,threshold,x,y):return encode_bc1_block(tile,threshold)
class ProductionSLDTests(unittest.TestCase):
 def setUp(self):
  self.request=load_and_validate_manifest(ROOT/"config/manifests/rom_principes-explicit-animations-v2.json");self.temporary_root=ROOT/"build/tmp";self.temporary_root.mkdir(parents=True,exist_ok=True)
 def report(self,root):
  return {"format":"rome2aoe2.consolidated-production-category","category":"idle","native_frames":1,"direction_order":list(range(16)),"direction_yaws":[(292.5-22.5*i)%360 for i in range(16)],"x1_dimensions":[200,200],"x2_dimensions":[400,400],"output_inventory":{"root":str(root)}}
 def test_generic_production_report_x1_round_trip(self):
  root=self.temporary_root/"round-trip";(root/"main/x1").mkdir(parents=True,exist_ok=True);(root/"shadow/x1").mkdir(parents=True,exist_ok=True)
  for direction in range(16):
   name=f"idle-direction-{direction:02d}-frame-000.png";Image.new("RGBA",(200,200),(direction*8,40,20,255)).save(root/"main/x1"/name);Image.new("RGBA",(200,200),(0,0,0,64)).save(root/"shadow/x1"/name)
  output=root/"idle_x1.sld"
  with patch("aoe2.sld_authoring.DirectXTexBC1Encoder",return_value=BasicAdapter()):result=author_sld_animation(self.report(root),"x1",root/"texconv.exe",output)
  parsed=parse_sld(output.read_bytes());self.assertEqual(16,len(parsed.frames));self.assertEqual((100,122),(parsed.frames[0].center_x,parsed.frames[0].center_y));self.assertTrue(all(frame.frame_type==LAYER_MAIN|LAYER_SHADOW for frame in parsed.frames));self.assertFalse(any(frame.frame_type&LAYER_PLAYERCOLOR for frame in parsed.frames));self.assertEqual("facet-major; production directions 0..15 unchanged",result["frame_order"])
 def test_manifest_category_sample_contract(self):
  self.assertEqual({"idle":43,"walk":23,"attack":27,"death":33},{key:value["frame_count"] for key,value in self.request.manifest["animations"].items()})
 def test_production_adapter_has_no_unit_special_cases(self):
  source=(ROOT/"src/aoe2/author_manifest_production_sld.py").read_text().casefold();self.assertNotIn("rom_principes",source);self.assertNotIn("rom_hastati",source)
 def test_canonical_direction_contract(self):
  self.assertEqual([292.5,270.0,247.5,225.0],[(292.5-22.5*i)%360 for i in range(4)])
 def test_deterministic_serializer(self):
  root=self.temporary_root/"determinism";(root/"main/x1").mkdir(parents=True,exist_ok=True);(root/"shadow/x1").mkdir(parents=True,exist_ok=True)
  for direction in range(16):
   name=f"idle-direction-{direction:02d}-frame-000.png";Image.new("RGBA",(200,200),(20,40,60,255)).save(root/"main/x1"/name);Image.new("RGBA",(200,200),(0,0,0,64)).save(root/"shadow/x1"/name)
  with patch("aoe2.sld_authoring.DirectXTexBC1Encoder",return_value=BasicAdapter()):
   first=author_sld_animation(self.report(root),"x1",root/"texconv.exe",root/"a.sld");second=author_sld_animation(self.report(root),"x1",root/"texconv.exe",root/"b.sld")
  self.assertEqual(first["sha256"],second["sha256"]);self.assertEqual((root/"a.sld").read_bytes(),(root/"b.sld").read_bytes())
if __name__=="__main__":unittest.main()
