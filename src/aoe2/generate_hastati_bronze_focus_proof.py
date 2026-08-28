"""Frozen-baseline bronze-only SLD proof and measurements."""
from __future__ import annotations
import colorsys,hashlib,json,shutil,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld,parse_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.aoe_sprite_finish import rgba,rgb_oklab,oklab_rgb,image,boundary_finish
from aoe2.generate_hastati_gameplay_finish_proof import aligned
from aoe2.generate_hastati_stock_punch_proof import semantic_finish,mask_canvas,stock
from aoe2.generate_hastati_material_finish_proof import ID
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,BG
BASE=ROOT/"build/local-integration/rome2/hastati-bronze-focus";MASTER=BASE/"masters";PRE=BASE/"x2-pre-sld";DEC=BASE/"decoded-x2";DIAG=BASE/"diagnostic-sld";MOD=BASE/"ROME2AOE2_HASTATI_BRONZE_FOCUS";G=MOD/"resources/_common/drs/graphics";DAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2HastatiBronzeFocus.aoe2scenario"
DEFS=json.loads((BASE/"bronze-render-definitions.json").read_text())["definitions"];IDS=list(DEFS);FINALS={"E0":"D0","E1":"D1","E2":"D2","E3":"D3","E4":"D4"}
NOTES={"A0":"control; balanced but subdued","A1":"richer base, still restrained","A2":"darkest useful base; risks flatness","A3":"dark base with warmer readable lift","A4":"strong separation; slightly shiny","B0":"highlight control","B1":"warmer without enough punch","B2":"warmer and clearer","B3":"broad but slightly plastic","B4":"bright selective accent; can look shiny","C0":"specular control","C1":"stronger specular readability","C2":"too shiny in isolated accents","C3":"micro-contrast improves small metal","C4":"best gameplay punch in C family","C5":"strong metal/non-metal boundary","D0":"frozen baseline","D1":"rich dark broad bronze","D2":"strong warm metal","D3":"heroic but near upper shiny bound","D4":"best stock-like metal balance"}
def bronze_mask(master,canvas,nominal,hot):return mask_canvas("bronze",master,canvas,nominal,hot)
def bronze_post(im,master,kind,level=1):
 a=rgba(im);lab=rgb_oklab(a[...,:3]);m=bronze_mask(master,im.width,106 if im.width==400 else 53,(im.width//2,im.width//2));L=lab[...,0].copy()
 if kind in ("micro","local","combined"):
  radius=1.0 if kind=="micro" else 1.7;blur=np.asarray(Image.fromarray(np.round(L*255).astype(np.uint8),"L").filter(ImageFilter.GaussianBlur(radius)),np.float32)/255;lab[...,0]=np.clip(L+(L-blur)*(.18 if level==1 else .27)*m,0,1)
 if kind in ("highlight","combined"):
  hi=np.clip((lab[...,0]-.38)/.38,0,1);lab[...,0]=np.clip(lab[...,0]+(.035 if level==1 else .05)*hi*m,0,1);lab[...,1]+=.010*hi*m;lab[...,2]+=.014*hi*m
 if kind in ("boundary","combined"):lab,_=boundary_finish(lab,{"bronze":m},.009 if level==1 else .014)
 return image(oklab_rgb(lab),a[...,3])
def finished(cid,canvas):
 master=Image.open(MASTER/f"{cid}.png").convert("RGBA");nominal=106 if canvas==400 else 53;body=aligned(master,master,canvas,nominal,(canvas//2,canvas//2));body=semantic_finish(body,"combined",1);post=DEFS[cid].get("post")
 if post:body=bronze_post(body,master,post,1)
 return body,master
def bronze_metrics(im,mask):
 arr=np.asarray(im.convert("RGBA"),np.uint8);sel=(mask>.03)&(arr[...,3]>8);rgb=arr[...,:3][sel];lum=.2126*rgb[:,0]+.7152*rgb[:,1]+.0722*rgb[:,2];lab=rgb_oklab(rgb.reshape((-1,1,3)).astype(np.float32)/255.0);ch=np.hypot(lab[...,1],lab[...,2]).ravel();hsv=np.array([colorsys.rgb_to_hsv(*(x/255 for x in q)) for q in rgb]);lit=lum>=np.quantile(lum,.75);gray=im.convert("L");blur=gray.filter(ImageFilter.GaussianBlur(1.5));local=np.abs(np.asarray(gray,np.float32)-np.asarray(blur,np.float32))[sel];edge=np.asarray(gray.filter(ImageFilter.FIND_EDGES),np.float32)[sel]
 q=lambda p:round(float(np.quantile(lum,p)),3)
 return {"pixels":int(sel.sum()),"luminance_p50":q(.5),"luminance_p75":q(.75),"luminance_p90":q(.9),"luminance_p95":q(.95),"chroma_mean":round(float(ch.mean()),5),"saturation_median":round(float(np.median(hsv[:,1])),5),"lit_warm_hue_degrees":round(float(np.median(hsv[lit,0])*360),3),"local_contrast":round(float(local.mean()),3),"edge_contrast":round(float(edge.mean()),3),"highlight_coverage":round(float(np.mean(lum>=np.quantile(lum,.9))),5),"clipped_highlight_coverage":round(float(np.mean(np.max(rgb,axis=1)>=250)),5)}
def contact(path,groups,objects,pixels=False):
 cw,ch=190,200;out=Image.new("RGBA",(cw*max(map(len,groups)),ch*len(groups)),BG);d=ImageDraw.Draw(out)
 for y,line in enumerate(groups):
  for x,label in enumerate(line):
   o=objects[label];b=o["main"].getchannel("A").getbbox();q=display(o).crop(b)
   if pixels:q=q.resize((q.width*4,q.height*4),Image.Resampling.NEAREST)
   q.thumbnail((cw-8,ch-28),Image.Resampling.NEAREST if pixels else Image.Resampling.LANCZOS);out.alpha_composite(q,(x*cw+(cw-q.width)//2,y*ch+2));d.text((x*cw+3,y*ch+ch-18),label,fill="white")
 out.save(path)
def closeups(path,labels,objects,masks):
 cw,ch=250,250;out=Image.new("RGBA",(cw*len(labels),ch),BG);d=ImageDraw.Draw(out)
 for i,label in enumerate(labels):
  o=objects[label];b=masks.get(label).getbbox() if label in masks else o["main"].getchannel("A").getbbox();pad=8;b=(max(0,b[0]-pad),max(0,b[1]-pad),min(o["main"].width,b[2]+pad),min(o["main"].height,b[3]+pad));q=display(o).crop(b).resize(((b[2]-b[0])*4,(b[3]-b[1])*4),Image.Resampling.NEAREST);q.thumbnail((cw-8,ch-25),Image.Resampling.NEAREST);out.alpha_composite(q,(i*cw+(cw-q.width)//2,2));d.text((i*cw+3,ch-18),label,fill="white")
 out.save(path)
def main():
 for p in (PRE,DEC,DIAG,G):p.mkdir(parents=True,exist_ok=True)
 enc=DirectXTexBC1Encoder(TEX);objects={};rows={};masks={}
 for cid in IDS:
  body,master=finished(cid,400);body.save(PRE/f"{cid}.png");mask=bronze_mask(master,400,106,(200,200));sh=shadow_v2(body,"SH02",(200,200));p=DIAG/f"{cid}_x2.sld";p.write_bytes(serialize_sld(author_identical_facets(body,sh,16,(200,200),encoder=enc)));o=decode(p,0);objects[cid]=o;o["main"].save(DEC/f"{cid}.png");masks[cid]=Image.fromarray(np.round(mask*255).astype(np.uint8),"L");rows[cid]={"id":cid,"definition":DEFS[cid],"bronze":bronze_metrics(o["main"],mask),"whole_body":metrics(o),"qualitative_note":NOTES[cid]}
 ws=GenieWorkspace.load(SOURCE_DAT);units=[]
 for i,(eid,cid) in enumerate(FINALS.items()):
  uid=3741+i;stem=f"rome2_hastati_bronze_{eid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati Bronze {eid}",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati Bronze {eid}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id;final_bronze=None
  for z,canvas,hot in (("x1",200,(100,100)),("x2",400,(200,200))):
   body,master=finished(cid,canvas)
   if eid=="E2":body=bronze_post(body,master,"local",1)
   if eid=="E3":body=bronze_post(body,master,"boundary",1)
   if eid=="E4":body=bronze_post(body,master,"combined",1)
   sh=shadow_v2(body,"SH02",hot);p=G/f"{stem}_{z}.sld";p.write_bytes(serialize_sld(author_identical_facets(body,sh,16,hot,encoder=enc)))
   if z=="x2":final_bronze=bronze_metrics(decode(p,0)["main"],bronze_mask(master,400,106,(200,200)))
  units.append({"id":eid,"source":cid,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"bronze":final_bronze})
 DAT.parent.mkdir(parents=True,exist_ok=True);ws.save(DAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Bronze Focus","Description":"Bronze-only study over immutable P5-era baseline."},indent=2)+"\n")
 broad=stock(76);leg=stock(1793);objects.update({"Stock Broad Sword":broad,"Stock Legionary":leg});contact(BASE/"bronze-focused-contact-sheet.png",[["Stock Broad Sword"]+[f"A{i}" for i in range(5)],["Stock Broad Sword"]+[f"B{i}" for i in range(5)],["Stock Legionary"]+[f"C{i}" for i in range(6)],["Stock Broad Sword"]+[f"D{i}" for i in range(5)]],objects);closeups(BASE/"bronze-closeups-4x.png",["Stock Broad Sword","Stock Legionary"]+[f"D{i}" for i in range(5)],objects,masks);contact(BASE/"in-game-proof-sheet.png",[["Stock Broad Sword","Stock Legionary"]+[f"D{i}" for i in range(5)]],objects)
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));seq=[("Stock Broad Sword",76),("Stock Legionary",1793)]+[(x["id"],x["unit_id"]) for x in units];placements=[]
 for i,(label,uid) in enumerate(seq):x=12+i*2.3;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=24,rotation=0);placements.append({"label":label,"unit_id":uid,"x":x,"y":24})
 sc.write_to_file(str(SCEN));report={"format":"rome2aoe2.hastati-bronze-focus","version":1,"baseline":{"label":"Hastati bronze punch baseline","path":str(ROOT/"build/local-integration/rome2/milestones/hastati-bronze-punch-baseline"),"immutable":True,"frozen":"R133, A9 lighting, improved cloth/general material hierarchy, SH02, C7 general semantic finish"},"measurements":rows,"finals":units,"recommendation":{"candidate":"E4","source":"D4 + bronze-only combined micro-contrast/highlight/boundary","runner_up":"E2","factor":"combined darker base + warm highlight + restrained specular + bronze-only local contrast"},"placements":placements,"paths":{"mod":str(MOD),"scenario":str(SCEN)}};(BASE/"hastati-bronze-focus-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report["recommendation"],indent=2))
if __name__=="__main__":main()
