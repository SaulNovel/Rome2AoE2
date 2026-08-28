"""Strict structural checks for the bounded composition calibration proof."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party"/"python-deps")];V=ROOT/"build"/"python-deps"/"sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from aoe2.sld import parse_sld,serialize_sld
from aoe2.analyze_sld import decode_frame
from aoe2_genie_tooling import GenieWorkspace
B=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration";REPORT=B/"composition-proof.json";MOD=B/"ROME2AOE2_COMPOSITION_CALIBRATION";G=MOD/"resources"/"_common"/"drs"/"graphics"
def near(im,x,y):
 pts=[(i%im.width,i//im.width) for i,p in enumerate(im.convert("RGBA").getdata()) if p[3]>8]
 return min((a-x)**2+(b-y)**2 for a,b in pts)
def main():
 rows=json.loads(REPORT.read_text())["candidates"];assert [r["id"] for r in rows]==["H01","H02","H03","E01","E02","E03","E04","E05","P01","P02","P03"]
 for key in ("id","unit_id","graphic_id","stem","display_name"):assert len({r[key] for r in rows})==len(rows)
 ws=GenieWorkspace.load(B/"composition_calibration.dat")
 for r in rows:
  u=ws.unit_manager.get(r["unit_id"]);g=ws.graphic_manager.get(r["graphic_id"]);assert u.name==r["display_name"] and u.standing_sprite_id1==u.standing_sprite_id2==g.id;assert g.file_name==r["stem"] and g.angle_count==16 and g.frame_count==1
  for suffix,canvas,hotspot,scale in (("x1",200,(100,100),1),("x2",400,(200,200),2)):
   raw=(G/f"{r['stem']}_{suffix}.sld").read_bytes();s=parse_sld(raw);assert serialize_sld(s)==raw
   assert len(s.frames)==16 and [f.frame_index for f in s.frames]==list(range(16))
   assert all((f.canvas_width,f.canvas_height)==(canvas,canvas) and (f.center_x,f.center_y)==hotspot for f in s.frames)
   rgb,shadow=decode_frame(s,0);assert near(rgb,*hotspot)<=(4*scale)**2 and near(shadow,*hotspot)<=(4*scale)**2
 assert len(list(G.glob("*.sld")))==22
 assert (MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat").is_file() and not (MOD/"mod").exists()
 assert (B/"Rome2CompositionCalibration.aoe2scenario").is_file() and (B/"LEGEND.txt").is_file()
 print("COMPOSITION CALIBRATION PROOF PASS")
if __name__=="__main__":main()
