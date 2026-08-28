"""Generate/installable Hastati V2: neutral body first, player color second."""
from __future__ import annotations
import json,math,shutil,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
V=ROOT/"build/python-deps/sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from PIL import Image,ImageChops,ImageDraw,ImageFilter,ImageFont
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import parse_sld,serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets,build_main_layer
from aoe2.generate_v4_ingame_proof import downsample_about_feet,make_shadow
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,GRAPHICS,REFS,FACET

BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration-v2";G=BASE/"ROME2AOE2_AOE_STYLE_HASTATI_V2/resources/_common/drs/graphics";MOD=BASE/"ROME2AOE2_AOE_STYLE_HASTATI_V2"
SOURCE=ROOT/"build/local-integration/rome2/runtime-resolution/renders/hastati-runtime-resolved-representative.png";CLASS=ROOT/"build/local-integration/rome2/cross-unit-calibration/renders-set-a/hastati-material-classes.png";TINT=ROOT/"build/local-integration/rome2/cross-unit-calibration/tint-masks/hastati-mask-rgb.png"
SOURCE_DAT=ROOT/"test_data/empires2_x2_p1.dat";TEMPLATE=ROOT/"test_data/EmptyMap.aoe2scenario";TEX=ROOT/"build/tools/directxtex-may2026/texconv.exe";DAT=BASE/"hastati_v2.dat";MODDAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2AoEStyleCalibrationHastatiV2.aoe2scenario"
PAL={"skin":(255,41,71),"bronze":(255,166,5),"iron":(8,71,255),"wood":(255,82,5),"cloth":(13,166,31),"leather":(82,23,6)};MASKS={}
TONE={"N01":(108,.10,40),"N02":(100,.16,36),"N03":(90,.22,32),"N04":(86,.275,28),"N05":(79,.31,24),"N06":(72,.35,20)}
SHADOW={"legacy":None,"SH01":(.65,48),"SH02":(.55,45),"SH03":(.47,42)}

