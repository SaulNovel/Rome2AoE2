"""Package the 15 static Set A renders as native x1/x2 AoE2 DE graphics."""
from __future__ import annotations
import json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"build"/"python-deps"/"pillow"),str(ROOT/"src"),str(ROOT/"third_party"/"python-deps"),str(ROOT/"third_party"/"AoE2ScenarioParser")]
VENDORED=ROOT/"build"/"python-deps"/"sld-authoring"
if VENDORED.is_dir():sys.path.insert(0,str(VENDORED))
from PIL import Image
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.generate_v4_ingame_proof import downsample_about_feet,make_shadow

BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";R=BASE/"renders-set-a"
SOURCE_DAT=ROOT/"test_data"/"empires2_x2_p1.dat";TEMPLATE=ROOT/"test_data"/"EmptyMap.aoe2scenario";TEXCONV=ROOT/"build"/"tools"/"directxtex-may2026"/"texconv.exe"
BUILD_DAT=BASE/"set_a_calibration.dat";SCENARIO=BASE/"Rome2InfantryCalibrationSetA.aoe2scenario";MOD=BASE/"ROME2AOE2_INFANTRY_CALIBRATION_SET_A";GRAPHICS=MOD/"resources"/"_common"/"drs"/"graphics";MOD_DAT=MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat"
UNITS=[("hastati","Hastati"),("principes","Principes"),("triarii","Triarii"),("velites","Velites"),("celtic-warriors","Celtic Warriors")];LIGHTS=["L06","L10","L11"];FACETS=16
def main():
    candidates=[]
    for idx,(slug,name,light) in enumerate((u[0],u[1],l) for u in UNITS for l in LIGHTS):
        candidates.append({"slug":slug,"unit_name":name,"light":light,"stem":f"rome2_seta_{slug.replace('-','_')}_{light.lower()}","display_name":f"{name} {light}","unit_id":2801+idx})
    ws=GenieWorkspace.load(SOURCE_DAT)
    for c in candidates:
        if ws.unit_manager.exists(c["unit_id"]):raise ValueError(f"unit ID occupied: {c['unit_id']}")
        g=ws.graphic_manager.add_graphic(c["stem"],name=c["display_name"],frame_count=1,angle_count=FACETS,frame_duration=1.0);u=ws.unit_manager.clone_into(c["unit_id"],74,on_conflict="error",fill_gaps="placeholder");u.name=c["display_name"];u.standing_sprite_id1=g.id;u.standing_sprite_id2=g.id;c["graphic_id"]=g.id
    ws.save(BUILD_DAT);MOD_DAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(BUILD_DAT,MOD_DAT);GRAPHICS.mkdir(parents=True,exist_ok=True)
    enc=DirectXTexBC1Encoder(TEXCONV)
    for c in candidates:
        src=Image.open(R/f"{c['slug']}-{c['light']}.png").convert("RGBA")
        for zoom,canvas,logical,hotspot in (("x1",200,50,(100,100)),("x2",400,100,(200,200))):
            main=downsample_about_feet(src,canvas,logical,hotspot);shadow=make_shadow(main);doc=author_identical_facets(main,shadow,FACETS,hotspot,encoder=enc);(GRAPHICS/f"{c['stem']}_{zoom}.sld").write_bytes(serialize_sld(doc))
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    sc=AoE2DEScenario.from_file(str(TEMPLATE));placements=[]
    for col,(uid,name) in enumerate(((74,"Stock Militia"),(75,"Stock Man-at-Arms"),(1793,"Stock Legionary"))):x=8+col*5;y=38;sc.unit_manager.add_unit(player=1,unit_const=uid,x=x,y=y,rotation=0);placements.append({"name":name,"unit_id":uid,"x":x,"y":y})
    for row,(slug,name) in enumerate(UNITS,1):
        for col,light in enumerate(LIGHTS):
            c=next(x for x in candidates if x["slug"]==slug and x["light"]==light);x=8+col*5;y=38-row*5;sc.unit_manager.add_unit(player=1,unit_const=c["unit_id"],x=x,y=y,rotation=0);c.update({"row":row,"column":col,"x":x,"y":y});placements.append({"name":c["display_name"],"unit_id":c["unit_id"],"x":x,"y":y})
    sc.write_to_file(str(SCENARIO));(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Five-unit L06/L10/L11 calibration Set A.","Title":"Rome2AoE2 Infantry Calibration Set A"},indent=2)+"\n")
    report={"format":"rome2aoe2.cross-unit-set-a-proof","version":1,"facets":16,"frames_per_facet":1,"logical_height":50,"canonical_dat":str(MOD_DAT),"scenario":str(SCENARIO),"mod_root":str(MOD),"candidates":candidates,"placements":placements};(BASE/"aoe-proof-set-a.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps(report,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
