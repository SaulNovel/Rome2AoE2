"""Build an isolated AoE2 dev DAT/mod/scenario from frozen generic outputs."""
from __future__ import annotations
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
sys.stdout.reconfigure(encoding="utf-8",errors="replace")
from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.datasets.trigger_lists import DiplomacyState
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from aoe2.dat_integration import CATEGORIES,RUNTIME_FIELDS,allocation_key,category_stem,clone_graphic,install_slds,reference_graphic_id,resolve_allocation,sha256,slug
from aoe2.sld import LAYER_MAIN,LAYER_SHADOW,parse_sld
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.dev_asset_refresh import transactional_replace_assets,validate_existing_integration
from rome2aoe2.production import PROFILE
from rome2aoe2.production_reports import resolve_consolidated_category,sld_category_root

def snapshot_unit(unit):return {field:getattr(unit,field) for field in ("name","standing_sprite_id1","standing_sprite_id2","walking_graphic_id","attack_graphic_id","dying_sprite_id","dead_unit_id","reload_time","displayed_reload_time")}
def scenario(template,output,report_path,unit_id,profile):
 document=AoE2DEScenario.from_file(str(template));document.player_manager.active_players=2;document.player_manager.players[1].set_player_diplomacy([2],DiplomacyState.ENEMY);document.player_manager.players[2].set_player_diplomacy([1],DiplomacyState.ENEMY)
 placements=[];rows=(44.0,54.0,64.0)
 for player,base_x,nominal in ((1,34.0,0.0),(2,76.0,math.pi)):
  document.player_manager.players[player].initial_player_view_x=55;document.player_manager.players[player].initial_player_view_y=54
  for group,y in enumerate(rows,1):
   for column in range(5):
    item={"player":player,"group":group,"unit_id":unit_id,"x":base_x+column*1.8 if player==1 else base_x-column*1.8,"y":y,"rotation":(nominal+(column-2)*math.pi/8)%(2*math.pi)};placements.append(item);document.unit_manager.add_unit(player=player,unit_const=unit_id,x=item["x"],y=y,rotation=item["rotation"])
 output.parent.mkdir(parents=True,exist_ok=True);document.write_to_file(str(output));written=AoE2DEScenario.from_file(str(output));counts={str(player):sum(unit.unit_const==unit_id for unit in written.unit_manager.units[player]) for player in (1,2)}
 if counts!={"1":15,"2":15}:raise RuntimeError(f"scenario unit counts changed: {counts}")
 result={"format":"rome2aoe2.dev-integration-scenario","version":1,"scenario":str(output),"unit_id":unit_id,"player_counts":counts,"mutual_enemies":True,"placements":placements};report_path.parent.mkdir(parents=True,exist_ok=True);report_path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");return result
