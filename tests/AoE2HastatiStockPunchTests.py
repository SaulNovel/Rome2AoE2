from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import parse_sld,serialize_sld,LAYER_PLAYERCOLOR
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/hastati-stock-punch";MOD=BASE/"ROME2AOE2_HASTATI_STOCK_PUNCH";G=MOD/"resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-stock-punch-report.json").read_text());assert p["fixed"]["scale"]=="R133" and p["fixed"]["composition"]=="unchanged" and not p["fixed"]["normal_body_quantization"]
 assert len(p["definitions"]["lighting_only"])==10 and len(p["definitions"]["material_only"])==8 and len(p["measurements"])==38
 assert all(p["measurements"][x]["metrics"]["bbox_height"]==105 for x in p["measurements"])
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat");assert len(p["units"])==8
 for c in p["units"]:
  gr=ws.graphic_manager.get(c["graphic_id"]);assert (gr.angle_count,gr.frame_count)==(16,1)
  for z,canvas,hot in (("x1",200,100),("x2",400,200)):
   raw=(G/f"{c['stem']}_{z}.sld").read_bytes();doc=parse_sld(raw);assert raw==serialize_sld(doc) and len(doc.frames)==16 and all((f.canvas_width,f.canvas_height,f.center_x,f.center_y)==(canvas,canvas,hot,hot) for f in doc.frames);assert not any(f.frame_type&LAYER_PLAYERCOLOR for f in doc.frames)
 for n in ("lighting-only-sheet.png","material-only-sheet.png","combined-finalists-sheet.png","combined-finalists-4x.png","Rome2HastatiStockPunch.aoe2scenario"):assert (BASE/n).is_file()
 print("HASTATI STOCK PUNCH PASS")
if __name__=="__main__":main()
