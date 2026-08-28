from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import LAYER_PLAYERCOLOR,parse_sld,serialize_sld
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/hastati-gameplay-finish";MOD=BASE/"ROME2AOE2_HASTATI_GAMEPLAY_FINISH";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-gameplay-finish-report.json").read_text());cs=p["candidates"]
 assert len(cs)==29 and len({c["id"] for c in cs})==len({c["unit_id"] for c in cs})==len({c["graphic_id"] for c in cs})==len({c["stem"] for c in cs})==29
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in cs:
  gr=ws.graphic_manager.get(c["graphic_id"]);u=ws.unit_manager.get(c["unit_id"]);assert (gr.angle_count,gr.frame_count,gr.file_name)==(16,1,c["stem"]) and u.standing_sprite_id1==gr.id
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();doc=parse_sld(raw);assert raw==serialize_sld(doc) and len(doc.frames)==16 and [f.frame_index for f in doc.frames]==list(range(16));assert all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in doc.frames)
   expected=c["id"] in ("PC1","PC2","PC3");assert any(f.frame_type&LAYER_PLAYERCOLOR for f in doc.frames)==expected
 by={c["id"]:c for c in cs};assert [by[x]["logical_height"] for x in ("S00","S05","S08","S10","S12")]==[44,46,47,48,49]
 assert by["PC1"]["metrics_x2"]["player_colour_coverage"]<by["PC2"]["metrics_x2"]["player_colour_coverage"]<by["PC3"]["metrics_x2"]["player_colour_coverage"]<.35
 assert by["T4"]["tunic"]=="reduction" and by["T5"]["tunic"]=="tunicbest" and p["fixed"]["semantic_masks"].startswith("body-transform aligned")
 assert (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file() and not (MOD/"mod").exists()
 for n in ("hastati-gameplay-neutral-uhd.png","hastati-gameplay-scale-uhd.png","hastati-gameplay-playercolor-uhd.png","hastati-gameplay-4x.png","hastati-gameplay-ingame-sheet.png","LEGEND.txt","Rome2HastatiGameplayFinish.aoe2scenario"):assert (BASE/n).is_file()
 print("HASTATI GAMEPLAY FINISH PASS")
if __name__=="__main__":main()