def asset_only(request,args,profile,registry,output_root,mod,scenario_path):
 key=allocation_key(request.manifest_hash,profile["id"]);allocation=registry["allocations"].get(key)
 if allocation is None:raise RuntimeError(f"asset-only refresh requires an existing allocation: {key}")
 dat_path=mod/"resources/_common/dat/empires2_x2_p1.dat";dat_before=sha256(dat_path);scenario_before=sha256(scenario_path);workspace=GenieWorkspace.load(dat_path);unit=workspace.unit_manager.get(allocation["unit_id"])
 graphics={category:workspace.graphic_manager.get(graphic_id) for category,graphic_id in allocation["graphic_ids"].items()};document=AoE2DEScenario.from_file(str(scenario_path));counts={str(player):sum(item.unit_const==allocation["unit_id"] for item in document.unit_manager.units[player]) for player in range(1,profile["scenario"]["players"]+1)}
 compatibility=validate_existing_integration(request.manifest,profile,allocation,unit,graphics,counts);unit_name=request.unit.definition.main_unit;graphics_root=mod/"resources/_common/drs/graphics";assets=[]
 for category in CATEGORIES:
  record=request.manifest["animations"][category];_,production=resolve_consolidated_category(request,category,args.production_profile);sld_root=sld_category_root(unit_name,request.manifest_hash,category,args.production_profile);sld_report_path=sld_root/f"{category}-sld-report.json"
  if not sld_report_path.is_file():raise RuntimeError(f"missing validated SLD report: {sld_report_path}")
  sld_report=json.loads(sld_report_path.read_text());
  if sld_report.get("production_profile")!=args.production_profile or sld_report.get("production_identity")!=production["production_identity"] or sld_report.get("frames_per_direction")!=record["frame_count"]:raise RuntimeError(f"SLD report identity mismatch: {category}")
  for scale in ("x1","x2"):
   encoded=sld_report["encoded"][scale];source=Path(encoded["path"])
   if not source.is_file() or sha256(source)!=encoded["sha256"]:raise RuntimeError(f"SLD source hash mismatch: {category}/{scale}")
   parsed=parse_sld(source.read_bytes())
   dimensions=(200,200) if scale=="x1" else (400,400);hotspot=(100,122) if scale=="x1" else (200,244)
   if parsed.version!=4 or encoded.get("directions")!=16 or len(parsed.frames)!=16*record["frame_count"] or any(frame.frame_type!=(LAYER_MAIN|LAYER_SHADOW) or (frame.canvas_width,frame.canvas_height)!=dimensions or (frame.center_x,frame.center_y)!=hotspot for frame in parsed.frames):raise RuntimeError(f"SLD structure mismatch: {category}/{scale}")
   destination=graphics_root/f"{category_stem(unit_name,category)}_{scale}.sld";assets.append({"category":category,"scale":scale,"source":str(source),"destination":str(destination),"sha256":encoded["sha256"]})
 installed=transactional_replace_assets(assets);dat_after=sha256(dat_path);scenario_after=sha256(scenario_path)
 if dat_after!=dat_before or scenario_after!=scenario_before:raise RuntimeError("asset-only refresh modified DAT or scenario")
 result={"format":"rome2aoe2.asset-only-dev-refresh","version":1,"manifest_hash":request.manifest_hash,"production_profile":args.production_profile,"mod":str(mod),"scenario":str(scenario_path),"dat":{"path":str(dat_path),"sha256_before":dat_before,"sha256_after":dat_after,"unchanged":True},"scenario_file":{"path":str(scenario_path),"sha256_before":scenario_before,"sha256_after":scenario_after,"unchanged":True},"compatibility":compatibility,"installed_assets":installed,"validation":{"asset_count":len(installed),"all_hashes_match":all(item["match"] for item in installed),"only_sld_assets_modified":True}}
 report=args.refresh_report or output_root/"asset-refresh-report.json";report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");print(report);return
