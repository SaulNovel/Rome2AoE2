"""Strict structural checks for the five-unit Set A native proof."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party"/"python-deps")];V=ROOT/"build"/"python-deps"/"sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from aoe2.sld import parse_sld,serialize_sld
from aoe2.analyze_sld import decode_frame
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";REPORT=BASE/"aoe-proof-set-a.json";MOD=BASE/"ROME2AOE2_INFANTRY_CALIBRATION_SET_A";G=MOD/"resources"/"_common"/"drs"/"graphics"
def cs():return json.loads(REPORT.read_text())["candidates"]
def load(c,z):
 d=(G/f"{c['stem']}_{z}.sld").read_bytes();s=parse_sld(d);assert serialize_sld(s)==d;return s
def near(im,x,y):
 pts=[(i%im.width,i//im.width) for i,p in enumerate(im.convert("RGBA").getdata()) if p[3]>8];return min((a-x)**2+(b-y)**2 for a,b in pts)
def main():
 c=cs();assert len(c)==15
 for k in ("unit_id","graphic_id","stem","display_name"):assert len({x[k] for x in c})==15
 ws=GenieWorkspace.load(BASE/"set_a_calibration.dat")
 for x in c:
  u=ws.unit_manager.get(x["unit_id"]);g=ws.graphic_manager.get(x["graphic_id"]);assert u.name==x["display_name"] and u.standing_sprite_id1==u.standing_sprite_id2==g.id;assert g.file_name==x["stem"] and g.angle_count==16 and g.frame_count==1
  for z,canvas,h,scale in (("x1",200,(100,100),1),("x2",400,(200,200),2)):
   s=load(x,z);assert len(s.frames)==16 and [f.frame_index for f in s.frames]==list(range(16));assert all((f.canvas_width,f.canvas_height)==(canvas,canvas) and (f.center_x,f.center_y)==h for f in s.frames)
   a,b=decode_frame(s,0);assert near(a,*h)<=(4*scale)**2 and near(b,*h)<=(4*scale)**2
 assert (MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat").is_file();assert len(list(G.glob("*.sld")))==30;assert not (MOD/"mod").exists();print("SET A AOE PROOF PASS")
if __name__=="__main__":main()
