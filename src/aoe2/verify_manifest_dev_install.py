"""Verify an installed generic AoE2 visual-test mod against its receipt."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")];sys.stdout.reconfigure(encoding="utf-8",errors="replace")
from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
from aoe2.dat_integration import sha256
def verify(receipt_path,mod,scenario_path):
 receipt=json.loads(receipt_path.read_text());dat=mod/"resources/_common/dat/empires2_x2_p1.dat"
 if receipt.get("format")=="rome2aoe2.fast-corpse-dev-integration":
  if receipt.get("release_eligible") is not False:raise RuntimeError("FAST corpse receipt unexpectedly release eligible")
  if sha256(dat)!=receipt["dat"]["sha256"] or sha256(scenario_path)!=receipt["scenario_sha256"]:raise RuntimeError("installed FAST corpse DAT/scenario hash mismatch")
  workspace=GenieWorkspace.load(dat);live=workspace.unit_manager.get(receipt["allocation"]["unit_id"]);corpse=workspace.unit_manager.get(receipt["allocation"]["corpse_unit_id"])
  if live.dead_unit_id!=corpse.id or live.dead_unit_id==receipt["profile"]["corpse_template_unit_id"] or corpse.standing_sprite_id1!=receipt["allocation"]["corpse_graphic_id"]:raise RuntimeError("installed FAST corpse mapping mismatch")
  hashes={}
  for asset in receipt["assets"]:
   path=mod/"resources/_common/drs/graphics"/Path(asset["path"]).name
   if sha256(path)!=asset["sha256"]:raise RuntimeError(f"installed FAST corpse SLD hash mismatch: {path.name}")
   hashes[path.name]=asset["sha256"]
  return {"format":"rome2aoe2.fast-corpse-install-verification","version":1,"mod":str(mod),"scenario":str(scenario_path),"dat_sha256":sha256(dat),"live_unit_id":live.id,"corpse_unit_id":corpse.id,"corpse_graphic_id":corpse.standing_sprite_id1,"sld_hashes":hashes,"validation":"passed"}
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
 parser=argparse.ArgumentParser();parser.add_argument("--receipt",type=Path,required=True);parser.add_argument("--mod",type=Path,required=True);parser.add_argument("--scenario",type=Path,required=True);parser.add_argument("--report",type=Path,required=True);args=parser.parse_args();result=verify(args.receipt,args.mod,args.scenario);args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");print(json.dumps(result,indent=2,sort_keys=True))
if __name__=="__main__":main()
