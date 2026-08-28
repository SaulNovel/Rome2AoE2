"""Author the focused fixed-R133 render-art-direction proof."""
from __future__ import annotations
import hashlib,json,math,shutil,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
import numpy as np
from PIL import Image,ImageDraw,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld,parse_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.generate_hastati_gameplay_finish_proof import aligned,tunic_stats
from aoe2.generate_hastati_v2_proof import SOURCE_DAT,TEMPLATE,TEX,shadow_v2
from aoe2.generate_hastati_v3_proof import pc_for
from aoe2.aoe_sprite_finish import semantic_masks,rgb_oklab,rgba
from aoe2.generate_hastati_material_finish_proof import ACTIVE,ID
from aoe2.analyze_aoe_style_uhd import decode,display,GRAPHICS,FACET,BG
BASE=ROOT/"build/local-integration/rome2/aoe-render-art-direction";MASTERS=BASE/"masters";PRE=BASE/"x2-pre-sld";DEC=BASE/"decoded-x2";DIAG=BASE/"diagnostic-sld";MOD=BASE/"ROME2AOE2_HASTATI_RENDER_ART_DIRECTION";G=MOD/"resources/_common/drs/graphics";DAT=MOD/"resources/_common/dat/empires2_x2_p1.dat";SCEN=BASE/"Rome2HastatiRenderArtDirection.aoe2scenario"
STUDIES=["CM1","CM2","CM3","CM4"]+[f"LR{i}" for i in range(7)]+[f"BR{i}" for i in range(5)]+[f"CL{i}" for i in range(4)]+[f"F{i}" for i in range(8)]
COLORS={"cloth":(255,0,0),"bronze":(0,0,255),"shield body":(255,0,255)}
def mask_array(name):return semantic_masks(ID,ACTIVE)[name]
def color_stats(im,mask):
 a=rgba(im);lab=rgb_oklab(a[...,:3]);w=mask*a[...,3];sel=w>.03
 if not np.any(sel):return {"pixels":0}
 L=lab[...,0][sel];aa=lab[...,1][sel];bb=lab[...,2][sel];ch=np.hypot(aa,bb);h=np.degrees(np.arctan2(bb,aa))%360;ww=w[sel]
 return {"pixels":int(sel.sum()),"luminance_p10":round(float(np.quantile(L,.1)),5),"luminance_p50":round(float(np.median(L)),5),"luminance_p90":round(float(np.quantile(L,.9)),5),"chroma_mean":round(float(np.average(ch,weights=ww)),5),"hue_degrees":round(float(np.average(h,weights=ww)),3),"near_white_coverage":round(float(np.mean(L>.92)),5),"deep_dark_coverage":round(float(np.mean(L<.18)),5)}
def transformed_mask(name,master,canvas,nominal,hot):
 m=Image.fromarray(np.round(mask_array(name)*255).astype(np.uint8),"L").convert("RGBA");return np.asarray(aligned(m,master,canvas,nominal,hot).getchannel("R"),np.float32)/255
def restrained(master,canvas,nominal,hot,mild=False):
 q=aligned(master,master,canvas,nominal,hot)
 if mild:q=q.filter(ImageFilter.UnsharpMask(radius=.8 if canvas==400 else .45,percent=25,threshold=3))
 return q
def author_x2(cid,master,enc):
 body=restrained(master,400,106,(200,200),cid=="F6");PRE.mkdir(parents=True,exist_ok=True);body.save(PRE/f"{cid}.png");shadow=shadow_v2(body,"SH02",(200,200));p=DIAG/f"{cid}_x2.sld";p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(serialize_sld(author_identical_facets(body,shadow,16,(200,200),encoder=enc)));o=decode(p,0);o["main"].save(DEC/f"{cid}.png");b=o["main"].getchannel("A").getbbox()
 masks_hi={x:mask_array(x) for x in ("cloth","bronze")};masks_pre={x:transformed_mask(x,master,400,106,(200,200)) for x in masks_hi}
 return o,{"id":cid,"master":str(MASTERS/f"{cid}.png"),"pre_x2":str(PRE/f"{cid}.png"),"decoded_x2":str(DEC/f"{cid}.png"),"diagnostic_sld_x2":str(p),"decoded_body_dimensions":[b[2]-b[0],b[3]-b[1]],"stages":{x:{"master":color_stats(master,masks_hi[x]),"downsample":color_stats(body,masks_pre[x]),"decoded_sld":color_stats(o["main"],masks_pre[x])} for x in masks_hi}}
def stock(uid):
 ws=GenieWorkspace.load(SOURCE_DAT);u=ws.unit_manager.get(uid);g=ws.graphic_manager.get(u.standing_sprite_id1);stem=g.file_name[:-3];return decode(GRAPHICS/f"{stem}_x2.sld",FACET*g.frame_count)
def crop_visual(o):
 b=o["main"].getchannel("A").getbbox();return display(o).crop(b)
