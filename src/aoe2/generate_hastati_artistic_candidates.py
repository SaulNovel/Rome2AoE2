"""Generate the evidence-bounded Hastati AoE2 presentation sweep."""
from __future__ import annotations
import json, math, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src")]
from PIL import Image,ImageChops,ImageDraw,ImageEnhance,ImageFilter,ImageFont
from aoe2.generate_v4_ingame_proof import downsample_about_feet
from aoe2.analyze_aoe_style_references import rgba_metrics

BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration";HI=BASE/"candidates-highres";GAME=BASE/"candidates-gameplay"
SOURCE=ROOT/"build/local-integration/rome2/runtime-resolution/renders/hastati-runtime-resolved-representative.png"
NEUTRAL=ROOT/"build/local-integration/rome2/material-reconstruction/renders/hastati-faction-neutral.png"
CLASS=ROOT/"build/local-integration/rome2/cross-unit-calibration/renders-set-a/hastati-material-classes.png"
TINT=ROOT/"build/local-integration/rome2/cross-unit-calibration/tint-masks/hastati-mask-rgb.png"
LIGHT=BASE/"lighting-highres"; STOCK=BASE/"decoded-stock"
PAL={"skin":(255,41,71),"bronze":(255,166,5),"iron":(8,71,255),"wood":(255,82,5),"cloth":(13,166,31),"leather":(82,23,6)}
MASK_CACHE={}

DEFS=[
 ("A01","50 px Control",{"height":50}),("A02","52 px",{"height":52}),("A03","54 px",{"height":54}),("A04","56 px",{"height":56}),
 ("B01","Tone Control",{}),("B02","Stronger Dark Floor",{"tone":"dark_floor"}),("B03","Lifted Midtones",{"tone":"lift_mid"}),
 ("B04","Strong S Curve",{"tone":"s_curve"}),("B05","Compressed Highlights",{"tone":"rolloff"}),("B06","Deep Shadows Rolloff",{"tone":"deep_rolloff"}),
 ("C01","Detail Control",{}),("C02","Mild Local Contrast",{"local":.45}),("C03","Strong Local Contrast",{"local":.8}),
 ("C04","Mild Gameplay Sharpen",{"post_sharp":.55}),("C05","Local Contrast Sharp",{"local":.55,"post_sharp":.55}),("C06","Cavity Readability",{"cavity":.55}),
 ("D01","L11 Control",{"light":"D01"}),("D02","Camera Soft Fill",{"light":"D02"}),("D03","Upper Front Softbox",{"light":"D03"}),
 ("D04","Restrained Rim",{"light":"D04"}),("D05","Fill And Rim",{"light":"D05"}),
 ("E01","Rome Faction Colour",{}),("E02","Restrained AoE Player Colour",{"neutral":True,"pc":.45}),
 ("E03","Strong AoE Player Colour",{"neutral":True,"pc":.7}),("E04","Material Chroma",{"chroma":1.16}),
 ("E05","Player Colour Material Chroma",{"neutral":True,"pc":.5,"chroma":1.13}),
 ("F01","Measured Stock Readability",{"height":52,"tone":"s_curve","local":.5,"post_sharp":.45,"pc":.45,"neutral":True}),
 ("F02","Shadow Cavity Fill",{"height":52,"tone":"deep_rolloff","cavity":.4,"light":"D05","pc":.45}),
 ("F03","Gameplay First",{"height":54,"tone":"deep_rolloff","local":.65,"post_sharp":.55,"pc":.55,"chroma":1.12,"neutral":True}),
]

def alpha_box(im):
 b=im.getchannel("A").getbbox()
 if not b:raise ValueError("empty source")
 return b
def class_masks(size):
 if size in MASK_CACHE:return MASK_CACHE[size]
 c=Image.open(CLASS).convert("RGBA").resize(size,Image.Resampling.NEAREST);out={k:Image.new("L",size) for k in PAL}
 for xy,p in zip(((x,y) for y in range(size[1]) for x in range(size[0])),c.getdata()):
  if p[3]<8:continue
  k=min(PAL,key=lambda z:sum((p[i]-PAL[z][i])**2 for i in range(3)))
  if sum((p[i]-PAL[k][i])**2 for i in range(3))<20000:out[k].putpixel(xy,255)
 MASK_CACHE[size]=out;return out
def remap_luma(im,kind):
 rgb=im.convert("RGB"); y=rgb.convert("L"); lut=[]
 for v in range(256):
  if kind=="dark_floor":n=v*(.62+.38*v/255)
  elif kind=="lift_mid":n=v+18*math.exp(-((v-115)/55)**2)
  elif kind=="s_curve":n=255/(1+math.exp(-((v-116)/38)))
  elif kind=="rolloff":n=v if v<155 else 155+(v-155)*.48
  elif kind=="deep_rolloff":n=v*.7 if v<90 else 63+(v-90)*.82 if v<175 else 132.7+(v-175)*.42
  else:n=v
  lut.append(max(0,min(255,round(n))))
 target=y.point(lut); ratio=[]
 for a,b in zip(y.getdata(),target.getdata()):ratio.append(1 if a<2 else b/a)
 data=[]
 for p,r in zip(rgb.getdata(),ratio):data.append(tuple(max(0,min(255,round(x*r))) for x in p))
 out=Image.new("RGB",im.size);out.putdata(data);out.putalpha(im.getchannel("A"));return out
def local_contrast(im,amount):
 y=im.convert("L");detail=ImageChops.subtract(y,y.filter(ImageFilter.GaussianBlur(5)),scale=1,offset=128)
 enhanced=ImageChops.add(im.convert("RGB"),Image.merge("RGB",(detail,detail,detail)),scale=1,offset=round(-128*amount))
 out=Image.blend(im.convert("RGB"),enhanced.convert("RGB"),amount).convert("RGBA");out.putalpha(im.getchannel("A"));return out
