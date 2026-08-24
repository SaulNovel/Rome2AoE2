"""Semantic validation for reusable AoE2 development scenarios."""
from __future__ import annotations
import contextlib,hashlib,io,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
def validate_scenario(path:Path,workspace,expected_unit_ids=(),expected_active_players=(1,2)):
 path=Path(path)
 with contextlib.redirect_stdout(io.StringIO()):document=AoE2DEScenario.from_file(str(path))
 players=[];all_ids=set();total=0
 for player_id,objects in enumerate(document.unit_manager.units):
  rows=[{"unit_id":item.unit_const,"x":item.x,"y":item.y,"rotation":getattr(item,"rotation",None)} for item in objects];players.append({"player_id":player_id,"count":len(rows),"objects":rows});total+=len(rows);all_ids.update(row["unit_id"] for row in rows)
 if total<=0:raise RuntimeError("development scenario contains zero placed objects")
 for player_id in expected_active_players:
  if player_id>=len(players) or players[player_id]["count"]<=0:raise RuntimeError(f"expected active player has no objects: {player_id}")
 missing=set(expected_unit_ids)-all_ids
 if missing:raise RuntimeError(f"expected test unit IDs are not placed: {sorted(missing)}")
 unresolved=sorted(unit_id for unit_id in all_ids if not workspace.unit_manager.exists(unit_id))
 if unresolved:raise RuntimeError(f"scenario object IDs are absent from target DAT: {unresolved}")
 return {"path":str(path),"sha256":hashlib.sha256(path.read_bytes()).hexdigest(),"file_size":path.stat().st_size,"game_version":document.game_version,"scenario_version":document.scenario_version,"player_count":len(document.player_manager.players),"map_dimensions":[document.map_manager.map_width,document.map_manager.map_height],"total_objects":total,"placed_unit_ids":sorted(all_ids),"players":players,"trigger_count":len(document.trigger_manager.triggers),"all_object_ids_resolve":True}
