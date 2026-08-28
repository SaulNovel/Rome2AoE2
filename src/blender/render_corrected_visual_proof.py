"""Render a small v2 lighting/attachment proof without touching production v1."""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"src/blender"),str(ROOT/"src/rome2")]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees

def main():
 p=argparse.ArgumentParser();p.add_argument("--input",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args(sys.argv[sys.argv.index("--")+1:]);spec=json.loads(a.input.read_text());a.output.mkdir(parents=True,exist_ok=True)
 doc=json.loads(Path(spec["static_input"]).read_text());shutil.copyfile(doc["texture_manifest"],a.output/"texture-manifest.json");records=[]
 for item in spec["scenes"]:
  bpy.ops.wm.open_mainfile(filepath=str(Path(item["blend"]).resolve()));scene=bpy.context.scene;production.camera(scene);runtime.RESOLUTION=400
  scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format="OPEN_EXR";scene.render.image_settings.color_mode="RGBA";scene.render.image_settings.color_depth="32";scene.render.image_settings.exr_codec="ZIP"
  weapon=next(o for o in scene.objects if o.type=="MESH" and o.get("manifest_component")=="melee_weapon");weapon.matrix_basis=Matrix(spec["weapon_full_frame_local_transform"])
  arm=next(o for o in scene.objects if o.type=="ARMATURE");start,end=arm.animation_data.action.frame_range
  phases=item["phases"]
  for phase in phases:
   value=start+(end-start)*phase;whole=int(value);scene.frame_set(whole,subframe=value-whole)
   for direction in (0,4,8,12):
    bpy.data.objects["Rome2AoE2_FacetRoot"].rotation_euler[2]=math.radians(soldier_yaw_degrees(direction));bpy.context.view_layer.update();work=a.output/"aov"/item["category"]/f"p{phase:.3f}-d{direction:02d}";work.mkdir(parents=True,exist_ok=True);runtime.OUT=a.output;runtime.AOV=work
    arrays={name:runtime.render_aov(scene,a.output,name,Path(doc["texture_root"])) for name in exact.exact_materials.RAW_AOVS};name=f"{item['category']}-phase-{phase:.3f}-direction-{direction:02d}.png"
    metrics=runtime.shade(scene,arrays,readability_fill=spec["readability_fill"],output_name=name,diagnostics=False);records.append({"category":item["category"],"phase":phase,"direction":direction,"output":str(a.output/name),"metrics":metrics})
 (a.output/"corrected-proof.json").write_text(json.dumps({"format":"rome2aoe2.corrected-visual-proof","version":1,"production_profile":"aoe2-infantry-animation-production-v2-provisional","readability_fill":spec["readability_fill"],"weapon_capability":"one_handed_blade_v2_full_source_frame","shadow_modified":False,"production_v1_overwritten":False,"records":records},indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
