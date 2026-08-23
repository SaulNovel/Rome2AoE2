"""Render the globally fixed AoE cast-shadow pass for a frozen native Action."""
import argparse,json,math,os,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"src"),str(ROOT/"src/blender"),str(ROOT/"src/rome2")]
import render_hastati_runtime_parity as runtime
from aoe2.facet_mapping import soldier_yaw_degrees
from downsample_rgba import downsample_rgba
from render_manifest_native_production import SCALE,TARGET_Z,DIRECTIONS,bounds,camera,frame,fingerprint
from rome2aoe2.errors import ConverterError
from rome2aoe2.visual_scale import (VISUAL_SCALE_MAX, VISUAL_SCALE_MIN,
                                    effective_orthographic_scale,
                                    validate_canvas_bounds, validate_visual_scale)
MASTER=800
def args():
 p=argparse.ArgumentParser();p.add_argument("--input-blend",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--report",type=Path,required=True);p.add_argument("--category",required=True);p.add_argument("--manifest-hash",required=True);p.add_argument("--animation-asset",required=True);p.add_argument("--source-samples",type=int,required=True);p.add_argument("--source-fps",type=float,required=True);p.add_argument("--action-fingerprint",required=True);p.add_argument("--directions",default="all");p.add_argument("--visual-scale",type=float,default=1.0);p.add_argument("--canonical-orthographic-scale",type=float,default=SCALE);return p.parse_args(sys.argv[sys.argv.index("--")+1:])
def array(path):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);v=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(v);r=v.reshape((im.size[1],im.size[0],4))[::-1].copy();bpy.data.images.remove(im);return r
def save(path,rgba):path.parent.mkdir(parents=True,exist_ok=True);runtime.png_rgba(path,rgba.astype(np.float32))
def down(rgba,size):return np.asarray(downsample_rgba(rgba.reshape(-1).tolist(),rgba.shape[1],rgba.shape[0],size,size,"bicubic"),np.float32).reshape((size,size,4))
def setup(scene,meshes):
 scene.render.engine="CYCLES";scene.cycles.samples=24;scene.cycles.use_denoising=True;scene.render.resolution_x=scene.render.resolution_y=MASTER;scene.render.resolution_percentage=100;scene.render.image_settings.file_format="PNG";scene.render.film_transparent=False;scene.display_settings.display_device="sRGB";scene.view_settings.view_transform="Raw";scene.view_settings.look="None";scene.view_settings.exposure=0;scene.view_settings.gamma=1
 world=bpy.data.worlds.new("ProductionShadowWorld");scene.world=world;world.use_nodes=True;world.node_tree.nodes["Background"].inputs["Color"].default_value=(1,1,1,1);world.node_tree.nodes["Background"].inputs["Strength"].default_value=.35
 mat=bpy.data.materials.new("ProductionShadowReceiver");mat.diffuse_color=(1,1,1,1);bpy.ops.mesh.primitive_plane_add(size=30,location=(0,0,-.01));plane=bpy.context.object;plane.data.materials.append(mat)
 opaque=bpy.data.materials.new("ProductionOpaqueCaster");opaque.diffuse_color=(.5,.5,.5,1)
 for m in meshes:m.data.materials.clear();m.data.materials.append(opaque);m.visible_camera=False;m.visible_shadow=True
 axis=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float32);d=axis@(-runtime.SUN_DIRECTION_R2);d/=np.linalg.norm(d);h=d[:2]/np.linalg.norm(d[:2]);e=math.radians(60);ld=np.array((h[0]*math.cos(e),h[1]*math.cos(e),math.sin(e)),np.float32)
 data=bpy.data.lights.new("ProductionFixedShadowKey","AREA");data.energy=900;data.shape="DISK";data.size=3;light=bpy.data.objects.new("ProductionFixedShadowKey",data);light.location=Vector(ld.tolist())*12;light.rotation_euler=(-light.location).to_track_quat("-Z","Y").to_euler();scene.collection.objects.link(light);return d.tolist(),ld.tolist()
