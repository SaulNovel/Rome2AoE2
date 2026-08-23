import sys,unittest
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from rome2aoe2.dev_asset_refresh import (IntegrationCompatibilityError,sha256,
                                         transactional_replace_assets,
                                         validate_existing_integration)
from rome2aoe2.production_reports import sld_category_root

CATEGORIES=("idle","walk","attack","death")
IDS={"idle":17072,"walk":17073,"attack":17074,"death":17075}
COUNTS={"idle":43,"walk":23,"attack":27,"death":33}
FPS={"idle":15,"walk":20,"attack":20,"death":15}

class AssetRefreshTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):(ROOT/"build/tmp").mkdir(parents=True,exist_ok=True)
 def fixture(self):
  manifest={"animations":{c:{"frame_count":COUNTS[c],"fps":FPS[c]} for c in CATEGORIES}}
  profile={"expected_template_corpse_unit_id":152,"scenario":{"players":2,"units_per_player":15}}
  allocation={"unit_id":2113,"graphic_ids":dict(IDS)}
  unit=SimpleNamespace(standing_sprite_id1=17072,standing_sprite_id2=17072,walking_graphic_id=17073,attack_graphic_id=17074,dying_sprite_id=17075,dead_unit_id=152)
  graphics={c:SimpleNamespace(id=IDS[c],frame_count=COUNTS[c],angle_count=16,frame_duration=1/FPS[c]) for c in CATEGORIES}
  return manifest,profile,allocation,unit,graphics,{"1":15,"2":15}
 def test_compatible_refresh_changes_only_expected_assets_and_preserves_other_files(self):
  validate_existing_integration(*self.fixture())
  root=ROOT/"build/tmp/dev-asset-refresh-tests/success";root.mkdir(parents=True,exist_ok=True);dat=root/"empires.dat";scenario=root/"test.scenario";other=root/"other.bin";dat.write_bytes(b"dat");scenario.write_bytes(b"scenario");other.write_bytes(b"other");before=(sha256(dat),sha256(scenario),sha256(other));assets=[]
  for index in range(8):
   source=root/f"source-{index}.sld";source.write_bytes(f"new-{index}".encode());destination=root/"graphics"/f"asset-{index}.sld";destination.parent.mkdir(exist_ok=True);destination.write_bytes(b"old");assets.append({"source":str(source),"destination":str(destination),"sha256":sha256(source)})
  result=transactional_replace_assets(assets);self.assertTrue(all(item["match"] for item in result));self.assertEqual(before,(sha256(dat),sha256(scenario),sha256(other)));self.assertEqual({Path(item["destination"]) for item in assets},{path for path in (root/"graphics").glob("*.sld")})
 def test_incompatible_mappings_frames_timing_and_ids_refuse(self):
  for field,mutate,reason in (
   ("mapping",lambda unit,graphics:setattr(unit,"walking_graphic_id",999),"INTEGRATION_MAPPING_MISMATCH"),
   ("frames",lambda unit,graphics:setattr(graphics["walk"],"frame_count",22),"INTEGRATION_FRAME_MISMATCH"),
   ("timing",lambda unit,graphics:setattr(graphics["attack"],"frame_duration",0.2),"INTEGRATION_TIMING_MISMATCH"),
   ("graphic-id",lambda unit,graphics:setattr(graphics["death"],"id",999),"INTEGRATION_GRAPHIC_ID_MISMATCH")):
   with self.subTest(field=field):
    manifest,profile,allocation,unit,graphics,counts=self.fixture();mutate(unit,graphics)
    with self.assertRaises(IntegrationCompatibilityError) as caught:validate_existing_integration(manifest,profile,allocation,unit,graphics,counts)
    self.assertEqual(reason,caught.exception.reason)
 def test_missing_sld_refuses_before_mutation(self):
  root=ROOT/"build/tmp/dev-asset-refresh-tests/missing";root.mkdir(parents=True,exist_ok=True);destination=root/"installed-0.sld";destination.write_bytes(b"old");assets=[]
  for index in range(8):
   source=root/f"source-{index}.sld"
   if index!=5:source.write_bytes(b"new")
   elif source.exists():source.unlink()
   assets.append({"source":str(source),"destination":str(root/f"installed-{index}.sld"),"sha256":sha256(source) if source.is_file() else "x"})
  with self.assertRaises(IntegrationCompatibilityError) as caught:transactional_replace_assets(assets)
  self.assertEqual("INTEGRATION_SLD_MISSING",caught.exception.reason);self.assertEqual(b"old",destination.read_bytes())
 def test_explicit_profile_scopes_sld_source(self):
  v2=sld_category_root("Any Unit","a"*64,"idle","aoe2-profile-two");v99=sld_category_root("Any Unit","a"*64,"idle","aoe2-profile-v99");self.assertNotEqual(v2,v99);self.assertIn("aoe2-profile-v99",v99.parts)
 def test_builder_remains_generic(self):
  source=(ROOT/"src/aoe2/build_manifest_dev_integration.py").read_text().casefold();self.assertNotIn("rom_principes",source);self.assertIn("--assets-only",source);self.assertIn("transactional_replace_assets",source);self.assertNotIn("parsed.facet_count",source);self.assertIn('encoded.get("directions")!=16',source)

if __name__=="__main__":unittest.main()