def cavity(im,amount):
 y=im.convert("L");blur=y.filter(ImageFilter.GaussianBlur(3));factor=[]
 for a,b in zip(y.getdata(),blur.getdata()):factor.append(max(0,min(255,round(255-amount*max(0,b-a)))))
 shade=Image.new("L",im.size);shade.putdata(factor);rgb=ImageChops.multiply(im.convert("RGB"),Image.merge("RGB",(shade,shade,shade)));rgb.putalpha(im.getchannel("A"));return rgb
def selective_chroma(im,factor,masks):
 sat=ImageEnhance.Color(im.convert("RGB")).enhance(factor).convert("RGBA"); mask=Image.new("L",im.size)
 for k in ("wood","cloth","leather"):mask=ImageChops.lighter(mask,masks[k])
 return Image.composite(sat,im,mask)
def process(cid,p):
 src=Image.open(LIGHT/f"{p['light']}.png" if p.get("light") else (NEUTRAL if p.get("neutral") else SOURCE)).convert("RGBA")
 masks=class_masks(src.size)
 if p.get("tone"):src=remap_luma(src,p["tone"])
 if p.get("local"):src=local_contrast(src,p["local"])
 if p.get("cavity"):src=cavity(src,p["cavity"])
 if p.get("chroma"):src=selective_chroma(src,p["chroma"],masks)
 return src
def pc_mask(canvas,height,hotspot,strength):
 src=Image.open(TINT).convert("RGBA");r=src.getchannel("R");rgba=Image.merge("RGBA",(r,r,r,src.getchannel("A")))
 fitted=downsample_about_feet(rgba,canvas,height,hotspot);m=fitted.getchannel("R").point(lambda v:round(v*strength));return m
def pc_preview(im,mask,color=(35,105,230)):
 # Diagnostic approximation only; the installed SLD retains base detail and
 # uses its native player-colour layer at runtime.
 gray=im.convert("L");tinted=Image.merge("RGBA",tuple(gray.point(lambda v,c=c:round(v*c/255)) for c in color)+(im.getchannel("A"),))
 return Image.composite(tinted,im,mask)
def bronze_metrics(im):
 masks=class_masks(im.size); vals=[]
 for p,m in zip(im.convert("RGB").getdata(),masks["bronze"].getdata()):
  if m>127:vals.append(.2126*p[0]+.7152*p[1]+.0722*p[2])
 vals.sort();return {"maximum":round(max(vals),3),"p95":round(vals[int(.95*(len(vals)-1))],3),"near_white_percent":round(100*sum(x>=245 for x in vals)/len(vals),4)} if vals else None
def label_sheet(items,path,thumb,columns):
 font=ImageFont.load_default();w=columns*thumb[0];rows=math.ceil(len(items)/columns);out=Image.new("RGBA",(w,rows*thumb[1]),(47,71,48,255));d=ImageDraw.Draw(out)
 for i,(name,im) in enumerate(items):
  x=(i%columns)*thumb[0];y=(i//columns)*thumb[1]; fit=im.copy();fit.thumbnail((thumb[0]-12,thumb[1]-30),Image.Resampling.LANCZOS);out.alpha_composite(fit,(x+(thumb[0]-fit.width)//2,y+5));d.rectangle((x,y+thumb[1]-22,x+thumb[0]-1,y+thumb[1]-1),fill=(20,20,20,220));d.text((x+4,y+thumb[1]-18),name,fill="white",font=font)
 out.save(path)
def main():
 HI.mkdir(parents=True,exist_ok=True);GAME.mkdir(parents=True,exist_ok=True);rows=[];high=[];game=[]
 for cid,name,p in DEFS:
  im=process(cid,p);im.save(HI/f"{cid}.png");height=p.get("height",52);g=downsample_about_feet(im,200,height,(100,100))
  if p.get("post_sharp"):g=Image.blend(g,g.filter(ImageFilter.UnsharpMask(1.0,130,2)),p["post_sharp"])
  g.save(GAME/f"{cid}.png");pcm=pc_mask(200,height,(100,100),p["pc"]) if p.get("pc") else Image.new("L",(200,200));pcm.save(GAME/f"{cid}-playercolor.png")
  rows.append({"id":cid,"name":name,"parameters":p,"logical_height":height,"highres_metrics":rgba_metrics(im),"gameplay_metrics":rgba_metrics(g,pc=pcm),"bronze":bronze_metrics(im)})
  hp=im
  if p.get("pc"):
   hm=Image.open(TINT).convert("RGBA").getchannel("R").point(lambda v:round(v*p["pc"]));hp=pc_preview(im,hm)
  high.append((f"{cid} {name}",hp));game.append((f"{cid} {name}",pc_preview(g,pcm) if p.get("pc") else g))
 stocks=[]
 for key in ("militia","man-at-arms","legionary"):
  stocks.append(("Stock "+key,Image.open(STOCK/f"{key}-x1-facet02-frame00.png").convert("RGBA")))
 label_sheet(stocks+high,BASE/"hastati-artistic-sweep-highres.png",(260,260),4)
 label_sheet(stocks+game,BASE/"hastati-artistic-sweep-gameplay.png",(220,150),4)
 payload={"format":"rome2aoe2.hastati-artistic-sweep","version":1,"common":{"composition":"runtime-resolved deterministic representative","material":"Rome II reconstructed v1","pose":"stand sample 0","camera":"45 azimuth/30 elevation","base_light":"L11","decal":"blank; runtime slice unresolved"},"candidates":rows}
 (BASE/"hastati-artistic-candidates.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n");print(json.dumps({"candidate_count":len(rows),"output":str(BASE)},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
