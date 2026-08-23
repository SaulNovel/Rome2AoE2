import json, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/"src")]
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.production import PROFILE
from rome2aoe2.production_reports import (MATERIAL_BACKEND,ProductionReportError,consolidate_category,
                                          resolve_consolidated_category,sld_category_root)

MANIFEST=ROOT/"config/manifests/rom_principes-explicit-animations-v2.json"
V3="aoe2-infantry-animation-production-v3-weapon-forward"

class ProductionProfilePlumbingTests(unittest.TestCase):
 def test_v1_layout_and_consolidation_remain_compatible(self):
  request=load_and_validate_manifest(MANIFEST);report=consolidate_category(request,"idle",PROFILE)
  self.assertEqual(PROFILE,report["production_profile"]);self.assertEqual(688,report["output_inventory"]["main_x2"]);self.assertEqual(688,report["output_inventory"]["shadow_x2"])
  root=sld_category_root("Rom_Principes",request.manifest_hash,"idle",PROFILE)
  self.assertEqual("idle",root.name);self.assertNotIn(PROFILE,root.parts)
  _,resolved=resolve_consolidated_category(request,"idle",PROFILE);self.assertEqual(PROFILE,resolved["production_profile"])
 def test_approved_v3_resolves_without_special_case(self):
  request=load_and_validate_manifest(MANIFEST)
  expected={"idle":"755bb608f930291c","walk":"f1389c0919e1e947","attack":"339e2e1c6eef62e2","death":"fd4c3fa460895604"}
  for category,identity in expected.items():
   report=consolidate_category(request,category,V3);self.assertEqual(V3,report["production_profile"]);self.assertEqual(identity,report["production_identity"]);self.assertEqual(0,report["validation"]["confirmed_overflow_count"]);self.assertEqual(0.6,report["main_illumination"]["readability_fill_linear"]);self.assertEqual(0.0,report["main_illumination"]["captured_environment_yaw_degrees"]);self.assertFalse(report["main_illumination"]["material_equations_modified"])
  temporary=ROOT/"build/tmp/v3-consolidated-idle.json";temporary.write_text(json.dumps(consolidate_category(request,"idle",V3)))
  with patch("rome2aoe2.production_reports.production_report_path",return_value=temporary):_,resolved=resolve_consolidated_category(request,"idle",V3)
  self.assertEqual(V3,resolved["production_profile"])
 def test_future_profile_name_flows_when_profile_capabilities_exist(self):
  future="aoe2-test-production-v99";root=ROOT/"build/tmp/profile-v99";category="idle";samples=1
  record={"frame_count":samples,"fps":15.0,"resolved_asset":"synthetic.anim"};request=SimpleNamespace(manifest={"visual_scale":1.0,"animations":{category:record}},manifest_hash="f"*64,unit=SimpleNamespace(definition=SimpleNamespace(main_unit="Synthetic")))
  root.mkdir(parents=True,exist_ok=True);records=[{"direction":d,"output_frame":0,"canvas_validation":{"confirmed_overflow":False}} for d in range(16)]
  common={"manifest_hash":request.manifest_hash,"category":category,"animation_asset":"synthetic.anim","native_source_samples":1,"direction_order":list(range(16)),"direction_yaws":[(292.5-22.5*i)%360 for i in range(16)],"visual_scale":1.0,"canonical_orthographic_scale":7.27480212108078,"effective_orthographic_scale":7.27480212108078,"action_fingerprint_before":"fingerprint","action_fingerprint_after":"fingerprint","records":records}
  hotspot={"x1":[100,122],"x2":[200,244],"ground_anchor":"unchanged"}
  (root/"render-report.json").write_text(json.dumps({**common,"profile":future,"main_illumination":{"captured_environment_yaw_degrees":0.0,"readability_fill_linear":0.5},"rendered_sample_mapping":[{"source_sample":0,"blender_frame":0.0}],"material_backend":MATERIAL_BACKEND,"canvas":{"master":[800,800],"x2":[400,400],"x1":[200,200]},"hotspot_policy":hotspot}))
  (root/"shadow-report.json").write_text(json.dumps({**common,"profile":"synthetic-shadow","canvas":{"x2":[400,400],"x1":[200,200]},"hotspot_policy":hotspot}))
  for kind,scale in (("main","master"),("main","x1"),("main","x2"),("shadow","x1"),("shadow","x2")):
   folder=root/kind/scale;folder.mkdir(parents=True,exist_ok=True)
   for d in range(16):(folder/f"idle-direction-{d:02d}-frame-000.png").touch()
  profile={"name":future,"main_illumination":{"captured_environment_yaw_degrees":0.0,"readability_fill_linear":0.5},"attachment_capabilities":{"one_handed_blade/weapon_02":"future-capability"},"shadow":{"profile":"synthetic-shadow"}}
  with patch("rome2aoe2.production_reports.resolve_production_profile",return_value=profile),patch("rome2aoe2.production_reports.category_output",return_value=root):report=consolidate_category(request,category,future)
  self.assertEqual(future,report["production_profile"]);self.assertEqual("future-capability",report["attachment_capabilities"]["one_handed_blade/weapon_02"]);self.assertEqual(profile["main_illumination"],report["main_illumination"])
  (root/"production-report.json").write_text(json.dumps(report))
  with patch("rome2aoe2.production_reports.resolve_production_profile",return_value=profile),patch("rome2aoe2.production_reports.category_output",return_value=root):_,resolved=resolve_consolidated_category(request,category,future)
  self.assertEqual(0.5,resolved["main_illumination"]["readability_fill_linear"])
 def test_source_and_cross_category_illumination_disagreement_fails(self):
  request=load_and_validate_manifest(MANIFEST)
  for category in ("idle","walk"):
   with self.subTest(category=category):
    root=Path(consolidate_category(request,category,V3)["category_root"]);document=json.loads((root/"render-report.json").read_text());document["main_illumination"]["readability_fill_linear"]=0.0
    with patch("rome2aoe2.production_reports._main_reports",return_value=[document]):
     with self.assertRaises(ProductionReportError) as caught:consolidate_category(request,category,V3)
    self.assertEqual("PRODUCTION_PROFILE_MISMATCH",caught.exception.reason)
 def test_orchestration_entry_points_are_profile_explicit(self):
  for relative in ("src/aoe2/author_manifest_production_sld.py","src/aoe2/build_manifest_dev_integration.py"):
   source=(ROOT/relative).read_text();self.assertIn("--production-profile",source);self.assertIn("resolve_consolidated_category",source);self.assertNotIn("camera_profile\"]!=PROFILE",source)
  self.assertNotIn("production_profile",(ROOT/"src/aoe2/sld_authoring.py").read_text())

if __name__=="__main__":unittest.main()
