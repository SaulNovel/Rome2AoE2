from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import parse_sld
from aoe2_genie_tooling import GenieWorkspace
from aoe2.generate_hastati_scale_reference_proof import strict
BASE=ROOT/"build/local-integration/rome2/hastati-scale-reference";MOD=BASE/"ROME2AOE2_HASTATI_SCALE_REFERENCE";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-scale-reference-report.json").read_text());ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 assert p["targets_x2_body_height"]=={"R100":79,"R115":91,"R125":99,"R133":105,"R140":111}
 try:strict(Path(p["stock"]["legionary"]["x1"]["path"]),0);raise AssertionError("strict x2 loader accepted x1")
 except ValueError:pass
 assert p["logical_rule"]=="all actual x2 sources resized uniformly by 0.5"
 for x in p["native_x2_composition"]:
  assert x["source_sld"].endswith("_x2.sld") and x["resize_factor"]==1 and x["decoded_body_dimensions"]==x["final_pasted_body_dimensions"]
 for x in p["logical_game_composition"]:assert x["source_sld"].endswith("_x2.sld") and x["resize_factor"]==.5
 assert len({x["resize_factor"] for x in p["logical_game_composition"]})==1
 for c in p["candidates"]:
  gr=ws.graphic_manager.get(c["graphic_id"]);assert (gr.angle_count,gr.frame_count)==(16,1)
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   path=G/f"{c['stem']}_{z}.sld";assert path.is_file();doc=parse_sld(path.read_bytes());assert len(doc.frames)==16 and all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in doc.frames)
  assert c["x2"]["hotspot"]==[2*x for x in c["x1"]["hotspot"]]
  assert c["x2"]["body_dimensions"][1]==c["target_x2_body_height"]
  assert c["uniform_scaling"] and c["source_aspect_ratio_preserved"] and c["x1"]["uniform_source_scale_xy"]>0 and c["x2"]["uniform_source_scale_xy"]>0
  m=c["perceived_scale_diagnostics_x2"];assert m["full_opaque_bbox_height"]==c["target_x2_body_height"] and 0<m["feet_to_core_head_helmet_height"]<=m["full_opaque_bbox_height"] and m["feet_to_shoulder_height"]<m["feet_to_core_head_helmet_height"] and m["torso_shoulder_central_run_width"]>0 and m["total_silhouette_width"]==c["x2"]["body_dimensions"][0]
 lm=p["stock"]["legionary"]["perceived_scale_diagnostics_x2"];assert lm["full_opaque_bbox_height"]==79 and lm["feet_to_core_head_helmet_height"]<=79
 assert (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file()
 marker=BASE/"ROME2AOE2_UHD_SELECTION_MARKER";mws=GenieWorkspace.load(marker/"resources/_common/dat/empires2_x2_p1.dat");mgr=mws.graphic_manager.get(p["uhd_marker_proof"]["graphic_id"]);assert (mgr.angle_count,mgr.frame_count)==(16,1)
 for z,canvas,hot in (("x1",200,100),("x2",400,200)):
  doc=parse_sld((marker/f"resources/_common/drs/graphics/{p['uhd_marker_proof']['stem']}_{z}.sld").read_bytes());assert len(doc.frames)==16 and all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in doc.frames)
 assert (BASE/"scale-reference-NATIVE-X2.png").is_file() and (BASE/"scale-reference-LOGICAL-GAME.png").is_file()
 print("HASTATI STRICT SCALE REFERENCE PASS")
if __name__=="__main__":main()
