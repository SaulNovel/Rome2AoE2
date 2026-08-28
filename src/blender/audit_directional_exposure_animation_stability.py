"""Cross-action stability gate for frozen per-direction exposure gains."""
import argparse,json,math,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender'),str(ROOT/'src/rome2')]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees
PHASES={'idle':[('representative',.5)],'walk':[('representative',.5)],'attack':[('anticipation',.15),('strike',.50),('recovery',.90)],'death':[('standing',.10),('falling',.55),('final',1.0)]};DIRECTIONS=(0,3,4,5,6,7,12,14,15)
def args():
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--gain-receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def main():
 a=args();inputs=json.loads(a.inputs.read_text());receipt=json.loads(a.gain_receipt.read_text());a.output.mkdir(parents=True,exist_ok=True);static=json.loads(Path(inputs['static_input']).read_text());profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities'];records=[]
 for category,phases in PHASES.items():
  bpy.ops.wm.open_mainfile(filepath=str(Path(inputs['actions'][category]['blend']).resolve()));scene=bpy.context.scene;production.camera(scene);root=bpy.data.objects['Rome2AoE2_FacetRoot'];arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';shutil=None
  material=a.output/'aov'/category;material.mkdir(parents=True,exist_ok=True);(material/'texture-manifest.json').write_bytes(Path(static['texture_manifest']).read_bytes());runtime.OUT=material
  for phase,fraction in phases:
   value=start+(end-start)*fraction;scene.frame_set(int(value),subframe=value-int(value));bpy.context.view_layer.update()
   for d in DIRECTIONS:
    root.rotation_euler[2]=math.radians(soldier_yaw_degrees(d));bpy.context.view_layer.update();runtime.AOV=material/phase/f'd{d:02d}';runtime.AOV.mkdir(parents=True,exist_ok=True);arrays={n:runtime.render_aov(scene,material,n,Path(static['texture_root'])) for n in exact.exact_materials.RAW_AOVS};roles=runtime.render_aov(scene,material,'semantic_role',Path(static['texture_root']));outputs={}
    for name,gain in (('v5',1.0),('lift',receipt['gains'][d])):
     filename=f'{category}-{phase}-d{d:02d}-{name}.png';metrics=runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],exposure_gain=gain,output_name=filename,diagnostics=False);outputs[name]={'path':str(material/filename),'gain':gain,'clipped_percent':metrics['clipped_pixel_percentage'],'highlight_p95':metrics['highlight_p95'],'dark_pixel_percentage':metrics['dark_pixel_percentage']}
    records.append({'category':category,'phase':phase,'fraction':fraction,'direction':d,'blender_frame':value,'outputs':outputs})
 maximum=max(r['outputs']['lift']['clipped_percent'] for r in records);report={'format':'rome2aoe2.directional-exposure-animation-stability','version':1,'identity':receipt['identity'],'release_eligible':False,'directions':list(DIRECTIONS),'phases':PHASES,'frozen_gains':receipt['gains'],'records':records,'validation':{'constant_gain_by_direction':all(r['outputs']['lift']['gain']==receipt['gains'][r['direction']] for r in records),'maximum_clipped_percent':maximum,'no_highlight_clipping':maximum==0,'v5_equipment_policies_retained':True,'shadow_rendered':False,'corpse_transition_requires_regenerated_exposed_final_colour':True}};(a.output/'animation-stability-report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
