"""Generate the small Hastati material-aware finishing comparison."""
from __future__ import annotations
import colorsys,json,shutil,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
from PIL import Image,ImageChops,ImageDraw,ImageFilter
import numpy as np
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.generate_hastati_v3_proof import master as v3master,acutance,pc_for
from aoe2.aoe_sprite_finish import finish,semantic_masks,resize_mask
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,GRAPHICS,REFS,FACET

BASE=ROOT/"build/local-integration/rome2/material-aware-finishing";IN=BASE/"inputs";MOD=BASE/"ROME2AOE2_HASTATI_MATERIAL_FINISH";G=MOD/"resources/_common/drs/graphics";DAT=BASE/"hastati_material_finish.dat";MODDAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2HastatiMaterialFinish.aoe2scenario"
ID=Image.open(IN/"hastati-material-id-3200.png").convert("RGBA")
ACTIVE={"cloth","skin","bronze","shield body","leather","other"}
DEFS=[("SRC","Source Control","source",800),("A2","Current A2","a2",800),("B6","Current B6","b6",800),("CP01","Tone L + Source Chroma","cp1",800),("CP02","Cloth Chroma 110","cp110",800),("CP03","Cloth Chroma 120","cp120",800),("CP04","Selective Cloth 115","selective",800),("CD01","CP03 Mild Luma Detail","d01",800),("CD02","CP03 Medium Luma Detail","d02",800),("CD03","CP03 Edge Aware","d03",800),("CD04","Material Aware Detail","d04",800),("SS32","CP03 3200 Lanczos","ss",3200),("BEST","Combined Material Finish","best",3200),("BESTPC","Combined Shield PC","bestpc",3200)]
def downsample(im,canvas,logical,hotspot,filter):
 a=im.getchannel("A");box=a.getbbox()
 if not box:return Image.new("RGBA",(canvas,canvas))
 crop=im.crop(box);feet=(im.width/2-box[0],im.height/2-box[1]);scale=logical/crop.height;size=(max(1,round(crop.width*scale)),logical);q=crop.resize(size,filter);out=Image.new("RGBA",(canvas,canvas));out.alpha_composite(q,(round(hotspot[0]-feet[0]*scale),round(hotspot[1]-feet[1]*scale)));return out
def high(kind,size):
 src=Image.open(IN/f"hastati-master-{size}.png").convert("RGBA")
 if kind=="source":return src,{"stage":"source"}
 if kind=="a2":return v3master(2,0),{"stage":"V3 A2"}
 if kind=="b6":return v3master(2,2),{"stage":"V3 B6 pre-acutance"}
 cfg={"cp1":(1,False,False,"D00"),"cp110":(1.1,False,False,"D00"),"cp120":(1.2,False,False,"D00"),"selective":(1,True,False,"D00"),"d01":(1.2,False,False,"D01"),"d02":(1.2,False,False,"D02"),"d03":(1.2,False,False,"D03"),"d04":(1.2,False,True,"D04"),"ss":(1.2,False,False,"D00"),"best":(1.2,False,True,"D01"),"bestpc":(1.2,False,True,"D01")}[kind]
 out,_,edge,backend=finish(src,ID,*cfg,ACTIVE);backend.update({"boundary_pixels":int((edge>.1).sum()),"cloth_chroma_scale":cfg[0],"selective":cfg[1],"boundary":cfg[2],"detail":cfg[3]});return out,backend
def material_metrics(obj):
 main=obj["main"];raw=semantic_masks(ID,ACTIVE);out={}
 for name,mask in raw.items():
  rgba=Image.fromarray(np.dstack((np.repeat((mask*255).astype(np.uint8)[...,None],3,2),(mask*255).astype(np.uint8))),"RGBA");m=downsample(rgba,400,88,(200,200),Image.Resampling.LANCZOS).getchannel("R");vals=[];hues=[]
  for p,w,a in zip(main.convert("RGB").getdata(),m.getdata(),main.getchannel("A").getdata()):
   if w>32 and a>8:vals.append(.2126*p[0]+.7152*p[1]+.0722*p[2]);h,s,v=colorsys.rgb_to_hsv(*(x/255 for x in p));hues.append((h*360,s*255))
  out[name]={"pixels":len(vals),"mean_luminance":round(statistics.fmean(vals),3) if vals else None,"median_luminance":round(statistics.median(vals),3) if vals else None,"mean_hue_degrees":round(statistics.fmean(x[0] for x in hues),3) if hues else None,"mean_chroma":round(statistics.fmean(x[1] for x in hues),3) if hues else None}
 return out
