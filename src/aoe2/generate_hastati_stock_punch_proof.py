"""Semantic stock-punch finishing, metrics, SLDs, sheets, and compact proof."""
from __future__ import annotations
import hashlib,json,shutil,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageChops,ImageDraw,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld,parse_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.aoe_sprite_finish import rgba,rgb_oklab,oklab_rgb,image,semantic_masks,boundary_finish
from aoe2.generate_hastati_gameplay_finish_proof import aligned
from aoe2.generate_hastati_material_finish_proof import ACTIVE,ID
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,GRAPHICS,FACET,BG
BASE=ROOT/"build/local-integration/rome2/hastati-stock-punch";MASTER=BASE/"masters";PRE=BASE/"x2-pre-sld";DEC=BASE/"decoded-x2";DIAG=BASE/"diagnostic-sld";MOD=BASE/"ROME2AOE2_HASTATI_STOCK_PUNCH";G=MOD/"resources/_common/drs/graphics";DAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2HastatiStockPunch.aoe2scenario"
MASKS=semantic_masks(ID,ACTIVE);IDS=[f"A{i}" for i in range(10)]+[f"B{i}" for i in range(8)]+[f"C{i}" for i in range(9)]+[f"D{i}" for i in range(3)];FINALS=[f"P{i}" for i in range(8)]
FINAL_SOURCE={"P0":"A0","P1":"A9","P2":"B7","P3":"C3","P4":"C4","P5":"C7","P6":"C8","P7":"D1"}
def mask_canvas(name,ref,canvas,nominal,hot):
 m=Image.fromarray(np.round(MASKS[name]*255).astype(np.uint8),"L").convert("RGBA");return np.asarray(aligned(m,ref,canvas,nominal,hot).getchannel("R"),np.float32)/255
def base_x2(name):
 ref=Image.open(MASTER/f"{name}.png").convert("RGBA");return aligned(ref,ref,400,106,(200,200)),ref
