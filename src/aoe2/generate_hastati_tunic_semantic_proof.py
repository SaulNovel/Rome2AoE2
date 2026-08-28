"""Focused E3_tunic semantic hue restoration proof (R00--R05)."""
from __future__ import annotations
import json,math,shutil,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageDraw,ImageChops
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.aoe_sprite_finish import rgba,rgb_oklab,semantic_hue_restore,semantic_masks,resize_mask
from aoe2.generate_hastati_material_finish_proof import high,downsample,ACTIVE,ID
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.generate_hastati_v3_proof import pc_for
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,GRAPHICS,REFS,FACET

BASE=ROOT/"build/local-integration/rome2/tunic-semantic-color";IN=BASE/"inputs"
MOD=BASE/"ROME2AOE2_HASTATI_TUNIC_SEMANTIC";G=MOD/"resources/_common/drs/graphics"
DAT=BASE/"hastati_tunic_semantic.dat";MODDAT=MOD/"resources/_common/dat/empires2_x2_p1.dat"
SCEN=BASE/"Rome2HastatiTunicSemantic.aoe2scenario"
DEFS=[("R00","BEST control",0,1),(
 "R01","50% semantic hue",.50,1),("R02","70% semantic hue",.70,1),
 ("R03","85% semantic hue",.85,1),("R04","100% semantic hue",1,1),
 ("R05","100% semantic hue +10% chroma",1,1.10)]

def weighted_stats(im,mask):
 a=rgba(im);lab=rgb_oklab(a[...,:3]);w=np.clip(mask,0,1)*a[...,3];sel=w>.02
 if not np.any(sel):return {"pixels":0}
 ww=w[sel];L=lab[...,0][sel];aa=lab[...,1][sel];bb=lab[...,2][sel];ch=np.hypot(aa,bb);ang=np.arctan2(bb,aa)
 def wp(v,p):
  o=np.argsort(v);v=v[o];q=ww[o];return float(v[np.searchsorted(np.cumsum(q),p*q.sum())])
 x=float(np.sum(np.cos(ang)*ww)/ww.sum());y=float(np.sum(np.sin(ang)*ww)/ww.sum())
 return {"pixels":int(sel.sum()),"hue_degrees":round(math.degrees(math.atan2(y,x))%360,3),
  "oklab_a":round(float(np.average(aa,weights=ww)),5),"oklab_b":round(float(np.average(bb,weights=ww)),5),
  "chroma":round(float(np.average(ch,weights=ww)),5),"luminance_p25":round(wp(L,.25),5),
  "luminance_p50":round(wp(L,.5),5),"luminance_p75":round(wp(L,.75),5)}

def fit_mask(mask,canvas,logical,hot):
 q=Image.fromarray(np.round(mask*255).astype(np.uint8),"L");r=Image.merge("RGBA",(q,q,q,q))
 return np.asarray(downsample(r,canvas,logical,hot,Image.Resampling.LANCZOS).getchannel("R"),np.float32)/255

