"""Render frozen native-basis Actions into deterministic AoE2 production frames."""
import argparse, hashlib, json, math, shutil, sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"src/blender"),str(ROOT/"src/rome2")]
import assemble_manifest_static as exact
from aoe2.facet_mapping import soldier_yaw_degrees
from downsample_rgba import downsample_rgba
from rome2aoe2.errors import ConverterError
from rome2aoe2.render_modes import sample_positions
from rome2aoe2.visual_scale import (CANONICAL_ORTHOGRAPHIC_SCALE,
                                    VISUAL_SCALE_MAX, VISUAL_SCALE_MIN,
                                    confirm_canvas_bounds,
                                    effective_orthographic_scale,
                                    outside_alpha_metrics, overscan_camera,
                                    validate_canvas_bounds, validate_visual_scale)

SCALE=CANONICAL_ORTHOGRAPHIC_SCALE; TARGET_Z=0.8503072261810303; MASTER=800
DIRECTIONS=[(292.5-22.5*i)%360 for i in range(16)]

def args():
 p=argparse.ArgumentParser();p.add_argument("--input-blend",type=Path,required=True);p.add_argument("--static-input",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--category",required=True);p.add_argument("--manifest-hash",required=True);p.add_argument("--animation-asset",required=True);p.add_argument("--source-samples",type=int,required=True);p.add_argument("--source-fps",type=float,required=True);p.add_argument("--action-fingerprint",required=True);p.add_argument("--directions",default="all");p.add_argument("--profile-name",default="aoe2-infantry-animation-production-v1");p.add_argument("--visual-scale",type=float,default=1.0);p.add_argument("--render-mode",choices=("full","fast"),default="full");p.add_argument("--looping",type=int,choices=(0,1),default=0);return p.parse_args(sys.argv[sys.argv.index("--")+1:])
def production_profile(name):
 if name=="aoe2-infantry-animation-production-v1":return {"name":name,"main_illumination":{"captured_environment_yaw_degrees":0.0,"readability_fill_linear":0.0}}
 path=ROOT/"config/render_profiles"/f"{name.replace('-','_')}.json"
 if not path.is_file():raise RuntimeError(f"unknown production profile: {name}")
 profile=json.loads(path.read_text(encoding="utf-8"))
 if profile.get("name")!=name:raise RuntimeError("production profile identity mismatch")
 return profile
def curves(action):
 return list(action.fcurves) if hasattr(action,"fcurves") else [c for l in action.layers for s in l.strips for b in s.channelbags for c in b.fcurves]
def fingerprint(action):
 payload=sorted((c.data_path,c.array_index,[(float(p.co[0]),float(p.co[1]),p.interpolation) for p in c.keyframe_points]) for c in curves(action));return hashlib.sha256(json.dumps(payload,separators=(",",":")).encode()).hexdigest()
def frame(scene,value):
 whole=int(value);scene.frame_set(whole,subframe=value-whole);bpy.context.view_layer.update()
def camera(scene,visual_scale=1.0,canonical_scale=SCALE):
 for o in list(scene.objects):
  if o.type in {"CAMERA","LIGHT"}:bpy.data.objects.remove(o,do_unlink=True)
 data=bpy.data.cameras.new("AoE2ProductionCamera");data.type="ORTHO";data.ortho_scale=effective_orthographic_scale(visual_scale,canonical_scale)
 cam=bpy.data.objects.new("AoE2ProductionCamera",data);scene.collection.objects.link(cam);scene.camera=cam
 az=math.radians(112.5);el=math.radians(18);target=Vector((0,0,TARGET_Z));distance=18
 cam.location=target+Vector((distance*math.cos(el)*math.cos(az),distance*math.cos(el)*math.sin(az),distance*math.sin(el)));cam.rotation_euler=(target-cam.location).to_track_quat("-Z","Y").to_euler()
def reduce(source,dest,size):
 im=bpy.data.images.load(str(source.resolve()),check_existing=False);values=list(im.pixels);outvals=downsample_rgba(values,im.size[0],im.size[1],size,size,"bicubic");out=bpy.data.images.new("ProductionReduced",size,size,alpha=True);out.alpha_mode="STRAIGHT";out.pixels.foreach_set(outvals);out.file_format="PNG";out.filepath_raw=str(dest.resolve());out.save();bpy.data.images.remove(out);bpy.data.images.remove(im)
def bounds(path):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);w,h=im.size;a=list(im.pixels)[3::4];pts=[(i%w,h-1-i//w) for i,v in enumerate(a) if v>0.0];bpy.data.images.remove(im);return None if not pts else [min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts)+1,max(y for x,y in pts)+1]
def alpha_top_down(path):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);w,h=im.size;a=list(im.pixels)[3::4];bpy.data.images.remove(im);return w,h,[a[(h-1-y)*w+x] for y in range(h) for x in range(w)]
def confirm_edge(scene,doc,a,illumination,stem,visual_scale,effective_scale,master_bounds,direction,ordinal,shield_readability=None,weapon_readability=None):
 spec=overscan_camera([MASTER,MASTER],effective_scale);validation=a.output_root/"validation/overscan/main/master"/stem;original_ortho=scene.camera.data.ortho_scale
 try:
  scene.camera.data.ortho_scale=spec["orthographic_scale"]
  exact.exact_render(scene,doc,validation.parent,validation.name,spec["resolution"][1],environment_yaw_degrees=illumination["captured_environment_yaw_degrees"],readability_fill=illumination["readability_fill_linear"],shield_readability=shield_readability,weapon_readability=weapon_readability)
 finally:
  scene.camera.data.ortho_scale=original_ortho
 w,h,alpha=alpha_top_down(validation);outside=outside_alpha_metrics(alpha,[w,h],spec["production_crop"])
 return confirm_canvas_bounds(visual_scale,a.category,direction,ordinal,"main",master_bounds,[MASTER,MASTER],spec,outside)
def main():
 a=args();visual_scale=validate_visual_scale(a.visual_scale);profile=production_profile(a.profile_name);canonical_scale=float(profile.get("camera",{}).get("orthographic_scale",SCALE));effective_scale=effective_orthographic_scale(visual_scale,canonical_scale);illumination=profile["main_illumination"];shield_readability=profile.get("render_capabilities",{}).get("shield_readability");weapon_readability=profile.get("render_capabilities",{}).get("weapon_readability");doc=json.loads(a.static_input.read_text());bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=="ARMATURE"]
 if len(arms)!=1 or len(arms[0].data.bones)!=50:raise RuntimeError("production requires one 50-bone native armature")
 arm=arms[0];action=arm.animation_data.action;before=fingerprint(action)
 if before!=a.action_fingerprint:raise RuntimeError("frozen Action fingerprint mismatch")
 root=bpy.data.objects.get("Rome2AoE2_FacetRoot")
 if root is None:raise RuntimeError("native production FacetRoot missing")
 camera(scene,visual_scale,canonical_scale);start,end=action.frame_range;samples=sample_positions(start,end,a.source_samples,a.source_fps,bool(a.looping),a.render_mode)
 material_root=a.output_root/("main/master" if a.render_mode=="full" else "main/x2");material_root.mkdir(parents=True,exist_ok=True);shutil.copyfile(doc["texture_manifest"],material_root/"texture-manifest.json")
 records=[];a.output_root.mkdir(parents=True,exist_ok=True)
 directions=list(range(16)) if a.directions=="all" else [int(v) for v in a.directions.split(",")]
 for direction in directions:
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(direction))
  for ordinal,value in enumerate(samples):
   frame(scene,value);stem=f"{a.category}-direction-{direction:02d}-frame-{ordinal:03d}.png";master=a.output_root/"main/master"/stem;x1=a.output_root/"main/x1"/stem;x2=a.output_root/"main/x2"/stem
   if a.render_mode=="full":x1.parent.mkdir(parents=True,exist_ok=True)
   x2.parent.mkdir(parents=True,exist_ok=True);master.parent.mkdir(parents=True,exist_ok=True)
   if a.render_mode=="fast":
    master=x2
    if not x2.is_file():exact.exact_render(scene,doc,x2.parent,stem,400,environment_yaw_degrees=illumination["captured_environment_yaw_degrees"],readability_fill=illumination["readability_fill_linear"],shield_readability=shield_readability,weapon_readability=weapon_readability)
   elif not master.is_file() or not x1.is_file() or not x2.is_file():exact.exact_render(scene,doc,master.parent,stem,MASTER,environment_yaw_degrees=illumination["captured_environment_yaw_degrees"],readability_fill=illumination["readability_fill_linear"],shield_readability=shield_readability,weapon_readability=weapon_readability);reduce(master,x2,400);reduce(master,x1,200)
   master_bounds=bounds(master);b1,b2=(bounds(x1) if a.render_mode=="full" else None),bounds(x2)
   if (a.render_mode=="full" and b1 is None) or b2 is None:raise RuntimeError("unexpected empty production frame")
   canvas_validation=validate_canvas_bounds(visual_scale,a.category,direction,ordinal,master_bounds,[MASTER,MASTER])
   try:
    if canvas_validation["edge_contact"]:canvas_validation=confirm_edge(scene,doc,a,illumination,stem,visual_scale,effective_scale,master_bounds,direction,ordinal,shield_readability,weapon_readability)
   except ConverterError as error:
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({"failure":error.as_dict()},indent=2,sort_keys=True)+"\n");raise
   records.append({"direction":direction,"direction_yaw":DIRECTIONS[direction],"output_frame":ordinal,"source_sample":ordinal,"blender_frame":value,"main_master":str(master),"main_x1":str(x1),"main_x2":str(x2),"master_bounds":master_bounds,"x1_bounds":b1,"x2_bounds":b2,"canvas_validation":canvas_validation})
   print(json.dumps({"category":a.category,"direction":direction,"frame":ordinal}))
 after=fingerprint(action)
 if after!=before:raise RuntimeError("native Action changed during production render")
 edge_contacts=sum(1 for record in records if record["canvas_validation"]["edge_contact"]);overscan_count=sum(1 for record in records if record["canvas_validation"]["overscan_performed"])
 report={"format":"rome2aoe2.native-production-render","version":1,"manifest_hash":a.manifest_hash,"category":a.category,"animation_asset":a.animation_asset,"action":action.name,"action_fingerprint_before":before,"action_fingerprint_after":after,"action_preserved":before==after,"native_source_samples":a.source_samples,"native_fps":a.source_fps,"action_frame_range":[start,end],"rendered_sample_mapping":[{"source_sample":i,"blender_frame":v} for i,v in enumerate(samples)],"direction_order":directions,"direction_yaws":[DIRECTIONS[i] for i in directions],"direction_policy":"fixed camera; rotate Rome2AoE2_FacetRoot","profile":profile["name"],"main_illumination":illumination,"visual_scale":visual_scale,"visual_scale_min":VISUAL_SCALE_MIN,"visual_scale_max":VISUAL_SCALE_MAX,"canonical_orthographic_scale":canonical_scale,"effective_orthographic_scale":effective_scale,"orthographic_scale":effective_scale,"camera_target_z":TARGET_Z,"canvas":{"master":[800,800],"x2":[400,400],"x1":[200,200]},"hotspot_policy":{"x1":[100,122],"x2":[200,244],"ground_anchor":"unchanged"},"x1_dimensions":[200,200],"x2_dimensions":[400,400],"material_backend":"rome2_exact_material_backend/runtime_material_preparation/frozen captured runtime display","shadow_profile":"fixed-global-cast-shadow-v1","records":records,"validation":{"armature_count":1,"bone_count":50,"no_empty_main_frames":True,"constant_canvas":True,"constant_visual_scale":True,"edge_contact_count":edge_contacts,"overscan_count":overscan_count,"confirmed_overflow_count":0,"canvas_overflow":False,"x1_x2_frame_parity":True,"action_preserved":before==after}}
 report.update({"render_mode":a.render_mode,"release_eligible":a.render_mode=="full","render_resolution":MASTER if a.render_mode=="full" else 400,"output_scales":["x1","x2"] if a.render_mode=="full" else ["x2"],"native_source_samples":a.source_samples,"rendered_sample_count":len(samples),"source_duration_seconds":(a.source_samples-1)/a.source_fps,"rendered_duration_seconds":(a.source_samples-1)/a.source_fps,"effective_render_fps":(len(samples)-1)/((a.source_samples-1)/a.source_fps) if a.source_samples>1 else a.source_fps});report["canvas"]={"master":[800,800],"x2":[400,400],"x1":[200,200]} if a.render_mode=="full" else {"x2":[400,400]};report["validation"]["x1_omitted"]=a.render_mode=="fast"
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
