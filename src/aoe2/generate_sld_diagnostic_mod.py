"""Generate the isolated one-facet Praetorian SLD diagnostic data mod."""
from __future__ import annotations
import argparse, json, shutil, sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(PROJECT_ROOT/"third_party"/"python-deps"))
from aoe2_genie_tooling import GenieWorkspace

SOURCE_UNIT_ID=74
DIAGNOSTIC_UNIT_ID=2081
COLOR_UNIT_ID=2113
FRONT_UNIT_ID=2114
DEBUG_UNIT_ID=2115
GRAPHIC_STEM="rome2aoe2_praetorian_sld_diagnostic"
COLOR_GRAPHIC_STEM="rome2aoe2_rgb_sld_diagnostic"
FRONT_GRAPHIC_STEM="rome2aoe2_praetorian_front3q"
DEBUG_GRAPHIC_STEM="rome2aoe2_praetorian_front3q_debug60"

def configure_clone(workspace, graphic_stem: str = GRAPHIC_STEM):
    if not workspace.unit_manager.exists(SOURCE_UNIT_ID): raise ValueError("Militia unit 74 is missing")
    if workspace.unit_manager.exists(DIAGNOSTIC_UNIT_ID): raise ValueError("diagnostic unit 2081 is already occupied")
    original=workspace.unit_manager.get(SOURCE_UNIT_ID)
    original_state=(original.standing_sprite_id1,original.standing_sprite_id2,original.name)
    graphic=workspace.graphic_manager.add_graphic(graphic_stem,name="Praetorian SLD diagnostic",frame_count=1,angle_count=16,frame_duration=1.0)
    clone=workspace.unit_manager.clone_into(DIAGNOSTIC_UNIT_ID,SOURCE_UNIT_ID,on_conflict="error",fill_gaps="placeholder")
    clone.name="Praetorian SLD Diagnostic"; clone.standing_sprite_id1=graphic.id; clone.standing_sprite_id2=graphic.id
    if (original.standing_sprite_id1,original.standing_sprite_id2,original.name) != original_state:
        raise RuntimeError("original Militia was modified")
    return graphic.id

