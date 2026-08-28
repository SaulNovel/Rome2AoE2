"""Package the Hastati AoE-style candidate sweep as one native AoE2 DE proof."""
from __future__ import annotations
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src"),str(ROOT/"third_party/python-deps"),str(ROOT/"third_party/AoE2ScenarioParser")]
V=ROOT/"build/python-deps/sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from PIL import Image,ImageFilter
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld,parse_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.generate_v4_ingame_proof import downsample_about_feet,make_shadow
from aoe2.generate_hastati_artistic_candidates import BASE,DEFS,process,pc_mask

SOURCE_DAT=ROOT/"test_data/empires2_x2_p1.dat";TEMPLATE=ROOT/"test_data/EmptyMap.aoe2scenario";TEX=ROOT/"build/tools/directxtex-may2026/texconv.exe"
MOD=BASE/"ROME2AOE2_AOE_STYLE_HASTATI";G=MOD/"resources/_common/drs/graphics";DAT=BASE/"hastati_style_calibration.dat";MODDAT=MOD/"resources/_common/dat/empires2_x2_p1.dat"
SCEN=BASE/"Rome2AoEStyleCalibrationHastati.aoe2scenario";FACETS=16
def player_layer(base,coverage):
 lum=base.convert("L");alpha=base.getchannel("A");v=Image.new("RGBA",base.size)
 data=[]
 for l,c,a in zip(lum.getdata(),coverage.getdata(),alpha.getdata()):
  q=round(l*c/255);data.append((q,q,q,a if q else 0))
 v.putdata(data);return v
def main():
 G.mkdir(parents=True,exist_ok=True);ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEX);candidates=[]
 for i,(cid,name,p) in enumerate(DEFS):
  uid=3101+i;stem=f"rome2_hastati_style_{cid.lower()}";display=f"Hastati {cid} {name}";gr=ws.graphic_manager.add_graphic(stem,name=display,frame_count=1,angle_count=FACETS,frame_duration=1.0)
  u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=display;u.standing_sprite_id1=u.standing_sprite_id2=gr.id
  c={"id":cid,"name":name,"display_name":display,"unit_id":uid,"graphic_id":gr.id,"stem":stem,"parameters":p};candidates.append(c)
  hi=process(cid,p);height=p.get("height",52)
  for zoom,canvas,logical,hotspot in (("x1",200,height,(100,100)),("x2",400,height*2,(200,200))):
   base=downsample_about_feet(hi,canvas,logical,hotspot)
   if p.get("post_sharp"):base2=Image.blend(base,base.filter(ImageFilter.UnsharpMask(1.0 if zoom=="x1" else 2.0,130,2)),p["post_sharp"]);base2.putalpha(base.getchannel("A"));base=base2
   pc=None
   if p.get("pc"):pc=player_layer(base,pc_mask(canvas,logical,hotspot,p["pc"]))
   doc=author_identical_facets(base,make_shadow(base),FACETS,hotspot,encoder=enc,player_color=pc);raw=serialize_sld(doc)
   if raw!=serialize_sld(parse_sld(raw)):raise RuntimeError(f"{cid} {zoom}: nondeterministic SLD")
   (G/f"{stem}_{zoom}.sld").write_bytes(raw)
 ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT)
 (MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"29-candidate Hastati AoE2 sprite-style calibration.","Title":"Rome2AoE2 Hastati Style Calibration"},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));placements=[]
 stocks=((74,"Stock Militia"),(75,"Stock Man-at-Arms"),(1793,"Stock Legionary"))
 for col,(uid,name) in enumerate(stocks):x=8+col*5;y=44;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=y,rotation=0);placements.append({"row":0,"column":col,"name":name,"unit_id":uid,"x":x,"y":y})
 groups=[("A",[c for c in candidates if c["id"].startswith("A")]),("B",[c for c in candidates if c["id"].startswith("B")]),("C",[c for c in candidates if c["id"].startswith("C")]),("D",[c for c in candidates if c["id"].startswith("D")]),("E",[c for c in candidates if c["id"].startswith("E")]),("F",[c for c in candidates if c["id"].startswith("F")])]
 for row,(_,items) in enumerate(groups,1):
  for col,c in enumerate(items):x=8+col*5;y=44-row*5;sc.unit_manager.add_unit(player=1,unit_const=c["unit_id"],x=x,y=y,rotation=0);c.update({"row":row,"column":col,"x":x,"y":y});placements.append({"row":row,"column":col,"name":c["display_name"],"unit_id":c["unit_id"],"x":x,"y":y})
 sc.write_to_file(str(SCEN))
 legend=["Rome2AoE2 Hastati Style Calibration","","Row 0: stock references",""]
 for p in placements:legend.append(f"row {p['row']} col {p['column']} | ({p['x']},{p['y']}) | unit {p['unit_id']} | {p['name']}")
 legend += ["","Custom graphics:"]+[f"{c['id']} | unit {c['unit_id']} | graphic {c['graphic_id']} | {c['stem']} | {json.dumps(c['parameters'],sort_keys=True)}" for c in candidates]
 (BASE/"LEGEND.txt").write_text("\n".join(legend)+"\n")
 report={"format":"rome2aoe2.hastati-style-proof","version":1,"candidate_count":len(candidates),"facets":16,"frames_per_facet":1,"mod_root":str(MOD),"canonical_dat":str(MODDAT),"scenario":str(SCEN),"legend":str(BASE/"LEGEND.txt"),"candidates":candidates,"placements":placements}
 (BASE/"hastati-style-proof.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
