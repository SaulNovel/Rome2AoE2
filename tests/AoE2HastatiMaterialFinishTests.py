from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import LAYER_PLAYERCOLOR,parse_sld,serialize_sld
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/material-aware-finishing";MOD=BASE/"ROME2AOE2_HASTATI_MATERIAL_FINISH";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-material-finish-report.json").read_text());cs=p["candidates"];assert len(cs)==14 and len({c["id"] for c in cs})==14 and len({c["unit_id"] for c in cs})==14 and len({c["graphic_id"] for c in cs})==14
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in cs:
  gr=ws.graphic_manager.get(c["graphic_id"]);u=ws.unit_manager.get(c["unit_id"]);assert (gr.angle_count,gr.frame_count,gr.file_name)==(16,1,c["stem"]) and u.standing_sprite_id1==gr.id
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();s=parse_sld(raw);assert serialize_sld(s)==raw and len(s.frames)==16 and [f.frame_index for f in s.frames]==list(range(16));assert all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in s.frames);assert any(f.frame_type&LAYER_PLAYERCOLOR for f in s.frames)==(c["id"]=="BESTPC")
 assert next(c for c in cs if c["id"]=="BESTPC")["metrics_x2"]["player_colour_coverage"]<.25
 assert {x["master"] for x in p["resampling"]["measurements"]}=={800,1600,3200} and {x["filter"] for x in p["resampling"]["measurements"]}=={"bicubic","lanczos","hamming"}
 inputs=json.loads((BASE/"inputs/hastati-finish-inputs.json").read_text());assert inputs["anti_aliasing"].startswith("single emission") and inputs["unsupported_exact_masks"]["shield metal"]
 for n in ("hastati-material-masks.png","hastati-colour-definition-uhd.png","hastati-colour-definition-4x.png","LEGEND.txt","Rome2HastatiMaterialFinish.aoe2scenario"):assert (BASE/n).is_file()
 assert (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file() and not (MOD/"mod").exists();print("HASTATI MATERIAL FINISH PASS")
if __name__=="__main__":main()