def crop_stage(im,mask,size=(260,250)):
 m=Image.fromarray(np.round(mask*255).astype(np.uint8),"L");b=m.getbbox()
 if not b:return Image.new("RGBA",size)
 pad=max(4,(b[3]-b[1])//12);b=(max(0,b[0]-pad),max(0,b[1]-pad),min(im.width,b[2]+pad),min(im.height,b[3]+pad))
 q=im.crop(b);q.thumbnail(size,Image.Resampling.LANCZOS);return q

def contact(rows,path,pixel4=False):
 leg=decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet'])
 cloth=semantic_masks(ID,ACTIVE)["cloth"];diag=Image.new("RGBA",ID.size,(255,0,0,0));diag.putalpha(Image.fromarray(np.round(cloth*255).astype(np.uint8),"L"))
 items=[("Stock Legionary",display(leg))]+[(r["id"],display(r["decoded_x2"])) for r in rows]+[("E3_tunic mask",diag)]
 cw,ch=(330,430) if pixel4 else (260,250);out=Image.new("RGBA",(cw*4,ch*2),(47,71,48,255));d=ImageDraw.Draw(out)
 for i,(name,im) in enumerate(items):
  if name=="E3_tunic mask":q=crop_stage(im,cloth,(cw-14,ch-32))
  else:
   b=im.getchannel("A").getbbox();q=im.crop(b) if b else im
   if pixel4:q=q.resize((q.width*4,q.height*4),Image.Resampling.NEAREST)
   q.thumbnail((cw-14,ch-32),Image.Resampling.NEAREST if pixel4 else Image.Resampling.LANCZOS)
  x=(i%4)*cw+(cw-q.width)//2;y=(i//4)*ch+4;out.alpha_composite(q,(x,y));d.text(((i%4)*cw+5,(i//4)*ch+ch-22),name,fill="white")
 out.save(path)

def pipeline_sheet(stages):
 cw,ch=280,280;out=Image.new("RGBA",(cw*4,ch*2),(38,38,38,255));d=ImageDraw.Draw(out)
 for i,(name,im,mask) in enumerate(stages):
  q=crop_stage(im,mask,(cw-14,ch-34));out.alpha_composite(q,((i%4)*cw+(cw-q.width)//2,(i//4)*ch+4));d.text(((i%4)*cw+4,(i//4)*ch+ch-24),name,fill="white")
 out.save(BASE/"hastati-tunic-color-pipeline.png")

def main():
 BASE.mkdir(parents=True,exist_ok=True);G.mkdir(parents=True,exist_ok=True)
 best,backend=high("best",3200);rome=Image.open(IN/"tunic-rome-tinted.png").convert("RGBA");raw=Image.open(IN/"tunic-raw-diffuse.png").convert("RGBA");maskrgb=Image.open(IN/"tunic-mask-rgb.png").convert("RGBA")
 cloth=semantic_masks(ID,ACTIVE)["cloth"];source=Image.open(ROOT/"build/local-integration/rome2/material-aware-finishing/inputs/hastati-master-3200.png").convert("RGBA")
 ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEX);rows=[]
 for i,(cid,name,strength,chroma) in enumerate(DEFS):
  hi=best if cid=="R00" else semantic_hue_restore(best,rome,cloth,strength,chroma)
  uid=3501+i;stem=f"rome2_hastati_tunic_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati {cid} {name}",frame_count=1,angle_count=16,frame_duration=1)
  u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati {cid} {name}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id
  row={"id":cid,"name":name,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"semantic_strength":strength,"semantic_chroma_scale":chroma,"backend":backend}
  for z,canvas,logical,hot in (("x1",200,44,(100,100)),("x2",400,88,(200,200))):
   body=downsample(hi,canvas,logical,hot,Image.Resampling.LANCZOS);shadow=shadow_v2(body,"SH02",hot)
   if z=="x2":body.save(IN/f"{cid}-x2-pre-sld.png")
   (G/f"{stem}_{z}.sld").write_bytes(serialize_sld(author_identical_facets(body,shadow,16,hot,encoder=enc)))
   dec=decode(G/f"{stem}_{z}.sld",0);cm=fit_mask(cloth,canvas,logical,hot);row[f"metrics_{z}"]=metrics(dec);row[f"tunic_{z}"]=weighted_stats(dec["main"],cm)
  row["decoded_x2"]=decode(G/f"{stem}_x2.sld",0);rows.append(row)
 ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT)
 (MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Tunic Semantic Color","Description":"Focused E3_tunic semantic hue restoration proof."},indent=2)+"\n")
 # Tiny one-row proof: stock Legionary immediately beside R00--R05.
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));placements=[];y=32
 sc.unit_manager.add_unit(player=1,unit_const=1793,x=8,y=y,rotation=0);placements.append({"id":"Stock Legionary","unit_id":1793,"x":8,"y":y})
 for i,r in enumerate(rows,1):x=8+i*3;sc.unit_manager.add_unit(player=1,unit_const=r["unit_id"],x=x,y=y,rotation=0);placements.append({"id":r["id"],"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"x":x,"y":y})
 sc.write_to_file(str(SCEN));(BASE/"LEGEND.txt").write_text("\n".join(f"{p['id']} | unit {p['unit_id']} | ({p['x']},{p['y']})" for p in placements)+"\n")
 contact(rows,BASE/"hastati-tunic-semantic-color-uhd.png");contact(rows,BASE/"hastati-tunic-semantic-color-4x.png",True)
 cm400=fit_mask(cloth,400,88,(200,200));r04=next(r for r in rows if r["id"]=="R04")
 stages=[("A raw diffuse",raw,cloth),("B Rome tint",rome,cloth),("C Blender pre-finish",source,cloth),("D BEST high-res",best,cloth),("E R04 x2 pre-SLD",Image.open(IN/"R04-x2-pre-sld.png").convert("RGBA"),cm400),("F R04 decoded x2",r04["decoded_x2"]["main"],cm400)]
 pipeline_sheet(stages)
 stage_metrics={n:weighted_stats(im,m) for n,im,m in stages};ma=rgba(maskrgb)[...,:3];sel=cloth>.02
 channel={c:{"mean":round(float(np.average(ma[...,i][sel],weights=cloth[sel])),5),"p50":round(float(np.median(ma[...,i][sel])),5),"coverage_gt_0_1_percent":round(float(100*np.mean(ma[...,i][sel]>.1)),3)} for i,c in enumerate("RGB")}
 trace=json.loads((IN/"trace.json").read_text());serial=[{k:v for k,v in r.items() if k!="decoded_x2"} for r in rows]
 report={"format":"rome2aoe2.hastati-tunic-semantic-color","version":1,"source_trace":trace,"mask_channel_measurements":channel,"pipeline_stages":stage_metrics,"candidates":serial,"placements":placements,"fixed":{"composition":"runtime-resolved deterministic representative","lighting":"L11 unchanged","logical_height":44,"shadow":"SH02 unchanged","player_color":"none in R00-R05; shield-only policy unchanged","grading":"BEST luminance/detail unchanged"},"paths":{"mod":str(MOD),"scenario":str(SCEN),"legend":str(BASE/"LEGEND.txt")}}
 (BASE/"hastati-tunic-semantic-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"candidates":len(rows),"channel":channel,"scenario":str(SCEN)},indent=2))
if __name__=="__main__":raise SystemExit(main())
