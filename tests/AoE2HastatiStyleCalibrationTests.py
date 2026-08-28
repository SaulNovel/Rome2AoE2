from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from aoe2.sld import parse_sld,serialize_sld
from aoe2.analyze_sld import decode_frame
from aoe2_genie_tooling import GenieWorkspace
BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration";MOD=BASE/"ROME2AOE2_AOE_STYLE_HASTATI";G=MOD/"resources/_common/drs/graphics"
def feet(doc,i):
 im,_=decode_frame(doc,i);b=im.getchannel("A").getbbox();return (doc.frames[i].center_x,(b[3] if b else 0)-doc.frames[i].center_y)
def main():
 r=json.loads((BASE/"hastati-style-proof.json").read_text());cs=r["candidates"]
 assert 24<=len(cs)<=30 and len({c["id"] for c in cs})==len(cs)
 assert len({c["unit_id"] for c in cs})==len(cs) and len({c["graphic_id"] for c in cs})==len(cs) and len({c["stem"] for c in cs})==len(cs)
 assert (MOD/"resources/_common/dat/empires2_x2_p1.dat").is_file() and not (MOD/"mod").exists()
 ws=GenieWorkspace.load(MOD/"resources/_common/dat/empires2_x2_p1.dat")
 for c in cs:
  u=ws.unit_manager.get(c["unit_id"]);g=ws.graphic_manager.get(c["graphic_id"])
  assert u.name==c["display_name"] and u.standing_sprite_id1==g.id and g.file_name==c["stem"] and g.angle_count==16 and g.frame_count==1
  docs=[]
  for z in ("x1","x2"):
   p=G/f"{c['stem']}_{z}.sld";raw=p.read_bytes();d=parse_sld(raw);docs.append(d)
   assert len(d.frames)==16 and [f.frame_index for f in d.frames]==list(range(16)) and raw==serialize_sld(d)
   assert all((f.canvas_width,f.canvas_height)==((200,200) if z=="x1" else (400,400)) for f in d.frames)
   assert all((f.center_x,f.center_y)==((100,100) if z=="x1" else (200,200)) for f in d.frames)
  f1=feet(docs[0],0);f2=feet(docs[1],0);assert abs(f1[1]-f2[1]/2)<=1.5
 assert (BASE/"aoe-reference-analysis.json").is_file() and (BASE/"hastati-artistic-sweep-highres.png").is_file() and (BASE/"hastati-artistic-sweep-gameplay.png").is_file()
 assert "build/" in (ROOT/".gitignore").read_text()
 # This milestone's proprietary reference decodes and generated SLDs must be
 # ignored.  The repository already contains unrelated user-supplied graphic
 # fixtures, so audit the assets produced here instead of pretending it does not.
 produced=list((BASE/"decoded-stock").glob("*.png"))+list(G.glob("*.sld"))
 for p in produced:
  rel=p.relative_to(ROOT);assert subprocess.run(["git","ls-files","--error-unmatch",str(rel)],cwd=ROOT,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode!=0
 print("HASTATI STYLE CALIBRATION PASS")
if __name__=="__main__":main()
