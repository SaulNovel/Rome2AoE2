"""Reduce, measure, encode, compare, and package the bounded daylight study."""
from __future__ import annotations
import colorsys,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.aoe_sprite_finish import rgba,rgb_oklab
from aoe2.generate_hastati_gameplay_finish_proof import aligned
from aoe2.generate_hastati_stock_punch_proof import semantic_finish,mask_canvas,stock
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.analyze_aoe_style_uhd import decode,display,metrics,BG

BASE=ROOT/"build/local-integration/rome2/hastati-rome2-daylight-bronze";MASTER=BASE/"masters";PRE=BASE/"x2-pre-sld";DEC=BASE/"decoded-x2";DIAG=BASE/"diagnostic-sld"
MOD=BASE/"ROME2AOE2_HASTATI_ROME2_DAYLIGHT_BRONZE";G=MOD/"resources/_common/drs/graphics";DAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2HastatiRome2DaylightBronze.aoe2scenario"
IDS=[f"BR{i}" for i in range(7)];FINALS=("BR0","BR3","BR4","BR5","BR6")

def mask(master,canvas):return mask_canvas("bronze",master,canvas,106 if canvas==400 else 53,(canvas//2,canvas//2))
def master_mask():
 a=np.asarray(Image.open(ROOT/"build/local-integration/rome2/material-aware-finishing/inputs/hastati-material-id-3200.png").convert("RGB"),np.uint8)
 return a[...,2].astype(np.float32)/255
def finish(cid,canvas):
 m=Image.open(MASTER/f"{cid}.png").convert("RGBA");body=aligned(m,m,canvas,106 if canvas==400 else 53,(canvas//2,canvas//2));return semantic_finish(body,"combined",1),m
def region(im,m):
 a=rgba(im);sel=(m*a[...,3])>.03;rgb=a[...,:3][sel];lab=rgb_oklab(a[...,:3]);L=lab[...,0][sel];aa=lab[...,1][sel];bb=lab[...,2][sel];ch=np.hypot(aa,bb);lum=.2126*rgb[:,0]+.7152*rgb[:,1]+.0722*rgb[:,2]
 hsv=np.array([colorsys.rgb_to_hsv(*q) for q in rgb]);gray=np.asarray(im.convert("L"),np.float32);blur=np.asarray(im.convert("L").filter(ImageFilter.GaussianBlur(1.5)),np.float32);q=lambda p:round(float(np.quantile(L,p)),5)
 return {"pixels":int(sel.sum()),"L10":q(.1),"L50":q(.5),"L90":q(.9),"L95":q(.95),"hue":round(float(np.degrees(np.arctan2(np.mean(bb),np.mean(aa)))%360),3),"chroma":round(float(ch.mean()),5),"saturation":round(float(np.median(hsv[:,1])),5),"local_contrast":round(float(np.abs(gray-blur)[sel].mean()),3),"highlight_coverage":round(float(np.mean(L>=.62)),5),"near_white_coverage":round(float(np.mean(np.max(rgb,axis=1)>=.98)),5),"clipped_coverage":round(float(np.mean(np.max(rgb,axis=1)>=.995)),5)}
def sheet(path,labels,objects):
 cw,ch=190,205;out=Image.new("RGBA",(cw*len(labels),ch),BG);d=ImageDraw.Draw(out)
 for i,x in enumerate(labels):
  o=objects[x];b=o["main"].getchannel("A").getbbox();q=display(o).crop(b);q.thumbnail((cw-8,ch-28),Image.Resampling.NEAREST);out.alpha_composite(q,(i*cw+(cw-q.width)//2,2));d.text((i*cw+3,ch-18),x,fill="white")
 out.save(path)
def highres_sheet():
 labels=IDS;cw,ch=300,390;out=Image.new("RGBA",(cw*len(labels),ch),(40,45,39,255));d=ImageDraw.Draw(out)
 for i,x in enumerate(labels):
  im=Image.open(MASTER/f"{x}.png").convert("RGBA");b=im.getchannel("A").getbbox();q=im.crop(b);q.thumbnail((cw-12,ch-32),Image.Resampling.LANCZOS);out.alpha_composite(q,(i*cw+(cw-q.width)//2,2));d.text((i*cw+5,ch-20),x,fill="white")
 out.save(BASE/"high-res-bronze-study.png")
def facing_report():
 rows=[];ims=[]
 for i in range(16):
  p=BASE/"facing-diagnostic"/f"facet_{i:02d}.png";mp=BASE/"facing-bronze-masks"/f"facet_{i:02d}.png";im=Image.open(p).convert("RGBA");ma=np.asarray(Image.open(mp).convert("RGB"),np.uint8)[...,0]>127;body=np.asarray(im)[...,3]>8;rows.append({"facet":i,"azimuth":45+22.5*i,"bronze_pixels_master_800":int(ma.sum()),"body_pixels_master_800":int(body.sum()),"bronze_body_coverage":round(float(ma.sum()/max(1,body.sum())),5)});ims.append(im)
 eligible=[r for r in rows if r["facet"] not in (7,8,9)];best=max(eligible,key=lambda x:x["bronze_pixels_master_800"]);alt=sorted(eligible,key=lambda x:x["bronze_pixels_master_800"],reverse=True)[1]
 cw,ch=220,250;sel=[0,best["facet"],alt["facet"]];out=Image.new("RGBA",(cw*3,ch),(40,45,39,255));d=ImageDraw.Draw(out)
 for j,i in enumerate(sel):q=ims[i].crop(ims[i].getchannel("A").getbbox());q.thumbnail((200,215),Image.Resampling.LANCZOS);out.alpha_composite(q,(j*cw+(cw-q.width)//2,4));r=rows[i];d.text((j*cw+5,225),f"facet {i:02d}: {r['bronze_pixels_master_800']} px ({100*r['bronze_body_coverage']:.1f}%)",fill="white")
 out.save(BASE/"facing-sheet.png");return {"current":rows[0],"bronze_exposure":best,"alternate":alt,"all":rows}
def main():
 for p in (PRE,DEC,DIAG,G):p.mkdir(parents=True,exist_ok=True)
 enc=DirectXTexBC1Encoder(TEX);objects={};rows={}
 for cid in IDS:
  body,master=finish(cid,400);m=mask(master,400);pre=region(body,m);body.save(PRE/f"{cid}.png");p=DIAG/f"{cid}_x2.sld";p.write_bytes(serialize_sld(author_identical_facets(body,shadow_v2(body,"SH02",(200,200)),16,(200,200),encoder=enc)));o=decode(p,0);o["main"].save(DEC/f"{cid}.png");objects[cid]=o
  rows[cid]={"definition":json.loads((BASE/"rome2-daylight-render-report.json").read_text())["definitions"][cid],"bronze":{"master_before_reduction":region(master,master_mask()),"x2_pre_sld":pre,"decoded_x2":region(o["main"],m)},"whole_body_decoded_x2":metrics(o)}
 ws=GenieWorkspace.load(SOURCE_DAT);units=[]
 for i,cid in enumerate(FINALS):
  uid=3761+i;stem=f"rome2_hastati_daylight_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati Daylight {cid}",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati Daylight {cid}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id
  for z,canvas in (("x1",200),("x2",400)):
   body,_=finish(cid,canvas);hot=(canvas//2,canvas//2);(G/f"{stem}_{z}.sld").write_bytes(serialize_sld(author_identical_facets(body,shadow_v2(body,"SH02",hot),16,hot,encoder=enc)))
  units.append({"candidate":cid,"unit_id":uid,"graphic_id":gr.id,"stem":stem})
 DAT.parent.mkdir(parents=True,exist_ok=True);ws.save(DAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Hastati Rome II Daylight Bronze","Description":"Bounded Rome II daylight and bronze finalists."},indent=2)+"\n")
 objects.update({"Stock Heavy Swordsman":stock(76),"Stock Legionary":stock(1793)});sheet(BASE/"decoded-x2-comparison.png",["Stock Heavy Swordsman","Stock Legionary"]+list(FINALS),objects);highres_sheet()
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));seq=[("Stock Heavy Swordsman",76),("Stock Legionary",1793)]+[(x["candidate"],x["unit_id"]) for x in units];placements=[]
 for i,(label,uid) in enumerate(seq):x=11+i*2.35;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=24,rotation=0);placements.append({"label":label,"unit_id":uid,"x":x,"y":24})
 sc.write_to_file(str(SCEN));render=json.loads((BASE/"rome2-daylight-render-report.json").read_text());report={"format":"rome2aoe2.hastati-rome2-daylight-bronze","version":1,"baseline":"tracked config/render_profiles/hastati_p5_stock_punch_baseline.json; BR0/P5","evidence":render["evidence"],"facings":facing_report(),"measurements":rows,"finalists":units,"placements":placements,"recommendation":{"visual_selection_required":"BR3-BR6 are bounded candidates; in-game result remains authority"},"paths":{"mod":str(MOD),"scenario":str(SCEN)}};(BASE/"hastati-rome2-daylight-bronze-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