def semantic_finish(im,kind,level=1):
 canvas=im.width;nominal=106 if canvas==400 else 53;hot=(canvas//2,canvas//2);ref=Image.open(MASTER/"B7.png").convert("RGBA");a=rgba(im);lab=rgb_oklab(a[...,:3]);cloth=mask_canvas("cloth",ref,canvas,nominal,hot);bronze=mask_canvas("bronze",ref,canvas,nominal,hot);allm=np.maximum.reduce([mask_canvas(x,ref,canvas,nominal,hot) for x in ("cloth","bronze","skin","shield body","leather")]);L=lab[...,0].copy()
 if kind in ("local","combined"):
  blur=np.asarray(Image.fromarray(np.round(L*255).astype(np.uint8),"L").filter(ImageFilter.GaussianBlur(1.5)),np.float32)/255;amt=.12 if level==1 else .20;lab[...,0]=np.clip(L+(L-blur)*amt*allm,0,1)
 if kind in ("cloth","combined","remap"):
  factor=1.10 if kind!="remap" else (1.08,.12+1,.16+1)[level-1];lab[...,1]=lab[...,1]*(1-cloth)+lab[...,1]*factor*cloth;lab[...,2]=lab[...,2]*(1-cloth)+lab[...,2]*factor*cloth
 if kind in ("bronze","combined","remap"):
  strength=.55 if level==1 else .75;hi=np.clip((lab[...,0]-.42)/.35,0,1);target=np.clip(lab[...,0]+.055*hi-.025*(1-hi),0,1);lab[...,0]=lab[...,0]*(1-bronze*strength)+target*bronze*strength;warm=(.035,.045);lab[...,1]+=warm[0]*bronze*(.35 if kind=="combined" else .22);lab[...,2]+=warm[1]*bronze*(.35 if kind=="combined" else .22)
 if kind in ("floor","combined"):
  sem=np.maximum(cloth,bronze);dark=np.clip((.30-lab[...,0])/.18,0,1)*sem;lab[...,1]*=(1+.10*dark);lab[...,2]*=(1+.10*dark)
 if kind=="boundary":lab,_=boundary_finish(lab,{"cloth":cloth,"bronze":bronze},.008 if level==1 else .013)
 return image(oklab_rgb(lab),a[...,3])
def build_images():
 imgs={}
 for n in [f"A{i}" for i in range(10)]+[f"B{i}" for i in range(8)]:imgs[n]=base_x2(n)[0]
 base=imgs["B7"];imgs.update(C0=base,C1=semantic_finish(base,"local"),C2=base.filter(ImageFilter.UnsharpMask(radius=.8,percent=28,threshold=3)),C3=semantic_finish(base,"cloth"),C4=semantic_finish(base,"bronze"),C5=semantic_finish(base,"floor"),C6=semantic_finish(base,"boundary"),C7=semantic_finish(base,"combined",1),C8=semantic_finish(base,"combined",2))
 imgs["D0"]=semantic_finish(base,"remap",1);imgs["D1"]=semantic_finish(base,"remap",2);imgs["D2"]=semantic_finish(base,"remap",3)
 for p,s in FINAL_SOURCE.items():imgs[p]=imgs[s]
 return imgs
def region_stats(im,mask):
 a=rgba(im);lab=rgb_oklab(a[...,:3]);sel=(mask*a[...,3])>.03
 if not np.any(sel):return {"pixels":0}
 L=lab[...,0][sel];aa=lab[...,1][sel];bb=lab[...,2][sel];ch=np.hypot(aa,bb);return {"pixels":int(sel.sum()),"L10":round(float(np.quantile(L,.1)),5),"L50":round(float(np.median(L)),5),"L90":round(float(np.quantile(L,.9)),5),"chroma":round(float(np.mean(ch)),5),"hue":round(float(np.degrees(np.arctan2(np.mean(bb),np.mean(aa)))%360),3)}
def stock(uid):
 ws=GenieWorkspace.load(SOURCE_DAT);u=ws.unit_manager.get(uid);gr=ws.graphic_manager.get(u.standing_sprite_id1);return decode(GRAPHICS/f"{gr.file_name[:-3]}_x2.sld",FACET*gr.frame_count)
def contact(path,groups,objects,pixels=False):
 cw,ch=180,190;cols=max(len(x) for x in groups);out=Image.new("RGBA",(cols*cw,len(groups)*ch),BG);d=ImageDraw.Draw(out)
 for y,line in enumerate(groups):
  for x,label in enumerate(line):
   o=objects[label];b=o["main"].getchannel("A").getbbox();q=display(o).crop(b)
   if pixels:q=q.resize((q.width*4,q.height*4),Image.Resampling.NEAREST)
   q.thumbnail((cw-8,ch-28),Image.Resampling.NEAREST if pixels else Image.Resampling.LANCZOS);out.alpha_composite(q,(x*cw+(cw-q.width)//2,y*ch+2));d.text((x*cw+3,y*ch+ch-18),label,fill="white")
 out.save(path)
def main():
 for p in (PRE,DEC,DIAG,G):p.mkdir(parents=True,exist_ok=True)
 imgs=build_images();enc=DirectXTexBC1Encoder(TEX);objects={};rows={};ref=Image.open(MASTER/"B7.png").convert("RGBA");cm={x:mask_canvas(x,ref,400,106,(200,200)) for x in ("cloth","bronze")}
 for cid in IDS+FINALS:
  body=imgs[cid];body.save(PRE/f"{cid}.png");shadow=shadow_v2(body,"SH02",(200,200));p=DIAG/f"{cid}_x2.sld";p.write_bytes(serialize_sld(author_identical_facets(body,shadow,16,(200,200),encoder=enc)));o=decode(p,0);objects[cid]=o;o["main"].save(DEC/f"{cid}.png");m=metrics(o);rows[cid]={"id":cid,"source":FINAL_SOURCE.get(cid,cid),"metrics":m,"cloth":region_stats(o["main"],cm["cloth"]),"bronze":region_stats(o["main"],cm["bronze"]),"source_sld":str(p)}
 ws=GenieWorkspace.load(SOURCE_DAT);units=[]
 for i,cid in enumerate(FINALS):
  uid=3721+i;stem=f"rome2_hastati_punch_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati Punch {cid}",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati Punch {cid}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id
  for z,canvas,nominal,hot in (("x1",200,53,(100,100)),("x2",400,106,(200,200))):
   if z=="x2":body=imgs[cid]
   else:
    src=Image.open(MASTER/f"{FINAL_SOURCE[cid]}.png").convert("RGBA") if FINAL_SOURCE[cid][0] in "AB" else Image.open(MASTER/"B7.png").convert("RGBA");body=aligned(src,src,canvas,nominal,hot)
    # Final semantic transformations are independently applied after x1 reduction.
    if FINAL_SOURCE[cid][0] in "CD":
     kind={"C3":"cloth","C4":"bronze","C7":"combined","C8":"combined","D1":"remap"}[FINAL_SOURCE[cid]];body=semantic_finish(body,kind,2 if FINAL_SOURCE[cid] in ("C8","D1") else 1)
   sh=shadow_v2(body,"SH02",hot);path=G/f"{stem}_{z}.sld";path.write_bytes(serialize_sld(author_identical_facets(body,sh,16,hot,encoder=enc)))
  units.append({"id":cid,"unit_id":uid,"graphic_id":gr.id,"stem":stem})
 DAT.parent.mkdir(parents=True,exist_ok=True);ws.save(DAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Stock Punch","Description":"Fixed-R133 stock-punch investigation."},indent=2)+"\n")
 leg=stock(1793);broad=stock(76);maa=stock(75);objects.update({"Stock Legionary":leg,"Stock Broad Sword":broad,"Stock Man-at-Arms":maa})
 contact(BASE/"lighting-only-sheet.png",[["Stock Legionary"]+[f"A{i}" for i in range(5)],["Stock Legionary"]+[f"A{i}" for i in range(5,10)]],objects)
 contact(BASE/"material-only-sheet.png",[["Stock Broad Sword"]+[f"B{i}" for i in range(4)],["Stock Legionary"]+[f"B{i}" for i in range(4,8)]],objects)
 contact(BASE/"combined-finalists-sheet.png",[["Stock Broad Sword","Stock Legionary","Stock Man-at-Arms"]+FINALS[:5],["Stock Legionary"]+FINALS[5:]],objects);contact(BASE/"combined-finalists-4x.png",[["Stock Legionary"]+FINALS],objects,True)
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));seq=[("Stock Legionary",1793),("Stock Man-at-Arms",75),("Stock Broad Sword",76)]+[(x["id"],x["unit_id"]) for x in units];placements=[]
 for i,(label,uid) in enumerate(seq):x=10+i*2.25;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=24,rotation=0);placements.append({"label":label,"unit_id":uid,"x":x,"y":24})
 sc.write_to_file(str(SCEN));defs=json.loads((BASE/"stock-punch-blender-report.json").read_text());report={"format":"rome2aoe2.hastati-stock-punch","version":1,"fixed":{"scale":"R133","composition":"unchanged","player_color":"none","normal_body_quantization":False},"definitions":defs,"finishing":{"C0":"none","C1":"semantic local contrast","C2":"mild acutance","C3":"cloth chroma preservation","C4":"bronze highlight shaping","C5":"semantic shadow chroma floor","C6":"material boundary emphasis","C7":"combined mild","C8":"combined upper","D0-D2":"bounded stock-guided semantic remaps 8/12/16%; not palette conversion"},"final_sources":FINAL_SOURCE,"measurements":rows,"units":units,"placements":placements,"attribution":{"recommended":"P5","lighting":"A9","material":"B7","finishing":"C7","remap":"D1 optional; smaller contribution than A/B/C"},"paths":{"mod":str(MOD),"scenario":str(SCEN)}};(BASE/"hastati-stock-punch-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report["attribution"],indent=2))
if __name__=="__main__":main()
