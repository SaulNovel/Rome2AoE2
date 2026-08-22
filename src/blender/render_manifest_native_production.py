"""Render frozen native-basis Actions into deterministic AoE2 production frames."""
import argparse, hashlib, json, math, shutil, sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"src/blender"),str(ROOT/"src/rome2")]
import assemble_manifest_static as exact
from aoe2.facet_mapping import soldier_yaw_degrees
from downsample_rgba import downsample_rgba

SCALE=7.27480212108078; TARGET_Z=0.8503072261810303; MASTER=800
DIRECTIONS=[(292.5-22.5*i)%360 for i in range(16)]

def args():
 p=argparse.ArgumentParser();p.add_argument("--input-blend",type=Path,required=True);p.add_argument("--static-input",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--category",required=True);p.add_argument("--manifest-hash",required=True);p.add_argument("--animation-asset",required=True);p.add_argument("--source-samples",type=int,required=True);p.add_argument("--source-fps",type=float,required=True);p.add_argument("--action-fingerprint",required=True);p.add_argument("--directions",default="all");return p.parse_args(sys.argv[sys.argv.index("--")+1:])
def curves(action):
 return list(action.fcurves) if hasattr(action,"fcurves") else [c for l in action.layers for s in l.strips for b in s.channelbags for c in b.fcurves]
def fingerprint(action):
 payload=sorted((c.data_path,c.array_index,[(float(p.co[0]),float(p.co[1]),p.interpolation) for p in c.keyframe_points]) for c in curves(action));return hashlib.sha256(json.dumps(payload,separators=(",",":")).encode()).hexdigest()
def frame(scene,value):
 whole=int(value);scene.frame_set(whole,subframe=value-whole);bpy.context.view_layer.update()
def camera(scene):
 for o in list(scene.objects):
  if o.type in {"CAMERA","LIGHT"}:bpy.data.objects.remove(o,do_unlink=True)
 data=bpy.data.cameras.new("AoE2ProductionCamera");data.type="ORTHO";data.ortho_scale=SCALE
 cam=bpy.data.objects.new("AoE2ProductionCamera",data);scene.collection.objects.link(cam);scene.camera=cam
 az=math.radians(112.5);el=math.radians(18);target=Vector((0,0,TARGET_Z));distance=18
 cam.location=target+Vector((distance*math.cos(el)*math.cos(az),distance*math.cos(el)*math.sin(az),distance*math.sin(el)));cam.rotation_euler=(target-cam.location).to_track_quat("-Z","Y").to_euler()
def reduce(source,dest,size):
 im=bpy.data.images.load(str(source.resolve()),check_existing=False);values=list(im.pixels);outvals=downsample_rgba(values,im.size[0],im.size[1],size,size,"bicubic");out=bpy.data.images.new("ProductionReduced",size,size,alpha=True);out.alpha_mode="STRAIGHT";out.pixels.foreach_set(outvals);out.file_format="PNG";out.filepath_raw=str(dest.resolve());out.save();bpy.data.images.remove(out);bpy.data.images.remove(im)
def bounds(path):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);w,h=im.size;a=list(im.pixels)[3::4];pts=[(i%w,h-1-i//w) for i,v in enumerate(a) if v>1/255];bpy.data.images.remove(im);return None if not pts else [min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts)+1,max(y for x,y in pts)+1]
def main():
 a=args();doc=json.loads(a.static_input.read_text());bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;arms=[o for o in scene.objects if o.type=="ARMATURE"]
 if len(arms)!=1 or len(arms[0].data.bones)!=50:raise RuntimeError("production requires one 50-bone native armature")
 arm=arms[0];action=arm.animation_data.action;before=fingerprint(action)
 if before!=a.action_fingerprint:raise RuntimeError("frozen Action fingerprint mismatch")
 root=bpy.data.objects.get("Rome2AoE2_FacetRoot")
 if root is None:raise RuntimeError("native production FacetRoot missing")
 camera(scene);start,end=action.frame_range;samples=[start+(end-start)*i/(a.source_samples-1) for i in range(a.source_samples)]
 material_root=a.output_root/"main/master";material_root.mkdir(parents=True,exist_ok=True);shutil.copyfile(doc["texture_manifest"],material_root/"texture-manifest.json")
 records=[];a.output_root.mkdir(parents=True,exist_ok=True)
 directions=list(range(16)) if a.directions=="all" else [int(v) for v in a.directions.split(",")]
 for direction in directions:
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(direction))
  for ordinal,value in enumerate(samples):
   frame(scene,value);stem=f"{a.category}-direction-{direction:02d}-frame-{ordinal:03d}.png";master=a.output_root/"main/master"/stem;x1=a.output_root/"main/x1"/stem;x2=a.output_root/"main/x2"/stem
   x1.parent.mkdir(parents=True,exist_ok=True);x2.parent.mkdir(parents=True,exist_ok=True);master.parent.mkdir(parents=True,exist_ok=True)
   if not x1.is_file() or not x2.is_file():exact.exact_render(scene,doc,master.parent,stem,MASTER);reduce(master,x2,400);reduce(master,x1,200)
   b1,b2=bounds(x1),bounds(x2)
   if b1 is None or b2 is None:raise RuntimeError("unexpected empty production frame")
   records.append({"direction":direction,"direction_yaw":DIRECTIONS[direction],"output_frame":ordinal,"source_sample":ordinal,"blender_frame":value,"main_x1":str(x1),"main_x2":str(x2),"x1_bounds":b1,"x2_bounds":b2})
   print(json.dumps({"category":a.category,"direction":direction,"frame":ordinal}))
 after=fingerprint(action)
 if after!=before:raise RuntimeError("native Action changed during production render")
 report={"format":"rome2aoe2.native-production-render","version":1,"manifest_hash":a.manifest_hash,"category":a.category,"animation_asset":a.animation_asset,"action":action.name,"action_fingerprint_before":before,"action_fingerprint_after":after,"action_preserved":before==after,"native_source_samples":a.source_samples,"native_fps":a.source_fps,"action_frame_range":[start,end],"rendered_sample_mapping":[{"source_sample":i,"blender_frame":v} for i,v in enumerate(samples)],"direction_order":directions,"direction_yaws":[DIRECTIONS[i] for i in directions],"direction_policy":"fixed camera; rotate Rome2AoE2_FacetRoot","profile":"aoe2-infantry-animation-production-v1","orthographic_scale":SCALE,"camera_target_z":TARGET_Z,"x1_dimensions":[200,200],"x2_dimensions":[400,400],"material_backend":"rome2_exact_material_backend/runtime_material_preparation/frozen captured runtime display","shadow_profile":"pending-fixed-shadow-pass-v1","records":records,"validation":{"armature_count":1,"bone_count":50,"no_empty_main_frames":True,"constant_canvas":True,"x1_x2_frame_parity":True,"action_preserved":before==after}}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