def sheets(rows,objects):
 stock_leg=stock(1793);stock_br=stock(76)
 arrangements=[[('Stock Broad Sword',stock_br)]+[(x,objects[x]) for x in [f"BR{i}" for i in range(5)]],[('Stock Legionary',stock_leg)]+[(x,objects[x]) for x in ("F0","F1","F2","F3")],[('Stock Legionary',stock_leg)]+[(x,objects[x]) for x in ("F4","F5","F6","F7")]]
 def make(path,high=False,pixels=False):
  cw,ch=220,210;out=Image.new("RGBA",(cw*6,ch*3),BG);d=ImageDraw.Draw(out)
  for y,line in enumerate(arrangements):
   for x,(label,obj) in enumerate(line):
    if high and label in rows:
     im=Image.open(rows[label]["master"]).convert("RGBA");b=im.getchannel("A").getbbox();q=im.crop(b)
    else:q=crop_visual(obj if "doc" in obj else objects[label])
    if pixels:q=q.resize((q.width*4,q.height*4),Image.Resampling.NEAREST)
    q.thumbnail((cw-10,ch-30),Image.Resampling.NEAREST if pixels else Image.Resampling.LANCZOS);out.alpha_composite(q,(x*cw+(cw-q.width)//2,y*ch+4));d.text((x*cw+4,y*ch+ch-19),label,fill="white")
  out.save(path)
 high_objects={k:v for k,v in rows.items()};make(BASE/"aoe-render-art-direction-highres.png",True);make(BASE/"aoe-render-art-direction-x2.png");make(BASE/"aoe-render-art-direction-4x.png",False,True)
def main():
 for p in (PRE,DEC,DIAG,G):p.mkdir(parents=True,exist_ok=True)
 enc=DirectXTexBC1Encoder(TEX);objects={};records={}
 for cid in STUDIES:
  master=Image.open(MASTERS/f"{cid}.png").convert("RGBA");objects[cid],records[cid]=author_x2(cid,master,enc)
 ws=GenieWorkspace.load(SOURCE_DAT);final_rows=[]
 for i,cid in enumerate([f"F{i}" for i in range(8)]+["F5PC"]):
  source="F5" if cid=="F5PC" else cid;master=Image.open(MASTERS/f"{source}.png").convert("RGBA");uid=3701+i;stem=f"rome2_hastati_art_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=f"Hastati Art {cid}",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"Hastati Art {cid}";u.standing_sprite_id1=u.standing_sprite_id2=gr.id;row={"id":cid,"source":source,"unit_id":uid,"graphic_id":gr.id,"stem":stem}
  for z,canvas,nominal,hot in (("x1",200,53,(100,100)),("x2",400,106,(200,200))):
   body=restrained(master,canvas,nominal,hot,source=="F6");shadow=shadow_v2(body,"SH02",hot);pc=None
   if cid=="F5PC":pc,_=pc_for(body,nominal,hot,"shield")
   p=G/f"{stem}_{z}.sld";p.write_bytes(serialize_sld(author_identical_facets(body,shadow,16,hot,encoder=enc,player_color=pc)));doc=parse_sld(p.read_bytes());row[z]={"path":str(p),"sha256":hashlib.sha256(p.read_bytes()).hexdigest(),"frames":len(doc.frames),"canvas":[canvas,canvas],"hotspot":list(hot)}
  final_rows.append(row)
 DAT.parent.mkdir(parents=True,exist_ok=True);ws.save(DAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Title":"Rome2AoE2 Hastati Render Art Direction","Description":"Fixed-R133 focused neutral render-source comparison."},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));seq=[("Stock Legionary",1793),("Stock Man-at-Arms",75),("Stock Broad Sword ref",76)]+[(x["id"],x["unit_id"]) for x in final_rows];placements=[]
 for i,(label,uid) in enumerate(seq):x=10+i*2.3;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=24,rotation=0);placements.append({"label":label,"unit_id":uid,"x":x,"y":24})
 sc.write_to_file(str(SCEN));sheets(records,objects)
 blender=json.loads((BASE/"blender-art-direction-report.json").read_text());guide=json.loads((BASE/"aoe-stock-color-guide.json").read_text());report={"format":"rome2aoe2.hastati-render-art-direction","version":1,"fixed_scale":"R133 decoded x2 bbox target 105; uniform X/Y","finishing":"alpha + Lanczos + SH02; F6 alone adds mild unsharp radius .8/25%","blender":blender,"stock_guide":str(BASE/"aoe-stock-color-guide.json"),"studies":records,"finals":final_rows,"recommendation":{"neutral":"F5","shield_only":"F5PC","status":"bounded evidence-based starting point; in-game judgment authoritative"},"placements":placements,"paths":{"mod":str(MOD),"scenario":str(SCEN),"highres_sheet":str(BASE/"aoe-render-art-direction-highres.png"),"x2_sheet":str(BASE/"aoe-render-art-direction-x2.png"),"pixels4_sheet":str(BASE/"aoe-render-art-direction-4x.png")}}
 report["blender"]["engine"]="BLENDER_EEVEE (Eevee Next implementation)"
 (BASE/"hastati-render-art-direction-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report["recommendation"],indent=2))
if __name__=="__main__":main()
