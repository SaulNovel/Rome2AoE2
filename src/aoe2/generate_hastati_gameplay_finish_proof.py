"""Bounded gameplay-scale Hastati color/definition calibration."""
from __future__ import annotations
import json,math,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.aoe_sprite_finish import rgba,rgb_oklab,oklab_rgb,image,semantic_hue_restore,semantic_masks,boundary_finish,luminance_detail
from aoe2.generate_hastati_material_finish_proof import high,ACTIVE,ID
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.generate_hastati_v3_proof import pc_for
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,GRAPHICS,REFS,FACET

BASE=ROOT/"build/local-integration/rome2/hastati-gameplay-finish";IN=BASE/"inputs";MOD=BASE/"ROME2AOE2_HASTATI_GAMEPLAY_FINISH";G=MOD/"resources/_common/drs/graphics"
DAT=BASE/"hastati_gameplay_finish.dat";MODDAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2HastatiGameplayFinish.aoe2scenario"
MASTER=ROOT/"build/local-integration/rome2/material-aware-finishing/inputs/hastati-master-3200.png";ROME=ROOT/"build/local-integration/rome2/tunic-semantic-color/inputs/tunic-rome-tinted.png"
SCALES=[("S00","Current 44px",44),("S05","+5% 46px",46),("S08","+8% 47px",47),("S10","+10% 48px",48),("S12","+12% 49px",49)]
TONES=[("T0","BEST baseline","base"),("T1","Full semantic","semantic"),("T2","Semantic + small chroma","chroma"),("T3","Semantic + cloth local contrast","clothdetail"),("T4","Reduction-aware semantic","reduction"),("T5","Combined tunic protection","tunicbest")]
DETAIL=[("L1","Local mild","local",1),("L2","Local medium","local",2),("L3","Local upper","local",3),("A1","Acutance mild","sharp",1),("A2","Acutance medium","sharp",2),("A3","Acutance upper","sharp",3),("C1","Combined mild","combined",1),("C2","Combined medium","combined",2),("C3","Combined upper","combined",3),("M1","Material boundaries mild","boundary",1),("M2","Material boundaries medium","boundary",2)]
PCS=[("PC0","No player color",None),("PC1","Shield only","shield"),("PC2","Shield tiny accent","tiny"),("PC3","Restrained accent upper","moderate")]

def aligned(im,reference,canvas,logical,hot,filter=Image.Resampling.LANCZOS):
 """Apply reference body's crop/scale/feet transform to an auxiliary pass."""
 box=reference.getchannel("A").getbbox();scale=logical/(box[3]-box[1]);size=(max(1,round((box[2]-box[0])*scale)),logical)
 q=im.crop(box).resize(size,filter);feet=(reference.width/2-box[0],reference.height/2-box[1]);out=Image.new("RGBA",(canvas,canvas));out.alpha_composite(q,(round(hot[0]-feet[0]*scale),round(hot[1]-feet[1]*scale)));return out

def cloth_detail(im,mask,amount=.10,radius=18):
 a=rgba(im);lab=rgb_oklab(a[...,:3]);L=lab[...,0];blur=np.asarray(Image.fromarray(np.round(L*255).astype(np.uint8),"L").filter(ImageFilter.GaussianBlur(radius)),np.float32)/255
 changed=lab.copy();changed[...,0]=np.clip(L+(L-blur)*amount,0,1);rgb=oklab_rgb(changed);w=mask[...,None];return image(a[...,:3]*(1-w)+rgb*w,a[...,3])

def raster_detail(im,kind,level,masks):
 if not kind:return im
 a=rgba(im);lab=rgb_oklab(a[...,:3]);z=im.width/400
 if kind in ("local","combined"):
  L=lab[...,0];radius=max(.5,(2.4-0.35*level)*z);blur=np.asarray(Image.fromarray(np.round(L*255).astype(np.uint8),"L").filter(ImageFilter.GaussianBlur(radius)),np.float32)/255;amt=(.08,.14,.20)[level-1];lab[...,0]=np.clip(L+(L-blur)*amt,0,1)
 if kind in ("sharp","combined"):
  L=lab[...,0];radius=max(.45,1.0*z);blur=np.asarray(Image.fromarray(np.round(L*255).astype(np.uint8),"L").filter(ImageFilter.GaussianBlur(radius)),np.float32)/255;amt=(.07,.12,.18)[level-1];lab[...,0]=np.clip(L+(L-blur)*amt,0,1)
 if kind=="boundary":lab,_=boundary_finish(lab,masks,(.006,.010)[level-1])
 return image(oklab_rgb(lab),a[...,3])

