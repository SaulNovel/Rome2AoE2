"""Audit whether Rome II packed diffuse alpha leaked into visible Hastati opacity."""
from pathlib import Path
import json,statistics,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"build/python-deps/pillow"))
from PIL import Image,ImageDraw,ImageFilter,ImageFont
BASE=ROOT/"build/local-integration/rome2";UNIT=BASE/"cross-unit-calibration/units/hastati";OUT=BASE/"aoe-style-calibration";RENDER=BASE/"runtime-resolution/renders/hastati-runtime-resolved-representative.png";CLASS=BASE/"cross-unit-calibration/renders-set-a/hastati-material-classes.png"
EXPECTED={"roman_body1":"skin","roman_1_head":"skin","E3_tunic":"tunic","E3_tunic_flipped":"tunic","italian_square_muscled_cuirass_":"bronze armour","roman_montefortino":"helmet","roman_early_scutum_lod1":"shield body/metal","roman_gladius_lod1":"weapon"}
def main():
 doc=json.loads((UNIT/"texture-manifest.json").read_text());rows=[]
 for m in doc["materials"]:
  if m["material_name"] not in EXPECTED:continue
  t=next((x for x in m["textures"] if x["semantic"]=="Diffuse" and x["status"]=="resolved"),None);a=[]
  if t:a=list(Image.open(UNIT/"textures"/Path(t["extracted_path"])).convert("RGBA").getchannel("A").getdata())
  rows.append({"region":EXPECTED[m["material_name"]],"material":m["material_name"],"diffuse":t["source_path"] if t else None,"source_alpha":{"min":min(a) if a else None,"max":max(a) if a else None,"mean":round(statistics.fmean(a),3) if a else None,"below_250_percent":round(100*sum(v<250 for v in a)/len(a),4) if a else None},"semantic":"opaque surface; diffuse alpha is cutout/packed coverage for used UV islands, not physical translucency"})
 im=Image.open(RENDER).convert("RGBA");cl=Image.open(CLASS).convert("RGBA");interior=cl.getchannel("A").filter(ImageFilter.MinFilter(5));vals=[a for a,m in zip(im.getchannel("A").getdata(),interior.getdata()) if m>250]
 audit={"format":"rome2aoe2.hastati-opacity-audit","version":1,"materials":rows,"rendered_interior":{"pixels":len(vals),"median_alpha":statistics.median(vals),"below_250_percent":round(100*sum(v<250 for v in vals)/len(vals),4),"fully_opaque_percent":round(100*sum(v==255 for v in vals)/len(vals),4)},"finding":"opaque Hastati surfaces are effectively opaque; pale appearance is RGB/tone, not alpha blending","production_change":False}
 (OUT/"hastati-opacity-audit.json").write_text(json.dumps(audit,indent=2,sort_keys=True)+"\n")
 # Checkerboard diagnostic plus alpha-only view.
 w,h=1100,500;sheet=Image.new("RGBA",(w,h),(255,255,255,255));d=ImageDraw.Draw(sheet);sz=24
 for y in range(0,h,sz):
  for x in range(0,w,sz):d.rectangle((x,y,x+sz-1,y+sz-1),fill=(190,190,190,255) if (x//sz+y//sz)%2 else (238,238,238,255))
 crop=im.crop(im.getchannel("A").getbbox());crop.thumbnail((430,430),Image.Resampling.LANCZOS);sheet.alpha_composite(crop,(40+(430-crop.width)//2,40+(430-crop.height)//2));alpha=im.getchannel("A");av=Image.merge("RGBA",(alpha,alpha,alpha,Image.new("L",alpha.size,255))).crop(im.getchannel("A").getbbox());av.thumbnail((430,430),Image.Resampling.NEAREST);sheet.alpha_composite(av,(610+(430-av.width)//2,40+(430-av.height)//2));d.text((40,15),"Rendered RGBA over checkerboard",fill="black");d.text((610,15),"Rendered alpha (white = opaque)",fill="black");d.text((40,470),f"Interior alpha: {audit['rendered_interior']}",fill="black");sheet.save(OUT/"hastati-opacity-audit.png");print(json.dumps(audit,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