def main():
 a=args();visual_scale=validate_visual_scale(a.visual_scale);canonical_scale=float(a.canonical_orthographic_scale);effective_scale=effective_orthographic_scale(visual_scale,canonical_scale);bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;arm=next(o for o in scene.objects if o.type=="ARMATURE");action=arm.animation_data.action;before=fingerprint(action)
 if before!=a.action_fingerprint:raise RuntimeError("shadow Action fingerprint mismatch")
 root=bpy.data.objects.get("Rome2AoE2_FacetRoot");camera(scene,visual_scale,canonical_scale);meshes=[o for o in scene.objects if o.type=="MESH" and not o.hide_render];recovered,light=setup(scene,meshes);raw=a.output_root/f"shadow-raw-{os.getpid()}.png";scene.render.filepath=str(raw.resolve())
 for m in meshes:m.visible_shadow=False
 bpy.ops.render.render(write_still=True);baseline=array(raw);base=baseline[...,:3]@np.array((.2126,.7152,.0722),np.float32)
 for m in meshes:m.visible_shadow=True
 start,end=action.frame_range;samples=[start+(end-start)*i/(a.source_samples-1) for i in range(a.source_samples)];records=[]
 directions=list(range(16)) if a.directions=="all" else [int(v) for v in a.directions.split(",")]
 for direction in directions:
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(direction))
  for ordinal,value in enumerate(samples):
   frame(scene,value);stem=f"{a.category}-direction-{direction:02d}-frame-{ordinal:03d}.png";x1=a.output_root/"shadow/x1"/stem;x2=a.output_root/"shadow/x2"/stem
   if not x1.is_file() or not x2.is_file():
    bpy.ops.render.render(write_still=True);rgba=array(raw);lum=rgba[...,:3]@np.array((.2126,.7152,.0722),np.float32);alpha=np.clip(np.maximum(0,base-lum)/np.maximum(base,1e-5)/.72,0,1)*.38;alpha[alpha<.025]=0;out=np.zeros((*alpha.shape,4),np.float32);out[...,3]=alpha;save(x2,down(out,400));save(x1,down(out,200))
   shadow_bounds=bounds(x2)
   try:validate_canvas_bounds(visual_scale,a.category,direction,ordinal,shadow_bounds,[400,400])
   except ConverterError as error:
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps({"failure":error.as_dict()},indent=2,sort_keys=True)+"\n");raise
   records.append({"direction":direction,"output_frame":ordinal,"source_sample":ordinal,"blender_frame":value,"shadow_x1":str(x1),"shadow_x2":str(x2),"x2_bounds":shadow_bounds})
 after=fingerprint(action);report={"format":"rome2aoe2.native-production-shadow","version":1,"manifest_hash":a.manifest_hash,"category":a.category,"animation_asset":a.animation_asset,"action_fingerprint_before":before,"action_fingerprint_after":after,"action_preserved":before==after,"native_source_samples":a.source_samples,"native_fps":a.source_fps,"direction_order":directions,"direction_yaws":[DIRECTIONS[i] for i in directions],"visual_scale":visual_scale,"visual_scale_min":VISUAL_SCALE_MIN,"visual_scale_max":VISUAL_SCALE_MAX,"canonical_orthographic_scale":canonical_scale,"effective_orthographic_scale":effective_scale,"orthographic_scale":effective_scale,"camera_target_z":TARGET_Z,"canvas":{"x2":[400,400],"x1":[200,200]},"hotspot_policy":{"x1":[100,122],"x2":[200,244],"ground_anchor":"unchanged"},"profile":"fixed-global-cast-shadow-v1","recovered_light_direction":recovered,"fixed_light_direction":light,"records":records,"validation":{"main_shadow_expected_count":len(directions)*a.source_samples,"shadow_count":len(records),"constant_visual_scale":True,"canvas_overflow":False,"action_preserved":before==after}}
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