def tunic_stats(im,mask):
 a=rgba(im);lab=rgb_oklab(a[...,:3]);w=mask*a[...,3];sel=w>.03
 if not np.any(sel):return {"pixels":0}
 aa=lab[...,1][sel];bb=lab[...,2][sel];ww=w[sel];L=lab[...,0][sel];angle=np.arctan2(bb,aa);x=np.average(np.cos(angle),weights=ww);y=np.average(np.sin(angle),weights=ww)
 return {"pixels":int(sel.sum()),"hue_degrees":round(math.degrees(math.atan2(y,x))%360,3),"chroma":round(float(np.average(np.hypot(aa,bb),weights=ww)),5),"luminance_p50":round(float(np.median(L)),5)}

def high_variant(kind,best,rome,cloth):
 if kind=="base":return best
 q=semantic_hue_restore(best,rome,cloth,1,1.04 if kind in ("chroma","tunicbest") else 1)
 if kind in ("clothdetail","tunicbest"):q=cloth_detail(q,cloth,.08 if kind=="clothdetail" else .10)
 return q

def render_candidate(spec,best,rome,master,masks_hi,enc):
 cid,name,logical,tkind,dkind,dlevel,pc_kind=spec;hi=high_variant(tkind,best,rome,masks_hi["cloth"]);row={"id":cid,"name":name,"logical_height":logical,"tunic":tkind,"detail":dkind,"detail_level":dlevel,"player_support":pc_kind}
 uid=3601+render_candidate.index;render_candidate.index+=1;stem=f"rome2_hastati_gameplay_{cid.lower()}";row.update(unit_id=uid,stem=stem)
 gr=render_candidate.ws.graphic_manager.add_graphic(stem,name=f"Hastati {cid} {name}",frame_count=1,angle_count=16,frame_duration=1);row["graphic_id"]=gr.id;u=render_candidate.ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati {cid} {name}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id
 for z,canvas,lh,hot in (("x1",200,logical,(100,100)),("x2",400,logical*2,(200,200))):
  body=aligned(hi,master,canvas,lh,hot);aux={k:np.asarray(aligned(Image.fromarray(np.round(v*255).astype(np.uint8),"L").convert("RGBA"),master,canvas,lh,hot).getchannel("R"),np.float32)/255 for k,v in masks_hi.items()}
  if tkind in ("reduction","tunicbest"):
   rr=aligned(rome,master,canvas,lh,hot);body=semantic_hue_restore(body,rr,aux["cloth"],.35 if tkind=="reduction" else .45,1.03 if tkind=="tunicbest" else 1)
  body=raster_detail(body,dkind,dlevel,aux);shadow=shadow_v2(body,"SH02",hot);pc=None
  if pc_kind:pc,cov=pc_for(body,lh,hot,pc_kind);row[f"player_coverage_{z}"]=round(cov,4)
  path=G/f"{stem}_{z}.sld";path.write_bytes(serialize_sld(author_identical_facets(body,shadow,16,hot,encoder=enc,player_color=pc)));dec=decode(path,0);row[f"metrics_{z}"]=metrics(dec);row[f"tunic_{z}"]=tunic_stats(dec["main"],aux["cloth"])
  if z=="x2":row["decoded_x2"]=dec
 return row
render_candidate.index=0

