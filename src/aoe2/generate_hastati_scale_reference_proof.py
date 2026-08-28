"""Strict x2 scale audit and stock-relative Hastati proof.

All proprietary/generated output stays below ignored build/local-integration.
"""
from __future__ import annotations
import json, math, shutil, statistics, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageChops,ImageDraw,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.aoe_sprite_finish import semantic_masks
from aoe2.generate_hastati_gameplay_finish_proof import aligned,high_variant,raster_detail
from aoe2.generate_hastati_material_finish_proof import high,ACTIVE,ID
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.analyze_aoe_style_uhd import decode,metrics,GRAPHICS,REFS,FACET,BG

BASE=ROOT/"build/local-integration/rome2/hastati-scale-reference"
MOD=BASE/"ROME2AOE2_HASTATI_SCALE_REFERENCE"; G=MOD/"resources/_common/drs/graphics"
MARKER_MOD=BASE/"ROME2AOE2_UHD_SELECTION_MARKER"; MG=MARKER_MOD/"resources/_common/drs/graphics"
DAT=MOD/"resources/_common/dat/empires2_x2_p1.dat"; MARKER_DAT=MARKER_MOD/"resources/_common/dat/empires2_x2_p1.dat"
SCEN=BASE/"Rome2HastatiScaleReference.aoe2scenario"; MARKER_SCEN=BASE/"Rome2UHDSelectionMarker.aoe2scenario"
MASTER=ROOT/"build/local-integration/rome2/material-aware-finishing/inputs/hastati-master-3200.png"
ROME=ROOT/"build/local-integration/rome2/tunic-semantic-color/inputs/tunic-rome-tinted.png"
OLD_BASE=ROOT/"build/local-integration/rome2/hastati-gameplay-finish"
OLD_G=OLD_BASE/"ROME2AOE2_HASTATI_GAMEPLAY_FINISH/resources/_common/drs/graphics"
RATIOS=(("R100",1.00),("R115",1.15),("R125",1.25),("R133",1.33),("R140",1.40))

def strict(path,index):
 if not path.name.endswith("_x2.sld"): raise ValueError(f"strict x2 reference rejected non-x2 path: {path}")
 if not path.is_file(): raise FileNotFoundError(f"required x2 SLD missing; fallback forbidden: {path}")
 return decode(path,index)

def body_bbox(obj):
 b=obj["main"].getchannel("A").getbbox()
 if not b: raise ValueError("empty decoded body")
 return b

def silhouette_diagnostics(obj):
 """Measure perceived scale from the decoded main-layer silhouette.

 A 3x3 morphological opening removes one-pixel feathers/spears before the
 core-top measurement.  Shoulder position is an explicitly approximate,
 reproducible anatomical sample at 28% down the opened core.  Torso width is
 the median central run across that row +/-2, avoiding detached equipment.
 """
 alpha=obj["main"].getchannel("A");mask=alpha.point(lambda v:255 if v>8 else 0)
 full=mask.getbbox()
 if not full:raise ValueError("empty decoded silhouette")
 opened=mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3));core=opened.getbbox() or full
 feet_y=full[3]-1;core_top=core[1];core_h=feet_y-core_top+1
 shoulder_y=min(feet_y,max(core_top,round(core_top+.28*(core_h-1))))
 center_x=obj["doc"].frames[0].center_x
 def central_run(y):
  xs=[x for x in range(mask.width) if opened.getpixel((x,y))]
  if not xs:return 0
  runs=[];a=prev=xs[0]
  for x in xs[1:]:
   if x!=prev+1:runs.append((a,prev+1));a=x
   prev=x
  runs.append((a,prev+1));run=min(runs,key=lambda q:0 if q[0]<=center_x<q[1] else min(abs(center_x-q[0]),abs(center_x-(q[1]-1))))
  return run[1]-run[0]
 widths=[central_run(y) for y in range(max(core_top,shoulder_y-2),min(feet_y+1,shoulder_y+3))];widths=[x for x in widths if x]
 return {"full_opaque_bbox":list(full),"full_opaque_bbox_height":full[3]-full[1],"core_bbox_after_3x3_open":list(core),"feet_y":feet_y,"core_top_y":core_top,"feet_to_core_head_helmet_height":core_h,"shoulder_sample_y":shoulder_y,"feet_to_shoulder_height":feet_y-shoulder_y+1,"torso_shoulder_central_run_width":round(statistics.median(widths)) if widths else 0,"total_silhouette_width":full[2]-full[0]}

