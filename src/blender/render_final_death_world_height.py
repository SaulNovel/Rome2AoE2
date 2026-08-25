"""Render one float world-height AOV for each selected final-death facing."""
import argparse,json,math,sys
from array import array
from pathlib import Path
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender')]
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees
def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--static-report',type=Path,required=True);p.add_argument('--source-report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--directions',default='all');return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def height_shader(texture_root,texture_base,ground_z):
 runtime.build_pass(texture_root,'diffuse_raw',texture_base)
 for mat in bpy.data.materials:
  if not mat.use_nodes:continue
  emissions=[n for n in mat.node_tree.nodes if n.bl_idname=='ShaderNodeEmission']
  if not emissions:continue
  node=emissions[0]
  for link in list(node.inputs['Color'].links):mat.node_tree.links.remove(link)
  geo=mat.node_tree.nodes.new('ShaderNodeNewGeometry');sep=mat.node_tree.nodes.new('ShaderNodeSeparateXYZ');sub=mat.node_tree.nodes.new('ShaderNodeMath');sub.operation='SUBTRACT';sub.inputs[1].default_value=ground_z-2.0;mat.node_tree.links.new(geo.outputs['Position'],sep.inputs[0]);mat.node_tree.links.new(sep.outputs['Z'],sub.inputs[0]);mat.node_tree.links.new(sub.outputs[0],node.inputs['Color'])
def main():
 a=args();static=json.loads(a.static_input.read_text());sr=json.loads(a.static_report.read_text());source=json.loads(a.source_report.read_text());ground_z=float(sr['studio']['ground_z']);bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene,1.0,float(source['canonical_orthographic_scale']));scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
 old=bpy.data.objects.get('conversion_ground')
 if old is not None:old.hide_render=True
 arm=[o for o in scene.objects if o.type=='ARMATURE'][0];action=arm.animation_data.action;production.frame(scene,float(action.frame_range[1]));root=bpy.data.objects.get('Rome2AoE2_FacetRoot');height_shader(Path(static['texture_manifest']).parent,Path(static['texture_root']),ground_z);p0=world_to_camera_view(scene,scene.camera,Vector((0,0,ground_z)));p1=world_to_camera_view(scene,scene.camera,Vector((0,0,ground_z-1)));vector=((p1.x-p0.x)*400,-(p1.y-p0.y)*400);ppw=math.hypot(*vector);directions=range(16) if a.directions=='all' else [int(x) for x in a.directions.split(',')];a.output.mkdir(parents=True,exist_ok=True);rows=[]
 depsgraph=bpy.context.evaluated_depsgraph_get();maximum_world_z=ground_z
 for obj in scene.objects:
  if obj.type!='MESH' or obj==old:continue
  evaluated=obj.evaluated_get(depsgraph);mesh=evaluated.to_mesh()
  try:maximum_world_z=max(maximum_world_z,max((evaluated.matrix_world@vertex.co).z for vertex in mesh.vertices))
  finally:evaluated.to_mesh_clear()
 for direction in directions:
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(direction));bpy.context.view_layer.update();exr=(a.output/f'world-height-direction-{direction:02d}.exr').resolve();scene.render.filepath=str(exr);bpy.ops.render.render(write_still=True);im=bpy.data.images.load(str(exr),check_existing=False);rgba=array('f',[0.0])*len(im.pixels);im.pixels.foreach_get(rgba);bpy.data.images.remove(im);height=array('f',[float('nan')])*(400*400);visible=[]
  for y in range(400):
   source_y=399-y
   for x in range(400):
    source=(source_y*400+x)*4;target=y*400+x
    if rgba[source+3]>0:height[target]=rgba[source]-2.0;visible.append(height[target])
  hp=a.output/f'world-height-direction-{direction:02d}.f32'
  with hp.open('wb') as stream:height.tofile(stream)
  rows.append({'direction':direction,'exr':str(exr),'height_f32':str(hp),'visible_height_min':min(visible),'visible_height_max':max(visible),'visible_pixels':len(visible)})
 max_visible=max(r['visible_height_max'] for r in rows);margin=.01;maximum_height=maximum_world_z-ground_z;sink=maximum_height+margin;report={'format':'rome2aoe2.final-death-world-height-aov','version':2,'representation':'Lossless ZIP OpenEXR RGBA float32 encodes (world Z - resolved ground Z + 2) in RGB and alpha-tested front-surface coverage in A; row-major decoded float32 .f32 caches store height above resolved ground with NaN background.','ground':{'world_z':ground_z,'source_report':str(a.static_report),'hard_coded':False},'source':{'colour_report':str(a.source_report),'input_blend':str(a.input_blend),'action':action.name,'final_action_frame':float(action.frame_range[1]),'colour_rendered':False},'camera':{'orthographic_scale':scene.camera.data.ortho_scale,'resolution':[400,400],'negative_world_z_screen_vector_x2':vector,'pixels_per_world_z_x2':ppw},'geometry':{'maximum_final_pose_world_z':maximum_world_z,'maximum_height_above_ground':maximum_height,'maximum_visible_aov_height_above_ground':max_visible,'safety_margin_world':margin,'required_world_sink':sink,'projected_x2_travel':sink*ppw},'directions':rows,'render_count':len(rows),'passes_per_direction':1,'asset_specific_rules':False};(a.output/'world-height-aov-report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
