"""Render tiny mask-only final-death ground-plane intersection diagnostics."""
import argparse, json, math, sys
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender')]
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees

def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--static-report',type=Path,required=True);p.add_argument('--source-report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--directions',default='0,6,7,14');return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def main():
 a=args();static=json.loads(a.static_input.read_text());sr=json.loads(a.static_report.read_text());source=json.loads(a.source_report.read_text());ground_z=float(sr['studio']['ground_z']);bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene,1.0,float(source['canonical_orthographic_scale']));scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=False;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='8';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
 arm=[o for o in scene.objects if o.type=='ARMATURE'][0];action=arm.animation_data.action;production.frame(scene,float(action.frame_range[1]));root=bpy.data.objects.get('Rome2AoE2_FacetRoot');base_z=root.location.z
 texture_root=Path(static['texture_manifest']).parent;runtime.build_pass(texture_root,'diffuse_raw',Path(static['texture_root']))
 for mat in bpy.data.materials:
  if mat.use_nodes:
   for node in mat.node_tree.nodes:
    if node.bl_idname=='ShaderNodeEmission':
     for link in list(node.inputs['Color'].links):mat.node_tree.links.remove(link)
     node.inputs['Color'].default_value=(1,1,1,1)
 old=bpy.data.objects.get('conversion_ground')
 if old is not None:bpy.data.objects.remove(old,do_unlink=True)
 bpy.ops.mesh.primitive_plane_add(size=100,location=(0,0,ground_z));plane=bpy.context.object;plane.name='CorpsePhysicalGroundOccluder';pm=bpy.data.materials.new('CorpseGroundMatte');pm.use_nodes=True;pn=pm.node_tree.nodes;pl=pm.node_tree.links;pn.clear();out=pn.new('ShaderNodeOutputMaterial');em=pn.new('ShaderNodeEmission');em.inputs['Color'].default_value=(0,0,0,1);pl.new(em.outputs[0],out.inputs['Surface']);plane.data.materials.append(pm)
 depsgraph=bpy.context.evaluated_depsgraph_get();max_z=ground_z
 for obj in scene.objects:
  if obj.type!='MESH' or obj==plane:continue
  evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
  try:max_z=max(max_z,max((evaluated.matrix_world@v.co).z for v in mesh.vertices))
  finally:evaluated.to_mesh_clear()
 p0=world_to_camera_view(scene,scene.camera,Vector((0,0,ground_z)));p1=world_to_camera_view(scene,scene.camera,Vector((0,0,ground_z-1)));vector=((p1.x-p0.x)*400,-(p1.y-p0.y)*400);ppw=math.hypot(*vector);legacy_world_total=96/ppw;world_total=max_z-ground_z+.01;fractions=(0,.25,.5,.75,1);depths=[world_total*f for f in fractions];a.output.mkdir(parents=True,exist_ok=True);rows=[]
 for direction in [int(x) for x in a.directions.split(',')]:
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(direction))
  for fraction,depth in zip(fractions,depths):
   root.location.z=base_z-depth;bpy.context.view_layer.update();path=(a.output/f'ground-mask-direction-{direction:02d}-sink-{round(fraction*100):03d}.png').resolve();scene.render.filepath=str(path);bpy.ops.render.render(write_still=True);rows.append({'direction':direction,'fraction':fraction,'world_sink':depth,'screen_displacement_x2':[vector[0]*depth,vector[1]*depth],'mask':str(path)})
 root.location.z=base_z
 report={'format':'rome2aoe2.physical-ground-occluder-diagnostic','version':1,'render_type':'mask-only','colour_rendered':False,'input_blend':str(a.input_blend),'action':action.name,'final_action_frame':float(action.frame_range[1]),'ground':{'object':plane.name,'orientation':'world XY / parallel to terrain','world_z':ground_z,'appearance':'black matte occluder; not composited as terrain'},'camera':{'orthographic_scale':scene.camera.data.ortho_scale,'resolution':[400,400],'negative_world_z_screen_vector_x2':vector,'pixels_per_world_z_x2':ppw},'sink':{'evaluated_final_pose_max_world_z':max_z,'required_world_distance':world_total,'safety_margin_world':.01,'derived_screen_travel_x2':world_total*ppw,'legacy_96px_world_distance':legacy_world_total,'legacy_96px_excess_factor':legacy_world_total/world_total,'fractions':fractions,'depths':depths},'directions':[0,6,7,14],'render_count':len(rows),'records':rows,'asset_specific_rules':False}
 (a.output/'physical-ground-occluder-report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
