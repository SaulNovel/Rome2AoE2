"""Verify an installed generic AoE2 visual-test mod against its receipt."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")];sys.stdout.reconfigure(encoding="utf-8",errors="replace")
from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from aoe2.dat_integration import sha256
from aoe2.active_mod_validation import audit_active_dat
from aoe2.scenario_validation import validate_scenario
def verify(receipt_path,mod,scenario_path,status_path=None,mods_root=None,target_status_path=None):
 receipt=json.loads(receipt_path.read_text());dat=mod/"resources/_common/dat/empires2_x2_p1.dat"
 if receipt.get("format")=="rome2aoe2.fast-directional-exposure-dev-integration":
  if sha256(dat)!=receipt["dat"]["sha256"] or sha256(scenario_path)!=receipt["scenario_sha256"]:raise RuntimeError("installed directional-exposure DAT/scenario hash mismatch")
  if status_path is None or mods_root is None or target_status_path is None:raise RuntimeError("directional runtime verification requires game-facing mod activation inputs")
  activation=audit_active_dat(status_path,mods_root,receipt["mod_title"],target_status_path,receipt["dat"]["sha256"]);active_dat=Path(activation["active_dat"]["dat_path"]);workspace=GenieWorkspace.load(active_dat);scenario_validation=validate_scenario(scenario_path,workspace,(receipt["allocation"]["unit_id"],));living=workspace.unit_manager.get(receipt["allocation"]["unit_id"]);corpse=workspace.unit_manager.get(receipt["allocation"]["corpse_unit_id"]);attack=workspace.graphic_manager.get(receipt["allocation"]["graphic_ids"]["attack"]);runtime={"reload_time":living.reload_time,"frame_delay":living.frame_delay,"interrupt_frame":living.interrupt_frame,"idle_attack_graphic_id":living.idle_attack_graphic_id,"sequence_type":workspace.dat.sprites[attack.id].sequence_type}
  if runtime!=receipt["runtime"] or living.dead_unit_id!=corpse.id or corpse.standing_sprite_id1!=receipt["allocation"]["corpse_graphic_id"]:raise RuntimeError("installed directional-exposure runtime/corpse mapping mismatch")
  hashes={}
  for category,asset in receipt["assets"].items():
   path=mod/"resources/_common/drs/graphics"/Path(asset["path"]).name
   if sha256(path)!=asset["sha256"]:raise RuntimeError(f"installed directional-exposure SLD mismatch: {category}")
   graphic=workspace.graphic_manager.get(receipt["graphics"][category]["graphic_id"]);expected=receipt["graphics"][category]
   if (graphic.frame_count,graphic.angle_count)!=(expected["frame_count"],expected["angle_count"]) or abs(graphic.frame_duration-expected["frame_duration"])>1e-6:raise RuntimeError(f"installed directional-exposure graphic mismatch: {category}")
   hashes[path.name]=asset["sha256"]
  unit_id=receipt["allocation"]["unit_id"];corpse_id=receipt["allocation"]["corpse_unit_id"];enabled_civs=[index for index in range(len(workspace.dat.civilizations)) if (workspace.unit_manager.get_unit(unit_id,index) is not None and not workspace.unit_manager._is_placeholder(workspace.unit_manager.get_unit(unit_id,index)) and getattr(workspace.unit_manager.get_unit(unit_id,index),'enabled',0)!=0)];corpse_civs=[index for index in range(len(workspace.dat.civilizations)) if (workspace.unit_manager.get_unit(corpse_id,index) is not None and not workspace.unit_manager._is_placeholder(workspace.unit_manager.get_unit(corpse_id,index)))];graphic_refs={"standing":living.standing_sprite_id1,"walking":living.walking_graphic_id,"attack":living.attack_graphic_id,"death":living.dying_sprite_id};resolved_graphics={name:workspace.graphic_manager.exists(graphic_id) for name,graphic_id in graphic_refs.items()}
  if not enabled_civs or not all(resolved_graphics.values()) or not corpse_civs:raise RuntimeError("active DAT unit/civilization/graphic resolution failed")
  return {"format":"rome2aoe2.fast-directional-exposure-install-verification","version":2,"mod":str(mod),"scenario":str(scenario_path),"scenario_sha256":sha256(scenario_path),"scenario_validation":scenario_validation,"activation":activation,"active_dat_sha256":sha256(active_dat),"unit":{"id":unit_id,"enabled_civilization_ids":enabled_civs,"graphic_references":graphic_refs,"graphics_resolve":resolved_graphics,"dead_unit_id":living.dead_unit_id},"corpse_unit":{"id":corpse_id,"civilization_ids":corpse_civs,"exists":workspace.unit_manager.exists(corpse_id)},"runtime":runtime,"graphics":receipt["graphics"],"sld_hashes":hashes,"corpse_contract":receipt["corpse_contract"],"runtime_claim":"proven against the sole enabled Rome2AoE2 data mod recorded in the game-facing mod-status.json","validation":"passed"}
 if receipt.get("format")=="rome2aoe2.fast-attack-tail-dev-integration":
  if sha256(dat)!=receipt["dat"]["sha256"] or sha256(scenario_path)!=receipt["scenario_sha256"]:raise RuntimeError("installed attack-tail DAT/scenario hash mismatch")
  workspace=GenieWorkspace.load(dat);scenario_validation=validate_scenario(scenario_path,workspace,(receipt["allocation"]["unit_id"],));u=workspace.unit_manager.get(receipt["allocation"]["unit_id"]);g=workspace.graphic_manager.get(receipt["attack"]["graphic_id"]);corpse=workspace.unit_manager.get(receipt["allocation"]["corpse_unit_id"]);cg=workspace.graphic_manager.get(receipt["corpse"]["graphic_id"]);runtime={"reload_time":u.reload_time,"frame_delay":u.frame_delay,"interrupt_frame":u.interrupt_frame,"idle_attack_graphic_id":u.idle_attack_graphic_id,"sequence_type":workspace.dat.sprites[g.id].sequence_type}
  attack_path=mod/"resources/_common/drs/graphics"/Path(receipt["attack"]["sld"]).name;corpse_path=mod/"resources/_common/drs/graphics"/Path(receipt["corpse"]["sld"]["path"]).name
  if runtime!=receipt["runtime"] or (g.frame_count,g.angle_count)!=(receipt["attack"]["frame_count"],receipt["attack"]["angle_count"]) or abs(g.frame_duration-receipt["attack"]["frame_duration"])>1e-7 or sha256(attack_path)!=receipt["attack"]["sha256"]:raise RuntimeError("installed attack-tail contract mismatch")
  if u.dead_unit_id!=corpse.id or corpse.standing_sprite_id1!=cg.id or (cg.frame_count,cg.angle_count)!=(receipt["corpse"]["frame_count"],receipt["corpse"]["angle_count"]) or abs(cg.frame_duration-receipt["corpse"]["frame_duration"])>1e-7 or sha256(corpse_path)!=receipt["corpse"]["sld"]["sha256"]:raise RuntimeError("installed approved corpse contract changed")
  return {"format":"rome2aoe2.fast-attack-tail-install-verification","version":1,"mod":str(mod),"scenario":str(scenario_path),"scenario_validation":scenario_validation,"attack":receipt["attack"],"runtime":runtime,"corpse":{"unit_id":corpse.id,"graphic_id":cg.id,"frame_count":cg.frame_count,"frame_duration":cg.frame_duration,"angle_count":cg.angle_count,"sld_sha256":sha256(corpse_path)},"validation":"passed"}
 if receipt.get("format")=="rome2aoe2.fast-corpse-dev-integration":
  if receipt.get("release_eligible") is not False:raise RuntimeError("FAST corpse receipt unexpectedly release eligible")
  if sha256(dat)!=receipt["dat"]["sha256"] or sha256(scenario_path)!=receipt["scenario_sha256"]:raise RuntimeError("installed FAST corpse DAT/scenario hash mismatch")
  workspace=GenieWorkspace.load(dat);scenario_validation=validate_scenario(scenario_path,workspace,(receipt["allocation"]["unit_id"],));live=workspace.unit_manager.get(receipt["allocation"]["unit_id"]);corpse=workspace.unit_manager.get(receipt["allocation"]["corpse_unit_id"])
  if live.dead_unit_id!=corpse.id or live.dead_unit_id==receipt["profile"]["corpse_template_unit_id"] or corpse.standing_sprite_id1!=receipt["allocation"]["corpse_graphic_id"]:raise RuntimeError("installed FAST corpse mapping mismatch")
  graphic=workspace.graphic_manager.get(receipt["allocation"]["corpse_graphic_id"]);expected=receipt["corpse_graphic"]
  if (graphic.frame_count,graphic.angle_count)!=(expected["frame_count"],expected["angle_count"]) or abs(graphic.frame_duration-expected["frame_duration"])>1e-7:raise RuntimeError("installed FAST corpse graphic timing mismatch")
  hashes={}
  for asset in receipt["assets"]:
   path=mod/"resources/_common/drs/graphics"/Path(asset["path"]).name
   if sha256(path)!=asset["sha256"]:raise RuntimeError(f"installed FAST corpse SLD hash mismatch: {path.name}")
   hashes[path.name]=asset["sha256"]
  return {"format":"rome2aoe2.fast-corpse-install-verification","version":3,"mod":str(mod),"scenario":str(scenario_path),"dat_sha256":sha256(dat),"live_unit_id":live.id,"corpse_unit_id":corpse.id,"corpse_graphic_id":corpse.standing_sprite_id1,"corpse_graphic":{"frame_count":graphic.frame_count,"frame_duration":graphic.frame_duration,"angle_count":graphic.angle_count},"sld_hashes":hashes,"scenario_validation":scenario_validation,"validation":"passed"}
 if sha256(dat)!=receipt["output_dat"]["sha256"]:raise RuntimeError("installed DAT hash mismatch")
 workspace=GenieWorkspace.load(dat);unit_id=receipt["allocation"]["unit_id"];unit=workspace.unit_manager.get(unit_id);expected=receipt["unit"]["graphic_references"];actual={"idle":unit.standing_sprite_id1,"walk":unit.walking_graphic_id,"attack":unit.attack_graphic_id,"death":unit.dying_sprite_id}
 if actual!=expected or unit.standing_sprite_id2!=expected["idle"] or unit.dead_unit_id!=receipt["unit"]["corpse_unit_id"]:raise RuntimeError("installed unit mapping mismatch")
 hashes={}
 for asset in receipt["installed_assets"]:
  name=Path(asset["installed"]).name;path=mod/"resources/_common/drs/graphics"/name
  if sha256(path)!=asset["sha256"]:raise RuntimeError(f"installed SLD hash mismatch: {name}")
  hashes[name]=asset["sha256"]
 scenario=AoE2DEScenario.from_file(str(scenario_path));counts={str(player):sum(item.unit_const==unit_id for item in scenario.unit_manager.units[player]) for player in (1,2)}
 if counts!=receipt["scenario"]["player_counts"]:raise RuntimeError(f"installed scenario mismatch: {counts}")
 return {"format":"rome2aoe2.dev-install-verification","version":1,"mod":str(mod),"scenario":str(scenario_path),"dat_sha256":sha256(dat),"unit_id":unit_id,"graphics":actual,"corpse_unit_id":unit.dead_unit_id,"sld_hashes":hashes,"scenario_counts":counts,"validation":"passed"}
def main():
 parser=argparse.ArgumentParser();parser.add_argument("--receipt",type=Path,required=True);parser.add_argument("--mod",type=Path,required=True);parser.add_argument("--scenario",type=Path,required=True);parser.add_argument("--report",type=Path,required=True);parser.add_argument("--status",type=Path);parser.add_argument("--mods-root",type=Path);parser.add_argument("--target-status-path");args=parser.parse_args();result=verify(args.receipt,args.mod,args.scenario,args.status,args.mods_root,args.target_status_path);args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
