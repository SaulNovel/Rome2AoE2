"""Quantify Rome II Mask RGB channels and compose the geometry coverage audit."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"build"/"python-deps"/"pillow"))
from PIL import Image,ImageDraw,ImageFont
BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";TM=BASE/"tint-masks";UNITS=[("hastati","Hastati"),("principes","Principes"),("triarii","Triarii"),("velites","Velites"),("hoplites","Hoplites"),("celtic-warriors","Celtic Warriors"),("eastern-spearmen","Eastern Spearmen"),("praetorian","Praetorian")]
def channel_stats(im):
 p=list(im.convert("RGB").getdata());n=len(p);return {c:{"mean":round(sum(x[i] for x in p)/n,2),"coverage_gt_32_percent":round(100*sum(x[i]>32 for x in p)/n,3)} for i,c in enumerate("RGB")}
def main():
 rows=[]
 for slug,name in UNITS:
  if slug=="praetorian":continue
  root=BASE/"units"/slug;doc=json.loads((root/"texture-manifest.json").read_text())
  for m in doc["materials"]:
   for t in m["textures"]:
    if t["semantic"]!="Mask" or t["status"]!="resolved":continue
    path=root/"textures"/Path(t["extracted_path"]);im=Image.open(path)
    rows.append({"unit":name,"material":m["material_name"],"material_type":m["material_type"],"source_models":m["source_models"],"source_texture":t["source_path"],"resolved_path":str(path),"dimensions":list(im.size),"format":im.format,"channels":channel_stats(im),"semantic_evidence":"RMV2 TextureType.Mask; Asset Editor feeds MaskTexture RGB to ApplyTintAndFactionColours","prototype_policy":"eligible only after excluding skin, hair, leather and conductor-class materials"})
 cover=[]
 for slug,name in UNITS:
  im=Image.open(TM/f"{slug}-mask-rgb.png").convert("RGBA");pix=[p for p in im.getdata() if p[3]>8];cover.append({"unit":name,"visible_mask_coverage_percent":round(100*sum(max(p[:3])>24 for p in pix)/len(pix),2),"channel_mean_rgb":[round(sum(p[i] for p in pix)/len(pix),2) for i in range(3)]})
 # Contact sheet, tightly cropping alpha-bearing geometry.
 cell=(320,300);out=Image.new("RGB",(4*cell[0],2*cell[1]+28),(24,26,29));d=ImageDraw.Draw(out);d.text((8,8),"Rome II RGB Mask coverage (R/G/B shown literally)",fill="white",font=ImageFont.load_default())
 for i,(slug,name) in enumerate(UNITS):
  im=Image.open(TM/f"{slug}-mask-rgb.png").convert("RGBA");box=im.getchannel("A").getbbox();crop=im.crop(box);crop.thumbnail((220,230),Image.Resampling.LANCZOS);x=(i%4)*cell[0]+(cell[0]-crop.width)//2;y=28+(i//4)*cell[1]+25;out.paste(crop,(x,y),crop);d.text(((i%4)*cell[0]+8,28+(i//4)*cell[1]+8),name,fill="white")
 out.save(BASE/"rome2-tint-mask-audit.png");(BASE/"rome2-tint-mask-audit.json").write_text(json.dumps({"format":"rome2aoe2.tint-mask-audit","version":1,"materials":rows,"visible_coverage":cover,"limitations":["RGB channels represent three Rome II faction-colour inputs; AoE2 prototype uses their union as one runtime player-colour mask.","SkinMask and sentinel test_mask/test_black are excluded.","Metal/conductor materials are excluded from the player-colour prototype even when a generic Mask texture exists."]},indent=2,sort_keys=True)+"\n");print(json.dumps(cover,indent=2))
if __name__=="__main__":main()