def class_masks(size):
 if size in MASKS:return MASKS[size]
 c=Image.open(CLASS).convert("RGBA").resize(size,Image.Resampling.NEAREST);out={k:Image.new("L",size) for k in PAL}
 for i,p in enumerate(c.getdata()):
  if p[3]<8:continue
  k=min(PAL,key=lambda z:sum((p[j]-PAL[z][j])**2 for j in range(3)));out[k].putpixel((i%size[0],i//size[0]),255)
 MASKS[size]=out;return out
def monotonic_lut(im,target,dark_fraction,dark_output):
 vals=sorted(v for v,a in zip(im.convert("L").getdata(),im.getchannel("A").getdata()) if a>8);xd=vals[int((len(vals)-1)*dark_fraction)];xm=vals[len(vals)//2];x75=vals[int(.75*(len(vals)-1))];x95=vals[int(.95*(len(vals)-1))]
 pts=[(0,0),(max(1,xd),dark_output),(max(xd+1,xm),target),(max(xm+1,x75),min(170,target+38)),(max(x75+1,x95),min(205,target+85)),(255,min(225,target+135))]
 # Collapse duplicate x and enforce monotonic y.
 clean=[]
 for x,y in pts:
  x=min(255,x);y=max(clean[-1][1]+1 if clean else 0,y)
  if clean and x<=clean[-1][0]:continue
  clean.append((x,min(255,y)))
 lut=[]
 for x in range(256):
  a,b=clean[0],clean[-1]
  for i in range(len(clean)-1):
   if clean[i][0]<=x<=clean[i+1][0]:a,b=clean[i],clean[i+1];break
  t=0 if b[0]==a[0] else (x-a[0])/(b[0]-a[0]);t=t*t*(3-2*t);lut.append(round(a[1]+(b[1]-a[1])*t))
 # A tiny 1-D blur removes knot shoulders while preserving monotonicity.
 line=Image.new("L",(256,1));line.putdata(lut);lut=list(line.filter(ImageFilter.GaussianBlur(1.2)).getdata());
 for i in range(1,256):lut[i]=max(lut[i],lut[i-1])
 return lut
def luma_map(im,lut):
 rgb=im.convert("RGB");y=rgb.convert("L");target=y.point(lut);data=[]
 for p,a,b in zip(rgb.getdata(),y.getdata(),target.getdata()):
  r=1 if a<2 else b/a;data.append(tuple(max(0,min(255,round(v*r))) for v in p))
 out=Image.new("RGB",im.size);out.putdata(data);out.putalpha(im.getchannel("A"));return out
def tone(im,tid):return im if tid=="N00" else luma_map(im,monotonic_lut(im,*TONE[tid]))
def bronze(im,level):
 if level==1:return im
 mask=class_masks(im.size)["bronze"];rgb=im.convert("RGB");out=[]
 slope=.62 if level==2 else .38;warm=.08 if level==2 else .16
 for p,m in zip(rgb.getdata(),mask.getdata()):
  if not m:out.append(p);continue
  y=.2126*p[0]+.7152*p[1]+.0722*p[2];ny=y if y<135 else 135+(y-135)*slope;r=1 if y<2 else ny/y;q=[max(0,min(255,round(v*r))) for v in p];f=warm*max(0,min(1,(y-130)/100));q=[round(q[i]*(1-f)+(255,174,58)[i]*f) for i in range(3)];out.append(tuple(q))
 x=Image.new("RGB",im.size);x.putdata(out);x.putalpha(im.getchannel("A"));return x
def detail(im,level):
 if level==1:return im
 amount=.28 if level==2 else .48;rgb=im.convert("RGB");blur=rgb.filter(ImageFilter.GaussianBlur(3.0));sharp=Image.blend(rgb,ImageChops.add(rgb,ImageChops.subtract(rgb,blur),scale=1.0),amount);sharp.putalpha(im.getchannel("A"));return sharp
def shadow_v2(main,kind,hotspot):
 if kind=="legacy":return make_shadow(main)
 ratio,opacity=SHADOW[kind];a=main.getchannel("A");box=a.getbbox();body=sum(v>8 for v in a.getdata());crop=a.crop(box);h=max(3,round(crop.height*.18));target=body*ratio
 best=None
 for s in [x/100 for x in range(35,301)]:
  w=max(3,round(crop.width*s));q=crop.resize((w,h),Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(1.2 if main.width==200 else 2.4));layer=Image.new("L",main.size);layer.paste(q,(hotspot[0]-w//2,hotspot[1]-h//2+2));area=sum(v>8 for v in layer.getdata());err=abs(area-target)
  if best is None or err<best[0]:best=(err,layer)
 layer=best[1];nz=[v for v in layer.getdata() if v>0];factor=opacity/statistics.fmean(nz) if nz else 1;layer=layer.point(lambda v:max(0,min(255,round(v*factor))));rgba=Image.new("RGBA",main.size,(0,0,0,255));rgba.putalpha(layer);return rgba
def pc_support(main,logical,hotspot,target):
 raw=Image.open(TINT).convert("RGBA");r=raw.getchannel("R");rgba=Image.merge("RGBA",(r,r,r,raw.getchannel("A")));m=downsample_about_feet(rgba,main.width,logical,hotspot).getchannel("R");a=main.getchannel("A");ml=build_main_layer(main);x1,y1,x2,y2=ml.offset_x1,ml.offset_y1,ml.offset_x2,ml.offset_y2
 best=None
 for threshold in range(1,256):
  eligible=Image.new("L",main.size);ep=eligible.load();mp=m.load();ap=a.load();blocks=set()
  for y in range(y1,y2):
   for x in range(x1,x2):
    if ap[x,y]>8 and mp[x,y]>=threshold:blocks.add(((x-x1)//4,(y-y1)//4))
  covered=sum(1 for y in range(y1,y2) for x in range(x1,x2) if ap[x,y]>8 and ((x-x1)//4,(y-y1)//4) in blocks);body=sum(v>8 for v in a.getdata());cov=covered/body if body else 0;err=abs(cov-target)
  if best is None or err<best[0]:best=(err,threshold,blocks,cov)
 _,threshold,blocks,cov=best
 eligible=Image.new("L",main.size);p=eligible.load()
 for y in range(y1,y2):
  for x in range(x1,x2):
   if a.getpixel((x,y))>8 and m.getpixel((x,y))>=threshold:p[x,y]=255
 return eligible,threshold,cov
def pc_layer(main,eligible,strength):
 lum=main.convert("L");out=Image.new("RGBA",main.size);data=[]
 for l,e,a in zip(lum.getdata(),eligible.getdata(),main.getchannel("A").getdata()):
  if not e:data.append((0,0,0,0));continue
  idx=(13-round(l*10/255)) if strength=="normal" else (15-round(l*15/255));idx=max(0,min(15,idx));data.append((idx,idx,idx,a))
 out.putdata(data);return out
def master(tone_id="N00",bronze_level=1,detail_level=1):return detail(bronze(tone(Image.open(SOURCE).convert("RGBA"),tone_id),bronze_level),detail_level)
def bronze_metrics(im):
 vals=[];cols=[];mask=class_masks(im.size)["bronze"]
 for p,m in zip(im.convert("RGB").getdata(),mask.getdata()):
  if m:vals.append(.2126*p[0]+.7152*p[1]+.0722*p[2]);cols.append((max(p)-min(p))/max(1,max(p))*255)
 vals.sort();return {"p50":round(statistics.median(vals),3),"p90":round(vals[int(.9*(len(vals)-1))],3),"p95":round(vals[int(.95*(len(vals)-1))],3),"maximum":round(max(vals),3),"near_white_percent":round(100*sum(v>=245 for v in vals)/len(vals),4),"mean_chroma":round(statistics.fmean(cols),3)}

def definitions():
 d=[]
 for i,h in enumerate((40,42,44,46,48,50),1):d.append((f"S{i:02d}",f"Size {h}",h,"N00",1,"legacy",1,None,None))
 d.append(("N00","Neutral Control",44,"N00",1,"legacy",1,None,None))
 for i in range(1,7):d.append((f"N{i:02d}",f"Tone {i}",44,f"N{i:02d}",1,"legacy",1,None,None))
 for i in range(1,4):d.append((f"BR{i:02d}",f"Bronze {i}",44,"N04",i,"legacy",1,None,None))
 for i in range(1,4):d.append((f"SH{i:02d}",f"Shadow {i}",44,"N04",2,f"SH{i:02d}",1,None,None))
 for i in range(1,4):d.append((f"D{i:02d}",f"Detail {i}",44,"N04",2,"SH02",i,None,None))
 d += [("NF01","Balanced 42",42,"N04",2,"SH02",2,None,None),("NF02","Balanced 44",44,"N04",2,"SH02",2,None,None),("NF03","Balanced 46",46,"N04",2,"SH02",2,None,None),("NF04","Darker 44",44,"N05",2,"SH02",2,None,None),("NF05","Stronger Detail 44",44,"N04",2,"SH02",3,None,None),("NF06","Softer Detail 44",44,"N03",2,"SH01",1,None,None)]
 d.append(("PC00","No Player Color",44,"N04",2,"SH02",2,None,None))
 for i,target in enumerate((.225,.30,.40,.50),1):
  d.append((f"PC{i:02d}",f"PC Support {round(target*100)} Normal",44,"N04",2,"SH02",2,target,"normal"));d.append((f"PC{i:02d}S",f"PC Support {round(target*100)} Strong",44,"N04",2,"SH02",2,target,"strong"))
 d += [("P01","NF01 Conservative PC",42,"N04",2,"SH02",2,.30,"normal"),("P02","NF02 Conservative PC",44,"N04",2,"SH02",2,.30,"normal"),("P03","NF03 Conservative PC",46,"N04",2,"SH02",2,.30,"normal"),("P04","NF02 Moderate PC",44,"N04",2,"SH02",2,.40,"normal")]
 return d
def sheet(rows,path,groups,pc=False):
 leg=decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet']);font=ImageFont.load_default();cw,ch=220,180;lines=[]
 for ids in groups:lines.append([("Stock Legionary",leg)]+[(x["id"]+" "+x["name"],x["decoded_x2"]) for x in rows if x["id"] in ids])
 out=Image.new("RGBA",(cw*max(len(x) for x in lines),ch*len(lines)),(47,71,48,255));d=ImageDraw.Draw(out)
 for y,line in enumerate(lines):
  for x,(name,obj) in enumerate(line):
   im=display(obj);b=ImageChops.lighter(obj["main"].getchannel("A"),obj["shadow"].convert("L")).getbbox();q=im.crop((max(0,b[0]-6),max(0,b[1]-6),min(im.width,b[2]+6),min(im.height,b[3]+6)));out.alpha_composite(q,(x*cw+(cw-q.width)//2,y*ch+5));d.text((x*cw+4,y*ch+158),name,fill="white",font=font)
 out.save(path)
def pixels4(rows):
 leg=decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet']);items=[("Stock Legionary",leg)]+[(x["id"],x["decoded_x2"]) for x in rows if x["id"] in ("NF02","PC01","PC02","PC03")];out=Image.new("RGBA",(300*len(items),460),(47,71,48,255));d=ImageDraw.Draw(out)
 for i,(name,x) in enumerate(items):b=x["main"].getchannel("A").getbbox();q=display(x).crop(b).resize(((b[2]-b[0])*4,(b[3]-b[1])*4),Image.Resampling.NEAREST);q.thumbnail((290,420),Image.Resampling.NEAREST);out.alpha_composite(q,(i*300+(300-q.width)//2,5));d.text((i*300+4,438),name,fill="white")
 out.save(BASE/"player-color-detail-comparison-4x.png");out.save(BASE/"hastati-v2-4x-pixels.png")
def main():
 BASE.mkdir(parents=True,exist_ok=True);G.mkdir(parents=True,exist_ok=True);ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEX);rows=[]
 for i,(cid,name,h,tid,br,sh,de,pc_target,pc_strength) in enumerate(definitions()):
  uid=3201+i;stem=f"rome2_hastati_v2_{cid.lower()}";display_name=f"Hastati V2 {cid} {name}";gr=ws.graphic_manager.add_graphic(stem,name=display_name,frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=display_name;u.standing_sprite_id1=u.standing_sprite_id2=gr.id;hi=master(tid,br,de);row={"id":cid,"name":name,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"logical_height":h,"tone":tid,"bronze":br,"shadow":sh,"detail":de,"player_support_target":pc_target,"player_strength":pc_strength,"bronze_metrics_highres":bronze_metrics(hi)}
  for zoom,canvas,logical,hotspot in (("x1",200,h,(100,100)),("x2",400,h*2,(200,200))):
   main=downsample_about_feet(hi,canvas,logical,hotspot);shadow=shadow_v2(main,sh,hotspot);pc=None
   if pc_target is not None:
    support,threshold,estimated=pc_support(main,logical,hotspot,pc_target);pc=pc_layer(main,support,pc_strength);row[f"pc_{zoom}"]={"source_r_threshold":threshold,"estimated_block_coverage":round(estimated,4)}
   raw=serialize_sld(author_identical_facets(main,shadow,16,hotspot,encoder=enc,player_color=pc));(G/f"{stem}_{zoom}.sld").write_bytes(raw)
  x2=decode(G/f"{stem}_x2.sld",0);row["decoded_x2"]=x2;row["metrics_x2"]=metrics(x2);rows.append(row)
 ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Hastati V2 neutral-first AoE style calibration.","Title":"Rome2AoE2 Hastati Style Calibration V2"},indent=2)+"\n")
 # Compact scenario: only nonredundant requested comparisons.
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));layout=[["stock"],["S01","S02","S03","S04","S05","S06"],["N01","N02","N03","N04","N05","N06"],["SH01","SH02","SH03"],["NF01","NF02","NF03","NF04","NF05","NF06"],["PC01","PC02","PC03","PC04"],["P01","P02","P03","P04"]];placements=[]
 for row,ids in enumerate(layout):
  y=44-row*4;x=8;sc.unit_manager.add_unit(player=1,unit_const=1793,x=x,y=y,rotation=0);placements.append({"row":row,"column":0,"id":"stock","name":"Stock Legionary","unit_id":1793,"x":x,"y":y})
  if row==0:
   for col,(uid,n) in enumerate(((75,"Stock Man-at-Arms"),(74,"Stock Militia")),1):sc.unit_manager.add_unit(player=1,unit_const=uid,x=8+col*4,y=y,rotation=0);placements.append({"row":row,"column":col,"id":"stock","name":n,"unit_id":uid,"x":8+col*4,"y":y})
  else:
   for col,cid in enumerate(ids,1):r=next(z for z in rows if z["id"]==cid);xx=8+col*4;sc.unit_manager.add_unit(player=1,unit_const=r["unit_id"],x=xx,y=y,rotation=0);placements.append({"row":row,"column":col,"id":cid,"name":r["name"],"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"x":xx,"y":y})
 sc.write_to_file(str(SCEN));legend=["Hastati V2 compact comparison"]+[f"row {p['row']} col {p['column']} ({p['x']},{p['y']}) | {p['id']} | unit {p['unit_id']} | {p['name']}" for p in placements];(BASE/"LEGEND.txt").write_text("\n".join(legend)+"\n")
 sheet(rows,BASE/"hastati-v2-neutral-uhd.png",[["S01","S02","S03","S04","S05","S06"],["N00","N01","N02","N03","N04","N05","N06"],["BR01","BR02","BR03"],["SH01","SH02","SH03"],["D01","D02","D03"],["NF01","NF02","NF03","NF04","NF05","NF06"]]);sheet(rows,BASE/"hastati-v2-playercolor-uhd.png",[["PC00","PC01","PC01S","PC02","PC02S"],["PC03","PC03S","PC04","PC04S"],["P01","P02","P03","P04"]]);pixels4(rows)
 serial=[]
 for r in rows:
  x={k:v for k,v in r.items() if k!="decoded_x2"};serial.append(x)
 report={"format":"rome2aoe2.hastati-style-v2","version":1,"fixed":{"composition":"runtime-resolved Hastati representative","materials":"unchanged reconstructed Rome II","lighting":"L11","master":str(SOURCE),"x2_independent_from_x1":True},"candidates":serial,"placements":placements,"mod_root":str(MOD),"scenario":str(SCEN),"legend":str(BASE/"LEGEND.txt")};(BASE/"hastati-v2-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"count":len(rows),"mod":str(MOD),"scenario":str(SCEN)},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
