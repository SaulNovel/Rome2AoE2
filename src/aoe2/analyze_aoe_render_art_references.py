"""Bounded final-x2 stock material/color guide (full-color, not a palette)."""
from __future__ import annotations
import colorsys,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src"),str(ROOT/"third_party/python-deps")]
from PIL import Image,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.analyze_aoe_style_uhd import decode,GRAPHICS,FACET
OUT=ROOT/"build/local-integration/rome2/aoe-render-art-direction/stock";DAT=ROOT/"test_data/empires2_x2_p1.dat"
UNITS=((1793,"Legionary"),(75,"Man-at-Arms"),(76,"Broad Swordsman reference (DAT HVSWD / Heavy Swordsman)"),(567,"Champion"),(93,"Spearman"))
def stats(im,pc):
 a=im.getchannel("A");pixels=[]
 for rgb,aa,p in zip(im.convert("RGB").getdata(),a.getdata(),pc.getdata()):
  if aa>8 and not p:
   h,s,v=colorsys.rgb_to_hsv(*(x/255 for x in rgb));lum=.2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2];pixels.append((rgb,h*360,s,lum))
 lum=sorted(x[3] for x in pixels);q=lambda p:round(lum[int((len(lum)-1)*p)],3)
 gray=im.convert("L");blur=gray.filter(ImageFilter.GaussianBlur(2.4));local=[abs(x-y) for x,y,aa in zip(gray.getdata(),blur.getdata(),a.getdata()) if aa>8]
 edge=gray.filter(ImageFilter.FIND_EDGES);edges=[x for x,aa in zip(edge.getdata(),a.getdata()) if aa>8]
 def region(name,pred):
  z=[x for x in pixels if pred(x)];ls=sorted(x[3] for x in z);hs=[x[1] for x in z];ss=[x[2] for x in z]
  if not z:return {"pixels":0}
  return {"pixels":len(z),"coverage":round(len(z)/len(pixels),5),"luminance_p10":round(ls[int(.1*(len(ls)-1))],3),"luminance_p25":round(ls[int(.25*(len(ls)-1))],3),"luminance_p50":round(statistics.median(ls),3),"luminance_p75":round(ls[int(.75*(len(ls)-1))],3),"luminance_p90":round(ls[int(.9*(len(ls)-1))],3),"luminance_p95":round(ls[int(.95*(len(ls)-1))],3),"luminance_max":round(max(ls),3),"saturation_median":round(statistics.median(ss),5),"representative_hue_degrees":round(statistics.median(hs),3),"near_white_coverage":round(sum(x[3]>=245 for x in z)/len(z),5),"deep_dark_coverage":round(sum(x[3]<=35 for x in z)/len(z),5)}
 return {"body":{"pixels":len(pixels),**{f"luminance_p{int(p*100):02d}":q(p) for p in (.1,.25,.5,.75,.9)},"saturation_median":round(statistics.median(x[2] for x in pixels),5),"near_white_coverage":round(sum(x[3]>=245 for x in pixels)/len(pixels),5),"deep_dark_coverage":round(sum(x[3]<=35 for x in pixels)/len(pixels),5),"highlight_coverage_p90":round(sum(x[3]>=q(.9) for x in pixels)/len(pixels),5),"local_contrast":round(statistics.mean(local),3),"edge_contrast":round(statistics.mean(edges),3)},"regions":{"bronze_like":region("bronze",lambda x:18<=x[1]<=72 and x[2]>=.22),"steel_like":region("steel",lambda x:x[2]<=.16 and x[3]>=65),"saturated_cloth_like":region("cloth",lambda x:x[2]>=.38 and x[3]>=25),"skin_like":region("skin",lambda x:5<=x[1]<=38 and .18<=x[2]<=.75 and x[3]>=55),"dark_cavity":region("dark",lambda x:x[3]<=35)}}
def main():
 OUT.mkdir(parents=True,exist_ok=True);ws=GenieWorkspace.load(DAT);refs=[]
 for uid,label in UNITS:
  u=ws.unit_manager.get(uid);g=ws.graphic_manager.get(u.standing_sprite_id1);stem=g.file_name[:-3] if g.file_name.endswith("_x1") else g.file_name;p=GRAPHICS/f"{stem}_x2.sld"
  if not p.is_file():raise FileNotFoundError(f"required stock x2 missing; fallback forbidden: {p}")
  o=decode(p,FACET*g.frame_count);png=OUT/f"unit-{uid}-{stem}-x2.png";o["main"].save(png)
  refs.append({"label":label,"unit_id":uid,"dat_internal_name":u.name,"graphic_id":int(g.id),"dat_graphic_file_name":g.file_name,"graphic_stem":stem,"frames_per_facet":g.frame_count,"facet":FACET,"source_x2_sld":str(p),"decoded_png":str(png),"measurements":stats(o["main"],o["pc_presence"])})
 guide={"format":"rome2aoe2.aoe-stock-color-guide","version":1,"not_a_palette":True,"normal_body_quantization":False,"region_method":"HSV/luminance heuristic on final decoded x2 RGB, excluding player-color support; regions overlap and do not claim exact materials","broad_swordsman_resolution":"No exact 'Broad Swordsman' localization exists in the installed AoE2 DE strings/DAT. Unit 76 HVSWD / u_inf_heavy_swordsman_idleA is the local DAT heavy-sword bronze visual reference requested.","references":refs}
 (OUT.parent/"aoe-stock-color-guide.json").write_text(json.dumps(guide,indent=2,sort_keys=True)+"\n");print(json.dumps({x["label"]:x["graphic_stem"] for x in refs},indent=2))
if __name__=="__main__":main()