def sheet(rows,path,groups,pixels=False):
 refs=[("Stock Legionary",decode(GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet'])),("Stock Man-at-Arms",decode(GRAPHICS/f"{REFS['man-at-arms']['stem']}_x2.sld",FACET*REFS['man-at-arms']['frames_per_facet']))]
 cw,ch=(310,410) if pixels else (230,180);out=Image.new("RGBA",(cw*(max(len(g) for g in groups)+2),ch*len(groups)),(47,71,48,255));d=ImageDraw.Draw(out)
 for y,g in enumerate(groups):
  items=refs+[(cid,next(r for r in rows if r["id"]==cid)["decoded_x2"]) for cid in g]
  for x,(label,obj) in enumerate(items):
   q=display(obj);b=q.getchannel("A").getbbox();q=q.crop(b)
   if pixels:q=q.resize((q.width*4,q.height*4),Image.Resampling.NEAREST)
   q.thumbnail((cw-10,ch-28),Image.Resampling.NEAREST if pixels else Image.Resampling.LANCZOS);out.alpha_composite(q,(x*cw+(cw-q.width)//2,y*ch+2));d.text((x*cw+4,y*ch+ch-20),label,fill="white")
 out.save(path)

def main():
 BASE.mkdir(parents=True,exist_ok=True);IN.mkdir(parents=True,exist_ok=True);G.mkdir(parents=True,exist_ok=True);master=Image.open(MASTER).convert("RGBA");rome=Image.open(ROME).convert("RGBA");best,_=high("best",3200);masks=semantic_masks(ID,ACTIVE)
 specs=[]
 specs += [(cid,name,logical,"semantic",None,0,None) for cid,name,logical in SCALES]
 specs += [(cid,name,44,kind,None,0,None) for cid,name,kind in TONES]
 specs += [(cid,name,44,"tunicbest",kind,level,None) for cid,name,kind,level in DETAIL]
 # Evidence-based neutral finalists, including the requested +8/+10 region.
 specs += [("F47","Balanced +8%",47,"tunicbest","combined",2,None),("F48","Balanced +10%",48,"tunicbest","combined",2,None),("F48M","Boundary +10%",48,"tunicbest","boundary",1,None)]
 specs += [(cid,name,47,"tunicbest","combined",2,pc) for cid,name,pc in PCS]
 render_candidate.ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEX);rows=[render_candidate(s,best,rome,master,masks,enc) for s in specs]
 render_candidate.ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Gameplay Finish","Description":"Bounded scale, tunic preservation, definition, and restrained player-color proof."},indent=2)+"\n")
 groups={"scale":[x[0] for x in SCALES],"tunic":[x[0] for x in TONES],"detail":["L1","L2","L3","A1","A2","A3"],"combined":["C1","C2","C3","M1","M2","F47","F48","F48M"],"player":[x[0] for x in PCS]}
 sheet(rows,BASE/"hastati-gameplay-neutral-uhd.png",[groups["tunic"],groups["detail"],groups["combined"]]);sheet(rows,BASE/"hastati-gameplay-scale-uhd.png",[groups["scale"]]);sheet(rows,BASE/"hastati-gameplay-playercolor-uhd.png",[groups["player"]]);sheet(rows,BASE/"hastati-gameplay-4x.png",[["T0","T4","T5","C1","C2","F47","F48","F48M","PC1"]],True);sheet(rows,BASE/"hastati-gameplay-ingame-sheet.png",[["F47","F48","F48M","PC0","PC1","PC2","PC3"]])
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));layout=[groups["scale"],groups["tunic"],groups["detail"],groups["combined"],groups["player"]];placements=[]
 for rr,ids in enumerate(layout):
  y=38-rr*4
  for rx,uid,label in ((8,1793,"Stock Legionary"),(12,75,"Stock Man-at-Arms")):sc.unit_manager.add_unit(player=1,unit_const=uid,x=rx,y=y,rotation=0);placements.append({"row":rr,"id":label,"unit_id":uid,"x":rx,"y":y})
  for cc,cid in enumerate(ids):r=next(x for x in rows if x["id"]==cid);x=16+cc*3;sc.unit_manager.add_unit(player=1,unit_const=r["unit_id"],x=x,y=y,rotation=0);placements.append({"row":rr,"id":cid,"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"x":x,"y":y})
 sc.write_to_file(str(SCEN));(BASE/"LEGEND.txt").write_text("\n".join(f"row {p['row']} | {p['id']} | unit {p['unit_id']} | ({p['x']},{p['y']})" for p in placements)+"\n")
 serial=[{k:v for k,v in r.items() if k!="decoded_x2"} for r in rows];report={"format":"rome2aoe2.hastati-gameplay-finish","version":1,"fixed":{"composition":"runtime-resolved deterministic representative","materials":"unchanged","textures":"unchanged","lighting":"L11","shadow":"SH02","semantic_masks":"body-transform aligned with continuous AA","x1_x2":"independent from 3200 master"},"candidate_groups":groups,"candidates":serial,"placements":placements,"recommendation":{"neutral":"F47","player_color":"PC1","provisional":"Metrics-informed; manual in-game selection is authoritative."},"paths":{"mod":str(MOD),"scenario":str(SCEN),"legend":str(BASE/"LEGEND.txt")}}
 (BASE/"hastati-gameplay-finish-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"candidates":len(rows),"mod":str(MOD),"scenario":str(SCEN)},indent=2))
if __name__=="__main__":raise SystemExit(main())
