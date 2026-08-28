from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import LAYER_PLAYERCOLOR,parse_sld,serialize_sld
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration-v2";MOD=BASE/"ROME2AOE2_AOE_STYLE_HASTATI_V2";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-v2-report.json").read_text());cs=p["candidates"];assert len(cs)==41 and len({x["id"] for x in cs})==41 and len({x["unit_id"] for x in cs})==41 and len({x["graphic_id"] for x in cs})==41
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in cs:
  g=ws.graphic_manager.get(c["graphic_id"]);u=ws.unit_manager.get(c["unit_id"]);assert g.angle_count==16 and g.frame_count==1 and g.file_name==c["stem"] and u.standing_sprite_id1==g.id
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();d=parse_sld(raw);assert raw==serialize_sld(d) and len(d.frames)==16 and [f.frame_index for f in d.frames]==list(range(16));assert all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in d.frames)
   has_pc=any(f.frame_type&LAYER_PLAYERCOLOR for f in d.frames);assert has_pc==(c["player_support_target"] is not None)
 for cid,lo,hi in (("PC01",.20,.28),("PC02",.25,.36),("PC03",.35,.46),("PC04",.45,.56)):
  c=next(x for x in cs if x["id"]==cid);assert lo<=c["metrics_x2"]["player_colour_coverage"]<=hi and c["player_shade_metrics"]["distinct_indices"]>=8
 for cid,ratio,opacity in (("SH01",.65,48),("SH02",.55,45),("SH03",.47,42)):
  m=next(x for x in cs if x["id"]==cid)["metrics_x2"];assert abs(m["shadow_area_relative_to_body"]-ratio)<.05 and abs(m["shadow_opacity_mean"]-opacity)<2
 assert all(next(x for x in cs if x["id"]==cid)["metrics_x2"]["player_colour_coverage"]==0 for cid in ("NF01","NF02","NF03","NF04","NF05","NF06"))
 op=json.loads((ROOT/"build/local-integration/rome2/aoe-style-calibration/hastati-opacity-audit.json").read_text());assert op["rendered_interior"]["fully_opaque_percent"]>99.5 and op["production_change"] is False
 for name in ("hastati-v2-neutral-uhd.png","hastati-v2-playercolor-uhd.png","hastati-v2-4x-pixels.png","player-color-detail-comparison-4x.png","LEGEND.txt","Rome2AoEStyleCalibrationHastatiV2.aoe2scenario"):assert (BASE/name).is_file()
 assert not (MOD/"mod").exists() and (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file();print("HASTATI V2 PASS")
if __name__=="__main__":main()
