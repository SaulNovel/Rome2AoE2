"""Generate the isolated DAT/scenario grid for native-SLD visual calibration."""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0,str(ROOT/"third_party"/"python-deps")); sys.path.insert(0,str(ROOT/"third_party"/"AoE2ScenarioParser"))
from aoe2_genie_tooling import GenieWorkspace
from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario

SOURCE_UNIT=74
VARIANTS=[
 (2701,"scale_45","Scale 45 px",1),(2702,"scale_50","Scale 50 px",1),(2703,"scale_54","Scale 54 px",1),(2704,"scale_60","Scale 60 px",1),
 (2705,"brightness_current","Brightness v2",1),(2706,"brightness_exposure-plus-03","Brightness +0.3",1),
 (2707,"brightness_exposure-plus-06","Brightness +0.6",1),(2708,"brightness_fill-plus","Brightness fill",1),
 (2709,"playercolor_restrained","Player color restrained blue",1),(2710,"playercolor_restrained","Player color restrained red",2),
 (2711,"playercolor_stronger","Player color stronger blue",1),(2712,"playercolor_stronger","Player color stronger red",2),
 (2713,"shadow_current","Shadow current",1),(2714,"shadow_stronger","Shadow stronger",1),(2715,"shadow_contact","Shadow contact",1),
 (2716,"four_directions","Direction rear 3Q",1),(2717,"four_directions","Direction front 3Q",1),
 (2718,"four_directions","Direction shield side",1),(2719,"four_directions","Direction front",1),
]

def source_files(asset_root:Path,key:str):
    stem=f"rome2aoe2_visual_{key}"; return stem,asset_root/f"{stem}_x1.sld",asset_root/f"{stem}_x2.sld"

def generate(source_dat:Path,template:Path,asset_root:Path,mod_root:Path,scenario_out:Path)->dict:
    workspace=GenieWorkspace.load(source_dat); original=workspace.unit_manager.get(SOURCE_UNIT)
    original_state=(original.name,original.standing_sprite_id1,original.standing_sprite_id2)
    graphics=mod_root/"resources"/"_common"/"drs"/"graphics"; graphics.mkdir(parents=True,exist_ok=True)
    records=[]; by_key={}
    for unit_id,key,label,owner in VARIANTS:
        if workspace.unit_manager.exists(unit_id): raise ValueError(f"reserved diagnostic unit {unit_id} is occupied")
        stem,x1,x2=source_files(asset_root,key)
        if not x1.is_file() or not x2.is_file(): raise FileNotFoundError(f"missing x1/x2 pair for {key}")
        if key not in by_key:
            graphic=workspace.graphic_manager.add_graphic(stem,name=label,frame_count=1,angle_count=16,frame_duration=1.0)
            by_key[key]=graphic.id; shutil.copy2(x1,graphics/x1.name); shutil.copy2(x2,graphics/x2.name)
        clone=workspace.unit_manager.clone_into(unit_id,SOURCE_UNIT,on_conflict="error",fill_gaps="placeholder")
        clone.name=label; clone.standing_sprite_id1=by_key[key]; clone.standing_sprite_id2=by_key[key]
        records.append({"unit_id":unit_id,"owner":owner,"name":label,"graphic_id":by_key[key],"stem":stem})
    if (original.name,original.standing_sprite_id1,original.standing_sprite_id2)!=original_state: raise RuntimeError("original Militia changed")
    dat=mod_root/"resources"/"_common"/"dat"/"empires2_x2_p1.dat"; dat.parent.mkdir(parents=True,exist_ok=True); workspace.save(dat)
    (mod_root/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Native SLD visual calibration grid","Title":"Rome2AoE2 SLD Visual Calibration"},indent=2)+"\n",encoding="utf-8")
    scenario=AoE2DEScenario.from_file(str(template)); placements=[]
    # Stock comparison row: Militia, Legionary, Man-at-Arms.
    for unit_id,x in ((74,8),(1793,12),(75,16)):
        scenario.unit_manager.add_unit(player=1,unit_const=unit_id,x=x,y=22); placements.append({"unit_id":unit_id,"player":1,"x":x,"y":22})
    rows=[VARIANTS[0:4],VARIANTS[4:8],VARIANTS[8:12],VARIANTS[12:15],VARIANTS[15:19]]
    rotations=(0.0,0.25,0.375,0.5)
    for row_index,row in enumerate(rows):
        y=18-row_index*4
        for column,(unit_id,key,label,owner) in enumerate(row):
            rotation=rotations[column] if row_index==4 else 0.0
            scenario.unit_manager.add_unit(player=owner,unit_const=unit_id,x=8+column*4,y=y,rotation=rotation)
            placements.append({"unit_id":unit_id,"player":owner,"x":8+column*4,"y":y,"rotation":rotation,"label":label})
    scenario_out.parent.mkdir(parents=True,exist_ok=True); scenario.write_to_file(str(scenario_out))
    return {"format":"rome2aoe2.sld-visual-calibration-mod","version":1,"dat":dat.name,"records":records,
            "stock_references":[74,1793,75],"placements":placements,"scenario":scenario_out.name}

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--source-dat",type=Path,required=True); p.add_argument("--template",type=Path,required=True)
    p.add_argument("--asset-root",type=Path,required=True); p.add_argument("--mod-root",type=Path,required=True)
    p.add_argument("--scenario",type=Path,required=True); p.add_argument("--report",type=Path,required=True); a=p.parse_args()
    report=generate(a.source_dat,a.template,a.asset_root,a.mod_root,a.scenario)
    a.report.parent.mkdir(parents=True,exist_ok=True); a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