def main():
 parser=argparse.ArgumentParser();parser.add_argument("manifest",type=Path);parser.add_argument("--expected-manifest-hash",required=True);parser.add_argument("--production-profile",default=PROFILE);parser.add_argument("--source-dat",type=Path);parser.add_argument("--template-scenario",type=Path);parser.add_argument("--profile",type=Path,default=ROOT/"config/aoe2/integration_profiles/infantry_melee_visual_test_v1.json");parser.add_argument("--registry",type=Path,default=ROOT/"config/aoe2/integration_allocations.json");parser.add_argument("--assets-only",action="store_true");parser.add_argument("--existing-mod",type=Path);parser.add_argument("--existing-scenario",type=Path);parser.add_argument("--refresh-report",type=Path);args=parser.parse_args()
 request=load_and_validate_manifest(args.manifest)
 if request.manifest_hash!=args.expected_manifest_hash:raise RuntimeError(f"manifest identity mismatch: {request.manifest_hash}")
 profile=json.loads(args.profile.read_text());registry=json.loads(args.registry.read_text());unit_name=request.unit.definition.main_unit;display_name=unit_name.split("_",1)[-1].replace("_"," ")
 output_root=ROOT/"build/dev-test/rome2aoe2"/slug(unit_name)/request.manifest_hash[:16];mod=output_root/f"Rome2AoE2 {display_name} Dev Test";graphics_root=mod/"resources/_common/drs/graphics";dat_path=mod/"resources/_common/dat/empires2_x2_p1.dat";dat_path.parent.mkdir(parents=True,exist_ok=True)
 if args.assets_only:
  mod=args.existing_mod or mod;scenario_path=args.existing_scenario or output_root/f"Rome2AoE2{display_name.replace(' ','')}DevTest.aoe2scenario";return asset_only(request,args,profile,registry,output_root,mod,scenario_path)
 if args.source_dat is None or args.template_scenario is None:parser.error("full integration requires --source-dat and --template-scenario")
 source_hash=sha256(args.source_dat);workspace=GenieWorkspace.load(args.source_dat);allocation=resolve_allocation(workspace,registry,request.manifest_hash,profile["id"]);template=workspace.unit_manager.get(profile["template_unit_id"]);template_before=snapshot_unit(template)
 sld_reports={};production_reports={}
 for category in CATEGORIES:
  record=request.manifest["animations"][category];production_path,production=resolve_consolidated_category(request,category,args.production_profile);sld_path=sld_category_root(unit_name,request.manifest_hash,category,args.production_profile)/f"{category}-sld-report.json";sld=json.loads(sld_path.read_text())
  if production["manifest_hash"]!=request.manifest_hash or production["production_profile"]!=args.production_profile or production["native_frames"]!=record["frame_count"]:raise RuntimeError(f"production identity mismatch: {category}")
  if sld["manifest_hash"]!=request.manifest_hash or sld["production_profile"]!=args.production_profile or sld["frames_per_direction"]!=record["frame_count"] or sld["total_frames"]!=16*record["frame_count"]:raise RuntimeError(f"SLD identity mismatch: {category}")
  production_reports[category]=(production_path,production);sld_reports[category]=(sld_path,sld)
 clone=workspace.unit_manager.clone_into(allocation["unit_id"],profile["template_unit_id"],on_conflict="error",fill_gaps="placeholder");clone.name=f"Rome II {display_name} visual test";graphics={};graphic_receipts={}
 for category in CATEGORIES:
  record=request.manifest["animations"][category];reference_id=reference_graphic_id(template,category);reference=workspace.dat.sprites[reference_id];graphic_id=allocation["graphic_ids"][category];stem=category_stem(unit_name,category);graphic=clone_graphic(workspace,reference,graphic_id,stem,f"{display_name} {category}",record["frame_count"],record["fps"]);graphics[category]=graphic
  graphic_receipts[category]={"graphic_id":graphic_id,"reference_graphic_id":reference_id,"logical_filename":stem,"frames_per_direction":record["frame_count"],"directions":16,"fps":record["fps"],"frame_duration":1/record["fps"],"sequence_duration":record["frame_count"]/record["fps"],"source_pose_span":record["duration"],"loop_semantics":category in {"idle","walk"},"runtime_fields":{field:getattr(reference,field) for field in RUNTIME_FIELDS},"source_animation":record["resolved_asset"],"production_report":str(production_reports[category][0]),"sld_report":str(sld_reports[category][0])}
 clone.standing_sprite_id1=clone.standing_sprite_id2=graphics["idle"].id;clone.walking_graphic_id=graphics["walk"].id;clone.attack_graphic_id=graphics["attack"].id;clone.dying_sprite_id=graphics["death"].id
 attack_duration=request.manifest["animations"]["attack"]["frame_count"]/request.manifest["animations"]["attack"]["fps"];attack_adjustment=None
 if profile["attack_timing_policy"]=="raise_reload_only_if_shorter_than_animation" and clone.reload_time<attack_duration:
  attack_adjustment={"reload_time_before":clone.reload_time,"reload_time_after":attack_duration};clone.reload_time=attack_duration;clone.displayed_reload_time=attack_duration
 if clone.dead_unit_id!=profile["expected_template_corpse_unit_id"]:raise RuntimeError(f"template corpse changed: {clone.dead_unit_id}")
 workspace.save(dat_path);written=GenieWorkspace.load(dat_path);written_template=written.unit_manager.get(profile["template_unit_id"]);written_unit=written.unit_manager.get(allocation["unit_id"])
 if snapshot_unit(written_template)!=template_before:raise RuntimeError("integration modified template unit")
 expected_refs={"idle":allocation["graphic_ids"]["idle"],"walk":allocation["graphic_ids"]["walk"],"attack":allocation["graphic_ids"]["attack"],"death":allocation["graphic_ids"]["death"]};actual_refs={"idle":written_unit.standing_sprite_id1,"walk":written_unit.walking_graphic_id,"attack":written_unit.attack_graphic_id,"death":written_unit.dying_sprite_id}
 if actual_refs!=expected_refs or written_unit.standing_sprite_id2!=expected_refs["idle"]:raise RuntimeError(f"unit graphic mapping mismatch: {actual_refs}")
 for category,expected in graphic_receipts.items():
  graphic=written.graphic_manager.get(expected["graphic_id"]);raw=written.dat.sprites[expected["graphic_id"]]
  if (graphic.frame_count,graphic.angle_count)!=(expected["frames_per_direction"],16) or abs(graphic.frame_duration-expected["frame_duration"])>1e-7:raise RuntimeError(f"graphic metadata mismatch: {category}")
  if any(getattr(raw,field)!=value for field,value in expected["runtime_fields"].items()):raise RuntimeError(f"graphic runtime metadata mismatch: {category}")
 sld_root=sld_category_root(unit_name,request.manifest_hash,CATEGORIES[0],args.production_profile).parent;assets=install_slds(sld_root,graphics_root,unit_name);output_hash=sha256(dat_path)
 if sha256(args.source_dat)!=source_hash:raise RuntimeError("source DAT was modified")
 scenario_path=output_root/f"Rome2AoE2{display_name.replace(' ','')}DevTest.aoe2scenario";scenario_report=scenario(args.template_scenario,scenario_path,output_root/"scenario-report.json",allocation["unit_id"],profile)
 (mod/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":f"Rome2AoE2 {display_name} Dev Test","Description":f"{profile['purpose']} Manifest {request.manifest_hash[:16]}."},indent=2)+"\n")
 receipt={"format":"rome2aoe2.aoe2-dev-integration-receipt","version":2,"manifest_hash":request.manifest_hash,"production_profile":args.production_profile,"integration_profile":profile["id"],"profile":profile,"source_dat":{"path":str(args.source_dat),"sha256":source_hash},"output_dat":{"path":str(dat_path),"sha256":output_hash},"allocation":allocation,"unit":{"name":written_unit.name,"unit_id":allocation["unit_id"],"template_unit_id":profile["template_unit_id"],"template_snapshot":template_before,"graphic_references":actual_refs,"standing_sprite_id2":written_unit.standing_sprite_id2,"corpse_unit_id":written_unit.dead_unit_id,"reload_time":written_unit.reload_time},"graphics":graphic_receipts,"attack_timing_adjustment":attack_adjustment,"death":{"corpse_unit_id":written_unit.dead_unit_id,"dat_sequence_duration":graphic_receipts["death"]["sequence_duration"],"source_pose_span":graphic_receipts["death"]["source_pose_span"],"transition":"inherited Militia sequence_type 11 completes, then dead_unit_id corpse transition"},"installed_assets":assets,"scenario":scenario_report,"modified_dat_records":{"units":[allocation["unit_id"]],"graphics":list(allocation["graphic_ids"].values())},"validation":{"allocation_unique":True,"production_identity":True,"sld_identity":True,"dat_round_trip":True,"source_dat_unchanged":True,"all_sld_hashes_match":True,"no_hastati_graphic_references":not bool(set(actual_refs.values())&{17068,17069,17070,17071})}}
 receipt_path=output_root/"integration-receipt.json";receipt_path.write_text(json.dumps(receipt,indent=2,sort_keys=True)+"\n");print(receipt_path)
if __name__=="__main__":main()
