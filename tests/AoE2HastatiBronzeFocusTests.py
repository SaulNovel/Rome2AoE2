from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import parse_sld,serialize_sld,LAYER_PLAYERCOLOR
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/hastati-bronze-focus";MOD=BASE/"ROME2AOE2_HASTATI_BRONZE_FOCUS";G=MOD/"resources/_common/drs/graphics";MILE=ROOT/"build/local-integration/rome2/milestones/hastati-bronze-punch-baseline"
def main():
 p=json.loads((BASE/"hastati-bronze-focus-report.json").read_text());assert p["baseline"]["immutable"] and p["recommendation"]["candidate"]=="E4" and len(p["measurements"])==21 and len(p["finals"])==5
 required={"luminance_p50","luminance_p75","luminance_p90","luminance_p95","chroma_mean","saturation_median","lit_warm_hue_degrees","local_contrast","edge_contrast","highlight_coverage","clipped_highlight_coverage"}
 assert all(required<=set(x["bronze"]) and x["whole_body"]["bbox_height"]==105 for x in p["measurements"].values())
 manifest=json.loads((MILE/"SHA256.json").read_text(encoding="utf-8-sig"));assert manifest
 for x in manifest:assert hashlib.sha256((MILE/x["path"]).read_bytes()).hexdigest().upper()==x["sha256"]
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in p["finals"]:
  assert required<=set(c["bronze"]);gr=ws.graphic_manager.get(c["graphic_id"]);assert (gr.angle_count,gr.frame_count)==(16,1)
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();doc=parse_sld(raw);assert raw==serialize_sld(doc) and len(doc.frames)==16 and all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in doc.frames) and not any(f.frame_type&LAYER_PLAYERCOLOR for f in doc.frames)
 for n in ("bronze-focused-contact-sheet.png","bronze-closeups-4x.png","in-game-proof-sheet.png","Rome2HastatiBronzeFocus.aoe2scenario"):assert (BASE/n).is_file()
 print("HASTATI BRONZE FOCUS PASS")
if __name__=="__main__":main()
