"""FAST/x2 V5 diagnostic varying only the world-fixed dominant-key azimuth."""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender'),str(ROOT/'src/rome2')]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
import audit_whole_unit_opposite_lighting as prior
from aoe2.facet_mapping import soldier_yaw_degrees
COMPONENTS=('body','armour','helmet','crest','shield','melee_weapon')

def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--source-aov-root',type=Path,required=True);p.add_argument('--diffuse-aov-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sample-fraction',type=float,default=.5);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def arrays_at(root,diffuse_root,d):
 arrays={n:np.load(root/f'direction-{d:02d}'/f'{n}.npy') for n in exact.exact_materials.RAW_AOVS};arrays['diffuse_raw']=np.load(diffuse_root/f'direction-{d:02d}'/'diffuse_raw.npy');return arrays
def signed(degrees):return (degrees+180)%360-180

def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);doc=json.loads(a.static_input.read_text());shutil.copyfile(doc['texture_manifest'],a.output/'texture-manifest.json')
 bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);root=bpy.data.objects['Rome2AoE2_FacetRoot'];arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;sample=start+(end-start)*a.sample_fraction;scene.frame_set(int(sample),subframe=sample-int(sample))
 runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw'
 texture_root=Path(doc['texture_root']);profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities']
 axis=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float32);L0=axis@(-runtime.SUN_DIRECTION_R2);L0/=np.linalg.norm(L0);V=np.array(scene.camera.matrix_world.to_quaternion()@Vector((0,0,1)),np.float32);V/=np.linalg.norm(V)
 current_az=math.degrees(math.atan2(L0[1],L0[0]));view_az=math.degrees(math.atan2(V[1],V[0]));center=signed(view_az-current_az);weak=center-math.copysign(10,center)
 candidates={'v5-control':0.0,'front-high-intermediate':center*.5,'front-high-weak-offset':weak,'front-high-centered':center};records=[]
 for d in range(16):
  yaw=soldier_yaw_degrees(d);root.rotation_euler[2]=math.radians(yaw);bpy.context.view_layer.update();arrays=arrays_at(a.source_aov_root,a.diffuse_aov_root,d);roles=np.load(a.source_aov_root/f'direction-{d:02d}'/'semantic_role.npy');active=arrays['diffuse_raw'][...,3]>.001
  runtime.OUT=a.output;runtime.AOV=a.output/'component-aov'/f'direction-{d:02d}';runtime.AOV.mkdir(parents=True,exist_ok=True);masks={'whole_unit':active}
  for c in COMPONENTS:masks[c]=prior.component_mask(scene,texture_root,c)&active
  masks['shield']=(roles[...,0]>.5)&active;masks['melee_weapon']=(roles[...,1]>.5)&(roles[...,0]<.5)&active
  for name,offset in candidates.items():
   path=a.output/f'{name}-d{d:02d}.png';shader=runtime.shade(scene,arrays,illumination_yaw_offset_degrees=offset,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=path.name,diagnostics=False,metric_masks=masks);image=prior.rgba(path);records.append({'candidate':name,'direction':d,'yaw':yaw,'key_yaw_offset_degrees':offset,'output':str(path),'metrics':{k:prior.stats(image,v) for k,v in masks.items()},'shader_metrics':shader})
 pairs=[]
 for name in candidates:
  by={r['direction']:r for r in records if r['candidate']==name}
  for d in range(8):
   values={}
   for k in by[d]['metrics']:
    x=by[d]['metrics'][k]['mean'];y=by[d+8]['metrics'][k]['mean'];values[k]={'first':x,'opposite':y,'relative_difference':None if x is None or y is None or x+y==0 else (y-x)/((x+y)/2)}
   pairs.append({'candidate':name,'pair':[d,d+8],'metrics':values})
 summary={name:{'mean_abs_opposite_pair_imbalance':float(np.mean([abs(p['metrics']['whole_unit']['relative_difference']) for p in pairs if p['candidate']==name])),'d2_d6_mean':float(np.mean([r['metrics']['whole_unit']['mean'] for r in records if r['candidate']==name and 2<=r['direction']<=6])),'d10_d14_mean':float(np.mean([r['metrics']['whole_unit']['mean'] for r in records if r['candidate']==name and 10<=r['direction']<=14]))} for name in candidates}
 report={'format':'rome2aoe2.fixed-key-alignment-audit','version':1,'release_eligible':False,'profile':profile['name'],'resolution':[400,400],'scale':'FAST/x2 review only','pose':{'category':'idle','sample_fraction':a.sample_fraction,'blender_frame':sample},'key_geometry':{'current_world_direction':L0.tolist(),'current_horizontal_azimuth_degrees':current_az,'camera_view_direction':V.tolist(),'camera_horizontal_azimuth_degrees':view_az,'elevation_degrees':math.degrees(math.asin(L0[2])),'photometry_changed':False,'elevation_changed':False,'candidate_yaw_offsets_degrees':candidates},'invariants':{'camera':'fixed production camera','unit_rotation':'production FacetRoot yaw mapping','dominant_key':'world-fixed within every 16-direction candidate','ambient_environment':'V5 unchanged and world-fixed','materials':'V5 unchanged','shield_readability':'V4 unchanged','weapon_readability':'V5 unchanged','animation_pose':'single frozen idle sample','scale':'400x400 x2','shadows':'production shadow policy untouched; no shadow assets authored by this main-layer audit'},'semantic_ownership':{'shield_and_melee_weapon':'frontmost semantic-role AOV','whole_unit':'frontmost alpha','other_components':'isolated component silhouette intersected with full alpha; overlap limitation'},'candidates':candidates,'summary':summary,'records':records,'opposite_pairs':pairs}
 (a.output/'fixed-key-alignment-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