def generate(source_dat: Path, output_dat: Path, source_sld_x1: Path, source_sld_x2: Path, color_sld_x1: Path,
             color_sld_x2: Path, front_sld_x1: Path, front_sld_x2: Path, debug_sld_x1: Path, debug_sld_x2: Path) -> dict:
    workspace=GenieWorkspace.load(source_dat)
    source_militia=workspace.unit_manager.get(SOURCE_UNIT_ID)
    source_state=(source_militia.name,source_militia.standing_sprite_id1,source_militia.standing_sprite_id2)
    graphic_id=configure_clone(workspace)
    if workspace.unit_manager.exists(COLOR_UNIT_ID): raise ValueError("diagnostic color unit 2082 is already occupied")
    color_graphic=workspace.graphic_manager.add_graphic(COLOR_GRAPHIC_STEM,name="RGB SLD diagnostic",frame_count=1,angle_count=16,frame_duration=1.0)
    color_clone=workspace.unit_manager.clone_into(COLOR_UNIT_ID,SOURCE_UNIT_ID,on_conflict="error",fill_gaps="placeholder")
    color_clone.name="RGB SLD Diagnostic"; color_clone.standing_sprite_id1=color_graphic.id; color_clone.standing_sprite_id2=color_graphic.id
    extra=[]
    for unit_id,stem,label in ((FRONT_UNIT_ID,FRONT_GRAPHIC_STEM,"Praetorian Front 3Q"),(DEBUG_UNIT_ID,DEBUG_GRAPHIC_STEM,"Praetorian Debug 60px")):
        graphic=workspace.graphic_manager.add_graphic(stem,name=label,frame_count=1,angle_count=16,frame_duration=1.0)
        clone=workspace.unit_manager.clone_into(unit_id,SOURCE_UNIT_ID,on_conflict="error",fill_gaps="placeholder")
        clone.name=label; clone.standing_sprite_id1=graphic.id; clone.standing_sprite_id2=graphic.id; extra.append((unit_id,graphic.id,stem))
    output_dat.parent.mkdir(parents=True,exist_ok=True); workspace.save(output_dat)
    mod_root=output_dat.parents[3]; graphics=mod_root/"resources"/"_common"/"drs"/"graphics"; graphics.mkdir(parents=True,exist_ok=True)
    destination=graphics/f"{GRAPHIC_STEM}_x1.sld"; destination_x2=graphics/f"{GRAPHIC_STEM}_x2.sld"
    color_destination=graphics/f"{COLOR_GRAPHIC_STEM}_x1.sld"; color_destination_x2=graphics/f"{COLOR_GRAPHIC_STEM}_x2.sld"
    front_destination=graphics/f"{FRONT_GRAPHIC_STEM}_x1.sld"; front_destination_x2=graphics/f"{FRONT_GRAPHIC_STEM}_x2.sld"
    debug_destination=graphics/f"{DEBUG_GRAPHIC_STEM}_x1.sld"; debug_destination_x2=graphics/f"{DEBUG_GRAPHIC_STEM}_x2.sld"
    shutil.copy2(source_sld_x1,destination); shutil.copy2(source_sld_x2,destination_x2); shutil.copy2(color_sld_x1,color_destination)
    shutil.copy2(color_sld_x2,color_destination_x2); shutil.copy2(front_sld_x1,front_destination); shutil.copy2(front_sld_x2,front_destination_x2)
    shutil.copy2(debug_sld_x1,debug_destination); shutil.copy2(debug_sld_x2,debug_destination_x2)
    (mod_root/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"One-facet native SLD compatibility diagnostic.","Title":"Rome2AoE2 SLD Diagnostic"},indent=2)+"\n",encoding="utf-8")
    written=GenieWorkspace.load(output_dat); militia=written.unit_manager.get(SOURCE_UNIT_ID); clone=written.unit_manager.get(DIAGNOSTIC_UNIT_ID)
    if (militia.name,militia.standing_sprite_id1,militia.standing_sprite_id2) != source_state: raise RuntimeError("written DAT changed original Militia")
    if (clone.standing_sprite_id1,clone.standing_sprite_id2) != (graphic_id,graphic_id): raise RuntimeError("written DAT lost diagnostic standing mapping")
    return {"format":"rome2aoe2.sld-diagnostic-mod","version":1,"source_unit_id":74,"diagnostic_unit_id":2081,
            "graphic_id":graphic_id,"graphic_stem":GRAPHIC_STEM,"frame_count":1,"facet_count":16,
            "sld_paths":[f"resources/_common/drs/graphics/{destination.name}",f"resources/_common/drs/graphics/{destination_x2.name}"],
            "color_unit_id":COLOR_UNIT_ID,"color_graphic_id":color_graphic.id,"color_sld_path":f"resources/_common/drs/graphics/{color_destination.name}",
            "front_unit_id":FRONT_UNIT_ID,"debug_unit_id":DEBUG_UNIT_ID,"extra_graphics":[{"unit_id":u,"graphic_id":g,"stem":s} for u,g,s in extra]}

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--source-dat",required=True); parser.add_argument("--output-dat",required=True); parser.add_argument("--sld-x1",required=True); parser.add_argument("--sld-x2",required=True); parser.add_argument("--color-sld-x1",required=True); parser.add_argument("--color-sld-x2",required=True); parser.add_argument("--front-sld-x1",required=True); parser.add_argument("--front-sld-x2",required=True); parser.add_argument("--debug-sld-x1",required=True); parser.add_argument("--debug-sld-x2",required=True); parser.add_argument("--report",required=True)
    args=parser.parse_args(); report=generate(Path(args.source_dat),Path(args.output_dat),Path(args.sld_x1),Path(args.sld_x2),Path(args.color_sld_x1),Path(args.color_sld_x2),Path(args.front_sld_x1),Path(args.front_sld_x2),Path(args.debug_sld_x1),Path(args.debug_sld_x2)); Path(args.report).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
