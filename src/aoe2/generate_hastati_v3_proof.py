"""Generate the bounded Hastati V3 readability finishing proof."""
from __future__ import annotations
import colorsys,json,math,shutil,statistics,sys
from collections import deque
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
V=ROOT/"build/python-deps/sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from PIL import Image,ImageChops,ImageDraw,ImageFilter,ImageFont
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets,build_main_layer
from aoe2.generate_v4_ingame_proof import downsample_about_feet
from aoe2.generate_hastati_v2_proof import SOURCE,CLASS,TINT,SOURCE_DAT,TEMPLATE,TEX,class_masks,monotonic_lut,luma_map,bronze,shadow_v2
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,GRAPHICS,REFS,FACET

BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration-v3";MOD=BASE/"ROME2AOE2_AOE_STYLE_HASTATI_V3";G=MOD/"resources/_common/drs/graphics"
DAT=BASE/"hastati_v3.dat";MODDAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2AoEStyleCalibrationHastatiV3.aoe2scenario"
# Smooth tone families.  Cloth treatment is a separate finishing control.
TONES={"A1":(94,.18,35),"A2":(88,.22,31),"A3":(86,.27,28),"A4":(80,.30,25)}
DEFS=[
 ("A1","Mild Dark Red",1,0,0,None),("A2","Medium Dark Red",2,0,0,None),("A3","Shadow Separation Red",3,0,0,None),("A4","Strong Separation Red",4,0,0,None),
 ("B1","Mild Local Contrast",2,1,0,None),("B2","Medium Local Contrast",2,2,0,None),("B3","Strong Local Contrast",2,3,0,None),
 ("B4","Mild Acutance",2,0,1,None),("B5","Medium Acutance",2,0,2,None),("B6","Local Contrast Acutance",2,2,3,None),
 ("C1","Shield Only",2,2,3,"shield"),("C2","Shield Tiny Cloth",2,2,3,"tiny"),("C3","Shield Restrained Cloth",2,2,3,"moderate"),("C4","Bounded Broad Diagnostic",2,2,3,"broad")]

def red_cloth_mask(size):
 src=Image.open(SOURCE).convert("RGBA").resize(size,Image.Resampling.NEAREST);cloth=class_masks(size)["cloth"];out=Image.new("L",size);op=out.load()
 for y in range(size[1]):
  for x in range(size[0]):
   r,g,b,a=src.getpixel((x,y))
   # Material provenance identifies the visible tunic as cloth. Its darkest
   # source texels carry too little chroma to survive the tone/downsample/BC1
   # chain, so include the entire tunic material rather than selecting only
   # already-bright red texels.
   if cloth.getpixel((x,y)) and a>8:op[x,y]=255
 return out

def preserve_red(source,toned,strength):
 mask=red_cloth_mask(source.size);out=toned.convert("RGBA");sp=source.convert("RGB").load();op=out.load()
 for y in range(out.height):
  for x in range(out.width):
   if not mask.getpixel((x,y)):continue
   sr,sg,sb=sp[x,y];tr,tg,tb,a=op[x,y];h,s,_=colorsys.rgb_to_hsv(sr/255,sg/255,sb/255);_,_,tv=colorsys.rgb_to_hsv(tr/255,tg/255,tb/255)
   # Retain source hue/chroma while leaving the tone curve in charge of value.
   # The rendered L11 cloth is warm-shifted; pull only the already-red cloth
   # hue back toward dark crimson and give it a bounded chroma/value floor.
   h=min(h,.045);rr,gg,bb=colorsys.hsv_to_rgb(h,max(s*.92,.62*strength),max(tv,.35));op[x,y]=(round(rr*255),round(gg*255),round(bb*255),a)
 return out

def local_contrast(im,level):
 if not level:return im
 radius=(7,6,5)[level-1];amount=(.18,.30,.42)[level-1];rgb=im.convert("RGB");blur=rgb.filter(ImageFilter.GaussianBlur(radius));delta=ImageChops.subtract(rgb,blur).point(lambda v:max(0,min(255,round((v-128)*amount+128))))
 # Pillow subtract is biased; use bounded per-channel differences explicitly.
 result=[]
 for p,b in zip(rgb.getdata(),blur.getdata()):result.append(tuple(max(0,min(255,round(p[i]+(p[i]-b[i])*amount))) for i in range(3)))
 out=Image.new("RGB",im.size);out.putdata(result);out.putalpha(im.getchannel("A"));return out

