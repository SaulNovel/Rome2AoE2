from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import LAYER_PLAYERCOLOR,parse_sld,serialize_sld
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration-v3";MOD=BASE/"ROME2AOE2_AOE_STYLE_HASTATI_V3";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-v3-report.json").read_text());cs=p["candidates"];assert len(cs)==14 and {c["id"] for c in cs}=={f"A{i}" for i in range(1,5)}|{f"B{i}" for i in range(1,7)}|{f"C{i}" for i in range(1,5)}
 assert len({c["unit_id"] for c in cs})==14 and len({c["graphic_id"] for c in cs})==14 and len({c["stem"] for c in cs})==14
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in cs:
  gr=ws.graphic_manager.get(c["graphic_id"]);unit=ws.unit_manager.get(c["unit_id"]);assert gr.angle_count==16 and gr.frame_count==1 and gr.file_name==c["stem"] and unit.standing_sprite_id1==gr.id
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();s=parse_sld(raw);assert serialize_sld(s)==raw and len(s.frames)==16 and [f.frame_index for f in s.frames]==list(range(16));assert all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in s.frames)
   assert any(bool(f.frame_type&LAYER_PLAYERCOLOR) for f in s.frames)==c["id"].startswith("C")
 assert all(c["metrics_x2"]["shadow_area_relative_to_body"]<.62 and c["metrics_x2"]["shadow_opacity_mean"]<50 for c in cs)
 cov=[next(c for c in cs if c["id"]==f"C{i}")["metrics_x2"]["player_colour_coverage"] for i in range(1,5)];assert cov==sorted(cov) and cov[-1]<.45
 assert all(c["red_cloth_x2"]["black_percent"]<15 for c in cs if c["id"]!="A4")
 for n in ("hastati-v3-neutral-uhd.png","hastati-v3-playercolor-uhd.png","hastati-v3-4x-pixels.png","hastati-v3-report.json","LEGEND.txt","Rome2AoEStyleCalibrationHastatiV3.aoe2scenario"):assert (BASE/n).is_file()
 assert not (MOD/"mod").exists();print("HASTATI V3 PASS")
if __name__=="__main__":main()
