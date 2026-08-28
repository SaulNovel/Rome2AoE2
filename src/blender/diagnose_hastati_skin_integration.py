"""Render production-input diagnostics for the frozen facet-03 Hastati."""
import json, sys
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/blender'))
import render_hastati_runtime_parity as rp
import render_cross_unit_set_a as cu

OUT=rp.OUT/'skin-integration-audit'; OUT.mkdir(parents=True,exist_ok=True)
ROOT_ASSET=ROOT/'build/local-integration/rome2/cross-unit-calibration/units/hastati'
SKIN_COLOURS={'roman_body1':(1,0,0,1),'roman_1_head':(0,1,1,1)}

def setup_nodes(mode):
 manifest=json.loads((ROOT_ASSET/'texture-manifest.json').read_text());records={m['material_name']:m for m in manifest['materials']}
 maps={n:{t['semantic']:ROOT_ASSET/'textures'/Path(t['extracted_path']) for t in row['textures'] if t['status']=='resolved'} for n,row in records.items()}
 for mat in bpy.data.materials:
  key=mat.name.split('.')[0];row=records.get(key,{});tex=maps.get(key,{});skin=row.get('material_type')=='WeightedSkinDirtmap'
  mat.use_nodes=True;nodes=mat.node_tree.nodes;links=mat.node_tree.links;nodes.clear();out=nodes.new('ShaderNodeOutputMaterial');em=nodes.new('ShaderNodeEmission');links.new(em.outputs[0],out.inputs['Surface'])
  if not skin: em.inputs['Color'].default_value=(0,0,0,1);continue
  if mode=='routing': em.inputs['Color'].default_value=SKIN_COLOURS[key];continue
  if mode=='uv':
   uv=nodes.new('ShaderNodeTexCoord');links.new(uv.outputs['UV'],em.inputs['Color']);continue
  semantic={'raw_diffuse':'Diffuse','raw_normal':'Normal','raw_gloss':'GlossMap','raw_skin_mask':'SkinMask','raw_dirt_mask':'DecalDirtmask','raw_dirt':'DecalDirtmap'}[mode]
  noncolor=semantic not in ('Diffuse','GlossMap');im=rp.image_node(nodes,tex[semantic],noncolor)
  if mode=='raw_dirt':links.new(rp.scaled_uv(nodes,links,4),im.inputs['Vector'])
  if mode in ('raw_normal','raw_dirt','raw_dirt_mask'):
   sep=nodes.new('ShaderNodeSeparateColor');links.new(im.outputs['Color'],sep.inputs['Color']);pack=nodes.new('ShaderNodeCombineColor')
   if mode=='raw_normal':links.new(im.outputs['Alpha'],pack.inputs['Red']);links.new(sep.outputs['Green'],pack.inputs['Green'])
   elif mode=='raw_dirt':links.new(sep.outputs['Red'],pack.inputs['Red']);links.new(sep.outputs['Green'],pack.inputs['Green']);links.new(im.outputs['Alpha'],pack.inputs['Blue'])
   else:links.new(im.outputs['Alpha'],pack.inputs['Red'])
   links.new(pack.outputs['Color'],em.inputs['Color'])
  else:links.new(im.outputs['Color'],em.inputs['Color'])

def render(scene,mode):
 setup_nodes(mode);path=(OUT/f'{mode}.exr').resolve();scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
 im=bpy.data.images.load(str(path),check_existing=False);a=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(a);a=a.reshape((rp.RESOLUTION,rp.RESOLUTION,4))[::-1].copy();bpy.data.images.remove(im);np.save(OUT/f'{mode}.npy',a)
 if mode=='routing':rp.png_rgba(rp.OUT/'debug-skin-family-routing.png',np.clip(a,0,1))

def main():
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit('hastati');cu.configure_camera(bpy.context.scene,rp.FACET_AZIMUTH,30,8.5,12);scene=bpy.context.scene
 scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=scene.render.resolution_y=rp.RESOLUTION;scene.render.resolution_percentage=100;scene.render.film_transparent=True
 scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';scene.view_settings.look='None';scene.view_settings.exposure=0;scene.view_settings.gamma=1
 for mode in ('routing','uv','raw_diffuse','raw_normal','raw_gloss','raw_skin_mask','raw_dirt_mask','raw_dirt'):render(scene,mode)
 routing=np.load(OUT/'routing.npy');counts={'roman_body1':int(np.count_nonzero(routing[...,0]>.5)),'roman_1_head':int(np.count_nonzero(routing[...,1]>.5))}
 (OUT/'routing.json').write_text(json.dumps({'pixel_counts':counts,'colours':SKIN_COLOURS},indent=2)+'\n')
if __name__=='__main__':main()
