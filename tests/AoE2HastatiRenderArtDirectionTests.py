from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import parse_sld,serialize_sld,LAYER_PLAYERCOLOR
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/aoe-render-art-direction";MOD=BASE/"ROME2AOE2_HASTATI_RENDER_ART_DIRECTION";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-render-art-direction-report.json").read_text());guide=json.loads((BASE/"aoe-stock-color-guide.json").read_text());assert guide["not_a_palette"] and not guide["normal_body_quantization"]
 assert p["fixed_scale"].startswith("R133") and set(p["studies"])==set([f"CM{i}" for i in range(1,5)]+[f"LR{i}" for i in range(7)]+[f"BR{i}" for i in range(5)]+[f"CL{i}" for i in range(4)]+[f"F{i}" for i in range(8)])
 assert all(x["decoded_body_dimensions"][1]==105 for x in p["studies"].values())
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in p["finals"]:
  gr=ws.graphic_manager.get(c["graphic_id"]);assert (gr.angle_count,gr.frame_count)==(16,1)
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   path=G/f"{c['stem']}_{z}.sld";raw=path.read_bytes();doc=parse_sld(raw);assert raw==serialize_sld(doc) and len(doc.frames)==16 and all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in doc.frames)
   pc=any(f.frame_type&LAYER_PLAYERCOLOR for f in doc.frames);assert pc==(c["id"]=="F5PC")
 assert (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file()
 for n in ("aoe-render-art-direction-highres.png","aoe-render-art-direction-x2.png","aoe-render-art-direction-4x.png","Rome2HastatiRenderArtDirection.aoe2scenario"):assert (BASE/n).is_file()
 print("HASTATI RENDER ART DIRECTION PASS")
if __name__=="__main__":main()