def acutance(im,level):
 if not level:return im
 # Applied after the dedicated x1/x2 downsample; radius scales with raster density.
 radius=1.0 if im.width==200 else 2.0;amount={1:.18,2:.35,3:.10}[level];rgb=im.convert("RGB");blur=rgb.filter(ImageFilter.GaussianBlur(radius));data=[]
 for p,b in zip(rgb.getdata(),blur.getdata()):data.append(tuple(max(0,min(255,round(p[i]+(p[i]-b[i])*amount))) for i in range(3)))
 out=Image.new("RGB",im.size);out.putdata(data);out.putalpha(im.getchannel("A"));return out

def master(tone_level,local_level):
 src=Image.open(SOURCE).convert("RGBA");tid=f"A{tone_level}";toned=luma_map(src,monotonic_lut(src,*TONES[tid]));finished=local_contrast(bronze(toned,2),local_level);return preserve_red(src,finished,(.75,.85,.95,1.0)[tone_level-1])

def largest_component(mask):
 p=mask.load();seen=set();best=[]
 for y in range(mask.height):
  for x in range(mask.width):
   if not p[x,y] or (x,y) in seen:continue
   q=deque([(x,y)]);seen.add((x,y));group=[]
   while q:
    a,b=q.popleft();group.append((a,b))
    for n in ((a-1,b),(a+1,b),(a,b-1),(a,b+1)):
     if 0<=n[0]<mask.width and 0<=n[1]<mask.height and n not in seen and p[n[0],n[1]]:seen.add(n);q.append(n)
   if len(group)>len(best):best=group
 out=Image.new("L",mask.size);o=out.load()
 for xy in best:o[xy]=255
 return out

def support_master(kind):
 c=Image.open(CLASS).convert("RGBA");unknown=Image.new("L",c.size);u=unknown.load()
 for y in range(c.height):
  for x in range(c.width):
   r,g,b,a=c.getpixel((x,y));u[x,y]=255 if a>8 and r>220 and b>180 and g<80 else 0
 shield=largest_component(unknown);tint=Image.open(TINT).convert("RGBA").getchannel("R");cloth=class_masks(c.size)["cloth"];out=shield.copy();o=out.load()
 threshold={"shield":256,"tiny":230,"moderate":175,"broad":115}[kind]
 if threshold<256:
  for y in range(c.height):
   for x in range(c.width):
    if cloth.getpixel((x,y)) and tint.getpixel((x,y))>=threshold:o[x,y]=255
 return out