def masks_sheet():
 masks=semantic_masks(ID,ACTIVE);names=list(masks);cw,ch=240,260;out=Image.new("RGBA",(cw*5,ch*2),(35,35,35,255));d=ImageDraw.Draw(out);body=ID.getchannel("A").getbbox();body=(body[0]-30,body[1]-30,body[2]+30,body[3]+30)
 master=Image.open(IN/"hastati-master-3200.png").convert("RGBA")
 for i,name in enumerate(names):
  m=Image.fromarray(np.round(masks[name]*255).astype(np.uint8)).crop(body);m.thumbnail((220,220),Image.Resampling.LANCZOS);cell=Image.new("RGBA",m.size,(255,255,255,255));cell.putalpha(m);out.alpha_composite(cell,((i%5)*cw+(cw-m.width)//2,(i//5)*ch));d.text(((i%5)*cw+4,(i//5)*ch+231),name,fill="white")
 # Explicit full-tunic overlay in the final cell.
 cloth=Image.fromarray(np.round(masks["cloth"]*255).astype(np.uint8));overlay=Image.new("RGBA",master.size,(255,0,0,0));overlay.putalpha(cloth.point(lambda x:round(x*.75)));vis=master.copy();vis.alpha_composite(overlay);vis=vis.crop(body);vis.thumbnail((220,220),Image.Resampling.LANCZOS);out.alpha_composite(vis,(4*240+(240-vis.width)//2,260));d.text((4*240+4,491),"cloth overlay: full E3_tunic",fill="white");out.save(BASE/"hastati-material-masks.png")
def sheet(rows,path,groups,scale4=False):
 leg=decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet']);lines=[]
 for ids in groups:lines.append([("Stock Legionary",leg)]+[(r["id"],r["decoded_x2"]) for r in rows if r["id"] in ids])
 cw,ch=(300,430) if scale4 else (220,180);out=Image.new("RGBA",(cw*max(map(len,lines)),ch*len(lines)),(47,71,48,255));d=ImageDraw.Draw(out)
 for yy,line in enumerate(lines):
  for xx,(name,obj) in enumerate(line):
   b=obj["main"].getchannel("A").getbbox();q=display(obj).crop(b)
   if scale4:q=q.resize((q.width*4,q.height*4),Image.Resampling.NEAREST);q.thumbnail((cw-10,ch-28),Image.Resampling.NEAREST)
   out.alpha_composite(q,(xx*cw+(cw-q.width)//2,yy*ch+2));d.text((xx*cw+4,yy*ch+ch-20),name,fill="white")
 out.save(path)
def resampling_diagnostics():
 rows=[];filters={"bicubic":Image.Resampling.BICUBIC,"lanczos":Image.Resampling.LANCZOS,"hamming":Image.Resampling.HAMMING}
 for size in (800,1600,3200):
  master=Image.open(IN/f"hastati-master-{size}.png").convert("RGBA");finished,_,_,_=finish(master,ID,1.2,False,False,"D00",ACTIVE)
  for name,filt in filters.items():
   body=downsample(finished,400,88,(200,200),filt);empty=Image.new("L",body.size);dummy={"main":body,"shadow":empty,"pc_presence":empty};m=metrics(dummy)
   rows.append({"master":size,"filter":name,"bbox":m["bbox"],"local_contrast":m["local_contrast"],"edge_contrast":m["edge_contrast"],"edge_acutance_p90":m["edge_acutance_p90"],"median_luminance":m["luminance"]["p50"]})
 return rows
def main():
 BASE.mkdir(parents=True,exist_ok=True);G.mkdir(parents=True,exist_ok=True);masks_sheet();ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEX);rows=[]
 for i,(cid,name,kind,size) in enumerate(DEFS):
  uid=3401+i;stem=f"rome2_hastati_finish_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati Finish {cid} {name}",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati Finish {cid} {name}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id;hi,backend=high(kind,size);row={"id":cid,"name":name,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"master_size":size,"backend":backend}
  for z,canvas,logical,hot in (("x1",200,44,(100,100)),("x2",400,88,(200,200))):
   filt=Image.Resampling.LANCZOS;body=downsample(hi,canvas,logical,hot,filt)
   if kind=="b6":body=acutance(body,3)
   shadow=shadow_v2(body,"SH02",hot);pc=None
   if kind=="bestpc":pc,cov=pc_for(body,logical,hot,"shield");row[f"player_coverage_{z}"]=round(cov,4)
   (G/f"{stem}_{z}.sld").write_bytes(serialize_sld(author_identical_facets(body,shadow,16,hot,encoder=enc,player_color=pc)))
   dec=decode(G/f"{stem}_{z}.sld",0);row[f"metrics_{z}"]=metrics(dec)
  row["decoded_x2"]=decode(G/f"{stem}_x2.sld",0);row["materials_x2"]=material_metrics(row["decoded_x2"]);rows.append(row)
 ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Material Finish","Description":"Material-aware color definition experiment."},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));layout=[["SRC","A2","B6"],["CP01","CP02","CP03","CP04"],["CD01","CD02","CD03","CD04"],["SS32","BEST","BESTPC"]];placements=[]
 for rr,ids in enumerate(layout):
  y=36-rr*4;sc.unit_manager.add_unit(player=1,unit_const=1793,x=8,y=y,rotation=0)
  for cc,cid in enumerate(ids,1):r=next(x for x in rows if x["id"]==cid);x=8+cc*4;sc.unit_manager.add_unit(player=1,unit_const=r["unit_id"],x=x,y=y,rotation=0);placements.append({"row":rr,"column":cc,"id":cid,"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"x":x,"y":y})
 sc.write_to_file(str(SCEN));(BASE/"LEGEND.txt").write_text("\n".join(["Hastati material-aware finishing"]+[f"row {p['row']} col {p['column']} ({p['x']},{p['y']}) {p['id']} unit={p['unit_id']} graphic={p['graphic_id']}" for p in placements])+"\n")
 sheet(rows,BASE/"hastati-colour-definition-uhd.png",[["SRC","A2","B6"],["CP01","CP02","CP03","CP04"],["CD01","CD02","CD03","CD04"],["SS32","BEST","BESTPC"]]);sheet(rows,BASE/"hastati-colour-definition-4x.png",[["A2","B6","CP03","CD01","CD02","CD03","CD04","SS32","BEST"]],True)
 serial=[{k:v for k,v in r.items() if k!="decoded_x2"} for r in rows];report={"format":"rome2aoe2.material-aware-finishing","version":1,"candidates":serial,"placements":placements,"resampling":{"R01":"800 -> 400","R02":"1600 -> 400","R03":"3200 -> 400","filters_tested":["Pillow bicubic","Pillow Lanczos","Pillow hamming"],"selected":"Lanczos","measurements":resampling_diagnostics()},"limitations":{"shield_metal":"not separable from shield body by current source material slot","weapon":"wood/metal mixed materials","opencv":"available" if any(r["backend"].get("opencv_available") for r in rows) else "wheel unavailable; deterministic NumPy edge-aware fallback used"},"paths":{"mod":str(MOD),"scenario":str(SCEN),"legend":str(BASE/"LEGEND.txt")}}
 (BASE/"hastati-material-finish-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"count":len(rows),"opencv":report["limitations"]["opencv"]},indent=2))
if __name__=="__main__":raise SystemExit(main())
