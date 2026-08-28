"""Package the bounded Hastati/Eastern/Praetorian comparison proof."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build"/"python-deps"/"pillow"),str(ROOT/"src"),str(ROOT/"third_party"/"python-deps"),str(ROOT/"third_party"/"AoE2ScenarioParser")];V=ROOT/"build"/"python-deps"/"sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from PIL import Image
from aoe2_genie_tooling import GenieWorkspace
from aoe2.generate_v4_ingame_proof import downsample_about_feet,make_shadow
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.sld import serialize_sld
B=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration";R=B/"renders";MOD=B/"ROME2AOE2_COMPOSITION_CALIBRATION";G=MOD/"resources"/"_common"/"drs"/"graphics";DAT=B/"composition_calibration.dat";SC=B/"Rome2CompositionCalibration.aoe2scenario";SOURCE=ROOT/"test_data"/"empires2_x2_p1.dat";TEMPLATE=ROOT/"test_data"/"EmptyMap.aoe2scenario";TEX=ROOT/"build"/"tools"/"directxtex-may2026"/"texconv.exe"
C=[("H01","Hastati 01 Neutral"),("H02","Hastati 02 Restrained PC R"),("H03","Hastati 03 RGB Diagnostic"),("E01","Eastern 01 Neutral"),("E02","Eastern 02 R"),("E03","Eastern 03 G"),("E04","Eastern 04 B"),("E05","Eastern 05 RGB"),("P01","Praetorian 01 Hamata Nieder A"),("P02","Praetorian 02 Segmentata Gold B"),("P03","Praetorian 03 Hamata Italic C")]
def pc_r(base,mask):
 o=Image.new("RGBA",base.size)
 for y in range(base.height):
  for x in range(base.width):
   b=base.getpixel((x,y));m=mask.getpixel((x,y));cov=m[0]/255;v=round((.2126*b[0]+.7152*b[1]+.0722*b[2])*cov);o.putpixel((x,y),(v,v,v,b[3] if cov>.01 else 0))
 return o
def main():
 G.mkdir(parents=True,exist_ok=True);ws=GenieWorkspace.load(SOURCE);enc=DirectXTexBC1Encoder(TEX);rows=[]
 for i,(cid,name) in enumerate(C):
  uid=2901+i;stem=f"rome2_comp_{cid.lower()}";gr=ws.graphic_manager.add_graphic(stem,name=name,frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=name;u.standing_sprite_id1=u.standing_sprite_id2=gr.id;src=Image.open(R/f"{cid}.png").convert("RGBA")
  # H02 demonstrates restrained runtime player colour from Rome R only while
  # keeping H01's neutral source reconstruction as its RGB base.
  if cid=="H02":src=Image.open(R/"H01.png").convert("RGBA");masksrc=Image.open(ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"/"tint-masks"/"hastati-mask-rgb.png").convert("RGBA")
  for z,canvas,logical,h in (("x1",200,50,(100,100)),("x2",400,100,(200,200))):
   base=downsample_about_feet(src,canvas,logical,h);pc=None
   if cid=="H02":pc=pc_r(base,downsample_about_feet(masksrc,canvas,logical,h))
   s=author_identical_facets(base,make_shadow(base),16,h,encoder=enc,player_color=pc);(G/f"{stem}_{z}.sld").write_bytes(serialize_sld(s))
  rows.append({"id":cid,"display_name":name,"unit_id":uid,"graphic_id":gr.id,"stem":stem})
 ws.save(DAT);md=MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat";md.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,md);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Bounded composition/material comparison.","Title":"Rome2AoE2 Composition Calibration"},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));places=[]
 for x,uid,n in ((8,74,"Stock Militia"),(13,75,"Stock Man-at-Arms"),(18,1793,"Stock Legionary")):sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=40,rotation=0);places.append((n,x,40))
 groups=[rows[:3],rows[3:8],rows[8:]]
 for y,g in zip((34,28,22),groups):
  for col,row in enumerate(g):x=8+col*5;sc.unit_manager.add_unit(player=1,unit_const=row["unit_id"],x=x,y=y,rotation=0);row.update({"x":x,"y":y});places.append((row["display_name"],x,y))
 sc.write_to_file(str(SC));legend=["Rome2 Composition Calibration","All custom units Player 1; 5-tile spacing",""]+[f"{r['id']} | ({r['x']},{r['y']}) | unit {r['unit_id']} | graphic {r['graphic_id']} | {r['display_name']}" for r in rows];(B/"LEGEND.txt").write_text("\n".join(legend)+"\n");(B/"composition-proof.json").write_text(json.dumps({"format":"rome2aoe2.composition-proof","version":1,"candidates":rows,"scenario":str(SC),"mod_root":str(MOD)},indent=2)+"\n");print(json.dumps(rows,indent=2))
if __name__=="__main__":main()