def pc_for(main,logical,hotspot,kind):
 # Start with the source-derived shield component. Add cloth blocks in
 # descending Rome-R confidence until a separate, bounded coverage target is
 # reached. This keeps support area independent from palette shade strength.
 shield=support_master("shield");srgb=Image.merge("RGBA",(shield,shield,shield,shield));sm=downsample_about_feet(srgb,main.width,logical,hotspot).getchannel("R")
 tint=Image.open(TINT).convert("RGBA").getchannel("R");trgb=Image.merge("RGBA",(tint,tint,tint,tint));tm=downsample_about_feet(trgb,main.width,logical,hotspot).getchannel("R")
 cloth=class_masks((800,800))["cloth"];crgb=Image.merge("RGBA",(cloth,cloth,cloth,cloth));cm=downsample_about_feet(crgb,main.width,logical,hotspot).getchannel("R");ml=build_main_layer(main);a=main.getchannel("A");blocks=set()
 for y in range(ml.offset_y1,ml.offset_y2):
  for x in range(ml.offset_x1,ml.offset_x2):
   if a.getpixel((x,y))>8 and sm.getpixel((x,y))>127:blocks.add(((x-ml.offset_x1)//4,(y-ml.offset_y1)//4))
 target={"shield":.20,"tiny":.25,"moderate":.31,"broad":.38}[kind];body=sum(v>8 for v in a.getdata())
 candidates={}
 for y in range(ml.offset_y1,ml.offset_y2):
  for x in range(ml.offset_x1,ml.offset_x2):
   b=((x-ml.offset_x1)//4,(y-ml.offset_y1)//4)
   if a.getpixel((x,y))>8 and cm.getpixel((x,y))>127 and b not in blocks:candidates[b]=max(candidates.get(b,0),tm.getpixel((x,y)))
 def coverage(bs):return sum(1 for y in range(ml.offset_y1,ml.offset_y2) for x in range(ml.offset_x1,ml.offset_x2) if a.getpixel((x,y))>8 and ((x-ml.offset_x1)//4,(y-ml.offset_y1)//4) in bs)/body
 if kind!="shield":
  for b,_ in sorted(candidates.items(),key=lambda z:(-z[1],z[0])):
   if coverage(blocks)>=target:break
   blocks.add(b)
 support=Image.new("L",main.size);s=support.load();lum=main.convert("L");layer=Image.new("RGBA",main.size);lp=layer.load();covered=0
 for y in range(ml.offset_y1,ml.offset_y2):
  for x in range(ml.offset_x1,ml.offset_x2):
   if a.getpixel((x,y))>8 and ((x-ml.offset_x1)//4,(y-ml.offset_y1)//4) in blocks:
    covered+=1;s[x,y]=255;idx=max(1,min(13,13-round(lum.getpixel((x,y))*10/255)));lp[x,y]=(idx,idx,idx,a.getpixel((x,y)))
 return layer,covered/body if body else 0

def red_metrics(obj):
 main=obj["main"];raw=red_cloth_mask((800,800));mask=downsample_about_feet(Image.merge("RGBA",(raw,raw,raw,raw)),main.width,44 if main.width==200 else 88,(main.width//2,main.height//2)).getchannel("R");vals=[]
 for p,m,a in zip(main.convert("RGB").getdata(),mask.getdata(),main.getchannel("A").getdata()):
  if m>64 and a>8:
   h,s,v=colorsys.rgb_to_hsv(*(q/255 for q in p));vals.append((h,s,v,.2126*p[0]+.7152*p[1]+.0722*p[2]))
 if not vals:return {"pixels":0}
 return {"pixels":len(vals),"mean_hue_degrees":round(statistics.fmean(v[0] for v in vals)*360,3),"mean_saturation":round(statistics.fmean(v[1] for v in vals)*255,3),"median_luminance":round(statistics.median(v[3] for v in vals),3),"black_percent":round(100*sum(v[3]<=20 for v in vals)/len(vals),3)}

def sheet(rows,path,ids,pc=False):
 leg=decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet']);lines=[]
 for group in ids:lines.append([("Stock Legionary",leg)]+[(r["id"]+" "+r["name"],r["decoded_x2"]) for r in rows if r["id"] in group])
 cw,ch=230,180;out=Image.new("RGBA",(cw*max(map(len,lines)),ch*len(lines)),(47,71,48,255));d=ImageDraw.Draw(out)
 for yy,line in enumerate(lines):
  for xx,(name,obj) in enumerate(line):
   b=ImageChops.lighter(obj["main"].getchannel("A"),obj["shadow"].convert("L")).getbbox();q=display(obj).crop((max(0,b[0]-8),max(0,b[1]-8),min(400,b[2]+8),min(400,b[3]+8)));out.alpha_composite(q,(xx*cw+(cw-q.width)//2,yy*ch+4));d.text((xx*cw+4,yy*ch+160),name,fill="white")
 out.save(path)

def pixels4(rows):
 leg=decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet']);items=[("Stock Legionary",leg)]+[(r["id"],r["decoded_x2"]) for r in rows if r["id"] in ("A2","B2","B4","B6","C1","C2")];out=Image.new("RGBA",(280*len(items),450),(47,71,48,255));d=ImageDraw.Draw(out)
 for i,(name,obj) in enumerate(items):
  b=obj["main"].getchannel("A").getbbox();q=display(obj).crop(b).resize(((b[2]-b[0])*4,(b[3]-b[1])*4),Image.Resampling.NEAREST);q.thumbnail((270,415),Image.Resampling.NEAREST);out.alpha_composite(q,(i*280+(280-q.width)//2,4));d.text((i*280+4,430),name,fill="white")
 out.save(BASE/"hastati-v3-4x-pixels.png")

def main():
 BASE.mkdir(parents=True,exist_ok=True);G.mkdir(parents=True,exist_ok=True);ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEX);rows=[]
 for i,(cid,name,tone_level,local_level,sharp_level,pc_kind) in enumerate(DEFS):
  uid=3301+i;stem=f"rome2_hastati_v3_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati V3 {cid} {name}",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati V3 {cid} {name}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id;hi=master(tone_level,local_level);row={"id":cid,"name":name,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"logical_height":44,"tone":f"A{tone_level}","local_contrast":local_level,"acutance":sharp_level,"player_support":pc_kind}
  for zoom,canvas,logical,hot in (("x1",200,44,(100,100)),("x2",400,88,(200,200))):
   body=acutance(downsample_about_feet(hi,canvas,logical,hot),sharp_level);shadow=shadow_v2(body,"SH02",hot);pc=None
   if pc_kind:pc,cov=pc_for(body,logical,hot,pc_kind);row[f"player_coverage_{zoom}"]=round(cov,4)
   raw=serialize_sld(author_identical_facets(body,shadow,16,hot,encoder=enc,player_color=pc));(G/f"{stem}_{zoom}.sld").write_bytes(raw)
   dec=decode(G/f"{stem}_{zoom}.sld",0);row[f"metrics_{zoom}"]=metrics(dec);row[f"red_cloth_{zoom}"]=red_metrics(dec)
  row["decoded_x2"]=decode(G/f"{stem}_x2.sld",0);rows.append(row)
 ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Hastati V3 bounded readability finishing calibration.","Title":"Rome2AoE2 Hastati Style Calibration V3"},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));layout=[["stock"],["A1","A2","A3","A4"],["B1","B2","B3"],["B4","B5","B6"],["C1","C2","C3","C4"]];placements=[]
 for rr,ids in enumerate(layout):
  y=38-rr*4;sc.unit_manager.add_unit(player=1,unit_const=1793,x=8,y=y,rotation=0);placements.append({"row":rr,"column":0,"id":"stock","unit_id":1793,"x":8,"y":y})
  if rr==0:
   for cc,uid in enumerate((75,74),1):sc.unit_manager.add_unit(player=1,unit_const=uid,x=8+cc*4,y=y,rotation=0)
  else:
   for cc,cid in enumerate(ids,1):r=next(x for x in rows if x["id"]==cid);x=8+cc*4;sc.unit_manager.add_unit(player=1,unit_const=r["unit_id"],x=x,y=y,rotation=0);placements.append({"row":rr,"column":cc,"id":cid,"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"x":x,"y":y})
 sc.write_to_file(str(SCEN));legend=["Hastati V3 compact comparison"]+[f"row {p['row']} col {p['column']} ({p['x']},{p['y']}) | {p['id']} | unit {p['unit_id']}" for p in placements];(BASE/"LEGEND.txt").write_text("\n".join(legend)+"\n")
 sheet(rows,BASE/"hastati-v3-neutral-uhd.png",[["A1","A2","A3","A4"],["B1","B2","B3"],["B4","B5","B6"]]);sheet(rows,BASE/"hastati-v3-playercolor-uhd.png",[["C1","C2","C3","C4"]]);pixels4(rows)
 serial=[]
 for r in rows:serial.append({k:v for k,v in r.items() if k!="decoded_x2"})
 report={"format":"rome2aoe2.hastati-style-v3","version":1,"fixed":{"composition":"runtime-resolved deterministic representative","selector":"stable-first-valid; unresolved randomness retained in effective-unit metadata","materials":"unchanged","textures":"unchanged","lighting":"L11","logical_height":44,"shadow":"SH02","x1_x2_independent":True},"candidates":serial,"placements":placements,"recommendation":{"neutral":"B6","player_color":"C1","note":"Metric-informed starting points only; manual in-game selection remains authoritative."},"paths":{"mod":str(MOD),"scenario":str(SCEN),"legend":str(BASE/"LEGEND.txt")}}
 (BASE/"hastati-v3-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"candidates":len(rows),"mod":str(MOD),"scenario":str(SCEN)},indent=2))
if __name__=="__main__":raise SystemExit(main())