def transparent_visual(obj):
 main=obj["main"].convert("RGBA"); sh=obj["shadow"].convert("L")
 out=Image.new("RGBA",main.size); out.alpha_composite(Image.new("RGBA",main.size,(10,14,10,0)))
 shadow=Image.new("RGBA",main.size,(10,14,10,255)); shadow.putalpha(sh); out.alpha_composite(shadow);out.alpha_composite(main)
 return out

def stock_record(key):
 r=REFS[key]; rec={"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"graphic_stem":r["stem"],"frames_per_facet":r["frames_per_facet"]}
 for z in ("x1","x2"):
  p=GRAPHICS/f"{r['stem']}_{z}.sld"
  if not p.is_file(): raise FileNotFoundError(f"required stock {z} SLD missing; fallback forbidden: {p}")
  o=decode(p,FACET*r["frames_per_facet"]);f=o["doc"].frames[FACET*r["frames_per_facet"]];b=body_bbox(o)
  rec[z]={"path":str(p),"canvas":list(o["main"].size),"hotspot":[f.center_x,f.center_y],"body_bbox":list(b),"body_dimensions":[b[2]-b[0],b[3]-b[1]]}
  if z=="x2":rec["perceived_scale_diagnostics_x2"]=silhouette_diagnostics(o)
 return rec

def old_trace(report,stock):
 by={x["id"]:x for x in report["candidates"]}; result=[]
 items=[("Stock Legionary",GRAPHICS/f"{REFS['legionary']['stem']}_x2.sld",FACET*REFS['legionary']['frames_per_facet']),
        ("Stock Man-at-Arms",GRAPHICS/f"{REFS['man-at-arms']['stem']}_x2.sld",FACET*REFS['man-at-arms']['frames_per_facet'])]
 items += [(cid,OLD_G/f"{by[cid]['stem']}_x2.sld",0) for cid in ("S00","S05","S08","S10","S12")]
 for label,p,index in items:
  o=strict(p,index); b=body_bbox(o); canvas=o["main"].size
  # Old display() returned an opaque full canvas. thumbnail((220,152)) then applied.
  factor=min(220/canvas[0],152/canvas[1],1.0); pasted=[round((b[2]-b[0])*factor),round((b[3]-b[1])*factor)]
  result.append({"sprite":label,"sheet":"hastati-gameplay-scale-uhd.png","source_sld":str(p),"source_density":"x2","decoded_canvas":list(canvas),"decoded_body_dimensions":[b[2]-b[0],b[3]-b[1]],"opaque_background_alpha_crop":list(canvas),"resize_factor":factor,"final_pasted_body_dimensions":pasted})
 return result

def render_candidate(ws,enc,cid,target,hi,master,masks):
 stem=f"rome2_hastati_scale_{cid.lower()}"; uid=3650+render_candidate.i;render_candidate.i+=1
 gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati {cid}",frame_count=1,angle_count=16,frame_duration=1)
 u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati {cid}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id
 master_box=master.getchannel("A").getbbox();rec={"id":cid,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"target_x2_body_height":target,"uniform_scaling":True,"source_aspect_ratio_preserved":True,"master_body_bbox":list(master_box)}
 for z,canvas,nominal,hot in (("x1",200,round((target+1)/2),(100,100)),("x2",400,target+1,(200,200))):
  body=aligned(hi,master,canvas,nominal,hot); aux={k:np.asarray(aligned(Image.fromarray(np.round(v*255).astype(np.uint8),"L").convert("RGBA"),master,canvas,nominal,hot).getchannel("R"),np.float32)/255 for k,v in masks.items()}
  body=raster_detail(body,"combined",2,aux); shadow=shadow_v2(body,"SH02",hot); p=G/f"{stem}_{z}.sld"
  p.write_bytes(serialize_sld(author_identical_facets(body,shadow,16,hot,encoder=enc)));o=decode(p,0);b=body_bbox(o);f=o["doc"].frames[0]
  rec[z]={"path":str(p),"canvas":list(o["main"].size),"hotspot":[f.center_x,f.center_y],"body_bbox":list(b),"body_dimensions":[b[2]-b[0],b[3]-b[1]],"facets":len(o["doc"].frames)}
  rec[z]["uniform_source_scale_xy"]=nominal/(master_box[3]-master_box[1])
  if z=="x2":rec["perceived_scale_diagnostics_x2"]=silhouette_diagnostics(o)
 if rec["x2"]["body_dimensions"][1]!=target: raise ValueError(f"{cid}: decoded x2 height {rec['x2']['body_dimensions'][1]} != target {target}")
 return rec
render_candidate.i=0

def sheet(items,path,logical):
 scale=.5 if logical else 1.0; cellw=150 if logical else 260; cellh=150 if logical else 260; ground=115 if logical else 220
 out=Image.new("RGBA",(cellw*len(items),cellh),BG);d=ImageDraw.Draw(out); logs=[]
 for i,(label,p,index,kind) in enumerate(items):
  o=strict(p,index);f=o["doc"].frames[index];b=body_bbox(o);im=transparent_visual(o)
  if logical:im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
  hot=(round(f.center_x*scale),round(f.center_y*scale));x=i*cellw+cellw//2-hot[0];y=ground-hot[1];out.alpha_composite(im,(x,y));d.text((i*cellw+3,cellh-18),label,fill="white")
  pasted=[round((b[2]-b[0])*scale),round((b[3]-b[1])*scale)]
  logs.append({"sprite":label,"kind":kind,"source_sld":str(p),"source_density":"x2","decoded_canvas":list(o["main"].size),"decoded_hotspot":[f.center_x,f.center_y],"decoded_body_bbox":list(b),"decoded_body_dimensions":[b[2]-b[0],b[3]-b[1]],"resize_factor":scale,"final_pasted_body_dimensions":pasted})
 out.save(path);return logs

def marker_body(canvas,hot,color,label):
 im=Image.new("RGBA",(canvas,canvas));d=ImageDraw.Draw(im);x,y=hot
 d.ellipse((x-22,y-70,x+22,y-26),fill=color,outline=(255,255,255,255),width=5);d.rectangle((x-18,y-28,x+18,y),fill=color,outline=(255,255,255,255),width=4);d.text((x-7,y-53),label,fill=(0,0,0,255));return im

def marker_proof(enc):
 ws=GenieWorkspace.load(SOURCE_DAT);stem="rome2_uhd_selection_marker";gr=ws.graphic_manager.add_graphic(stem,name="UHD x1 x2 selection marker",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(3699,74,on_conflict="error",fill_gaps="placeholder");u.name="UHD selection marker";u.standing_sprite_id1=u.standing_sprite_id2=gr.id
 MG.mkdir(parents=True,exist_ok=True)
 for z,canvas,hot,color,label in (("x1",200,(100,100),(255,0,255,255),"X1"),("x2",400,(200,200),(0,255,255,255),"X2")):
  body=marker_body(canvas,hot,color,label);(MG/f"{stem}_{z}.sld").write_bytes(serialize_sld(author_identical_facets(body,None,16,hot,encoder=enc)))
 MARKER_DAT.parent.mkdir(parents=True,exist_ok=True);ws.save(MARKER_DAT);(MARKER_MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 UHD Selection Marker","Description":"MAGENTA=X1; CYAN=X2 diagnostic."},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));sc.unit_manager.add_unit(player=1,unit_const=3699,x=20,y=20,rotation=0);sc.write_to_file(str(MARKER_SCEN))
 return {"unit_id":3699,"graphic_id":gr.id,"stem":stem,"x1_marker":"MAGENTA X1","x2_marker":"CYAN X2","mod":str(MARKER_MOD),"scenario":str(MARKER_SCEN),"result":"manual in-game observation required"}

def main():
 G.mkdir(parents=True,exist_ok=True);stock={k:stock_record(k) for k in ("legionary","man-at-arms","militia")};h=stock["legionary"]["x2"]["body_dimensions"][1]
 targets={cid:round(h*ratio) for cid,ratio in RATIOS};master=Image.open(MASTER).convert("RGBA");rome=Image.open(ROME).convert("RGBA");best,_=high("best",3200);masks=semantic_masks(ID,ACTIVE);hi=high_variant("tunicbest",best,rome,masks["cloth"]);enc=DirectXTexBC1Encoder(TEX)
 ws=GenieWorkspace.load(SOURCE_DAT);rows=[render_candidate(ws,enc,cid,targets[cid],hi,master,masks) for cid,_ in RATIOS]
 old=json.loads((OLD_BASE/"hastati-gameplay-finish-report.json").read_text());f47=next(x for x in old["candidates"] if x["id"]=="F47")
 custom_trace={}
 for cid in ("S00","S08","F47","F48","F48M"):
  r=next(x for x in old["candidates"] if x["id"]==cid);custom_trace[cid]={"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"stem":r["stem"]}
  for z in ("x1","x2"):
   p=OLD_G/f"{r['stem']}_{z}.sld";o=decode(p,0);b=body_bbox(o);f=o["doc"].frames[0];custom_trace[cid][z]={"path":str(p),"canvas":list(o["main"].size),"hotspot":[f.center_x,f.center_y],"body_bbox":list(b),"body_dimensions":[b[2]-b[0],b[3]-b[1]]}
   if z=="x2":custom_trace[cid]["perceived_scale_diagnostics_x2"]=silhouette_diagnostics(o)
 DAT.parent.mkdir(parents=True,exist_ok=True);ws.save(DAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Scale Reference","Description":"Strict stock-relative neutral scale proof."},indent=2)+"\n")
 items=[("Stock Legionary",Path(stock["legionary"]["x2"]["path"]),FACET*REFS["legionary"]["frames_per_facet"],"stock"),("Stock Man-at-Arms",Path(stock["man-at-arms"]["x2"]["path"]),FACET*REFS["man-at-arms"]["frames_per_facet"],"stock")]
 items += [(r["id"],Path(r["x2"]["path"]),0,"custom") for r in rows];items += [("CURRENT_F47",Path(custom_trace["F47"]["x2"]["path"]),0,"custom-existing")]
 native=sheet(items,BASE/"scale-reference-NATIVE-X2.png",False);logical=sheet(items,BASE/"scale-reference-LOGICAL-GAME.png",True)
 for a,b in zip(native,logical):
  if a["sprite"]!=b["sprite"] or b["resize_factor"]!=.5:raise ValueError("logical normalization mismatch")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));placements=[]
 seq=[("Stock Legionary",1793,None),("Stock Man-at-Arms",75,None)]+[(r["id"],r["unit_id"],r["graphic_id"]) for r in rows]+[("CURRENT_F47",f47["unit_id"],f47["graphic_id"])]
 # F47 must be present in this DAT/mod too.
 fg=ws.graphic_manager.add_graphic(f47["stem"],name="Current F47",frame_count=1,angle_count=16,frame_duration=1);fu=ws.unit_manager.clone_into(f47["unit_id"],74,on_conflict="replace",fill_gaps="placeholder");fu.name="Current F47";fu.standing_sprite_id1=fu.standing_sprite_id2=fg.id;shutil.copy2(custom_trace["F47"]["x1"]["path"],G/Path(custom_trace["F47"]["x1"]["path"]).name);shutil.copy2(custom_trace["F47"]["x2"]["path"],G/Path(custom_trace["F47"]["x2"]["path"]).name);ws.save(DAT)
 seq[-1]=("CURRENT_F47",f47["unit_id"],fg.id)
 for i,(label,uid,gid) in enumerate(seq):x=12+i*2.4;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=24,rotation=0);placements.append({"label":label,"unit_id":uid,"graphic_id":gid,"x":x,"y":24})
 sc.write_to_file(str(SCEN));marker=marker_proof(enc);trace=old_trace(old,stock)
 report={"format":"rome2aoe2.strict-scale-reference","version":2,"fixed_recipe":{"composition":"unchanged runtime-resolved representative","lighting":"L11","shadow":"SH02","tunic":"tunicbest semantic protection","detail":"combined level 2","player_color":"none"},"perceived_scale_method":{"purpose":"diagnostic only; never changes candidate targets","core":"decoded x2 alpha>8 followed by 3x3 morphological opening to suppress thin protrusions","shoulder":"reproducible approximate sample 28% down opened core","torso_width":"median central connected run across shoulder row +/-2","feet":"bottom opaque row of original decoded silhouette","limitation":"algorithmic silhouette estimates, not semantic anatomy; in-game comparison remains authoritative"},"stock":stock,"custom_existing":custom_trace,"old_sheet_trace":trace,"old_sheet_root_cause":"display() composites an opaque background before alpha crop, so crop is the whole canvas; thumbnail scales 200x200 Legionary x2 by 0.76 and 400x400 Man-at-Arms/custom x2 by 0.38","H_stock_x2":h,"targets_x2_body_height":targets,"candidates":rows,"native_x2_composition":native,"logical_game_composition":logical,"logical_rule":"all actual x2 sources resized uniformly by 0.5","placements":placements,"uhd_marker_proof":marker,"paths":{"mod":str(MOD),"scenario":str(SCEN),"native_x2":str(BASE/"scale-reference-NATIVE-X2.png"),"logical_game":str(BASE/"scale-reference-LOGICAL-GAME.png")}}
 (BASE/"hastati-scale-reference-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"H_stock_x2":h,"targets":targets,"mod":str(MOD),"scenario":str(SCEN)},indent=2))
if __name__=="__main__":raise SystemExit(main())
