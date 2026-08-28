"""Rollback-safe FAST/x2 camera-facing frontal studio-light diagnostic."""
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
COMPONENTS=('body','armour','helmet','crest','shield','melee_weapon');AXIS=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float32)
def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--source-aov-root',type=Path,required=True);p.add_argument('--diffuse-aov-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sample-fraction',type=float,default=.5);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def arrays_at(a,d):
 x={n:np.load(a.source_aov_root/f'direction-{d:02d}'/f'{n}.npy') for n in exact.exact_materials.RAW_AOVS};x['diffuse_raw']=np.load(a.diffuse_aov_root/f'direction-{d:02d}'/'diffuse_raw.npy');return x
def direction(azimuth,elevation):
 e=math.radians(elevation);a=math.radians(azimuth);return np.array((math.cos(e)*math.cos(a),math.cos(e)*math.sin(a),math.sin(e)),np.float32)
def set_key(blender_direction):runtime.SUN_DIRECTION_R2[:]=-(AXIS.T@blender_direction)
def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);doc=json.loads(a.static_input.read_text());shutil.copyfile(doc['texture_manifest'],a.output/'texture-manifest.json');bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);root=bpy.data.objects['Rome2AoE2_FacetRoot'];arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;sample=start+(end-start)*a.sample_fraction;scene.frame_set(int(sample),subframe=sample-int(sample))
 runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';texture_root=Path(doc['texture_root']);profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities']
 original=runtime.SUN_DIRECTION_R2.copy();V=np.array(scene.camera.matrix_world.to_quaternion()@Vector((0,0,1)),np.float32);V/=np.linalg.norm(V);az=math.degrees(math.atan2(V[1],V[0]));camera_elevation=math.degrees(math.asin(V[2]));moderate=35.0
 variants={'v5-control':None,'exact-frontal':[(V,1.0)],'front-moderate-elevation':[(direction(az,moderate),1.0)],'broad-frontal-studio':[(direction(az+da,moderate+de),w) for da,de,w in ((-18,-7,.08),(-18,7,.08),(0,-7,.13),(0,0,.42),(0,7,.13),(18,-7,.08),(18,7,.08))]};records=[]
 for d in range(16):
  yaw=soldier_yaw_degrees(d);root.rotation_euler[2]=math.radians(yaw);bpy.context.view_layer.update();arrays=arrays_at(a,d);roles=np.load(a.source_aov_root/f'direction-{d:02d}'/'semantic_role.npy');active=arrays['diffuse_raw'][...,3]>.001;runtime.OUT=a.output;runtime.AOV=a.output/'component-aov'/f'direction-{d:02d}';runtime.AOV.mkdir(parents=True,exist_ok=True);masks={'whole_unit':active}
  for c in COMPONENTS:masks[c]=prior.component_mask(scene,texture_root,c)&active
  masks['shield']=(roles[...,0]>.5)&active;masks['melee_weapon']=(roles[...,1]>.5)&(roles[...,0]<.5)&active
  for name,samples in variants.items():
   path=a.output/f'{name}-d{d:02d}.png'
   if samples is None:
    set_key(AXIS@(-original));runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=path.name,diagnostics=False)
   elif len(samples)==1:
    set_key(samples[0][0]);runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=path.name,diagnostics=False)
   else:
    images=[]
    for i,(key,weight) in enumerate(samples):
     set_key(key);tmp=a.output/f'.broad-{i}-d{d:02d}.png';runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=tmp.name,diagnostics=False);images.append((prior.rgba(tmp),weight));tmp.unlink()
    blended=sum(im*w for im,w in images);blended[...,3]=images[0][0][...,3];runtime.png_rgba(path,blended)
   image=prior.rgba(path);records.append({'candidate':name,'direction':d,'yaw':yaw,'output':str(path),'metrics':{k:prior.stats(image,v) for k,v in masks.items()}})
 runtime.SUN_DIRECTION_R2[:]=original;pairs=[]
 for name in variants:
  by={r['direction']:r for r in records if r['candidate']==name}
  for d in range(8):
   values={}
   for k in by[d]['metrics']:
    x=by[d]['metrics'][k]['mean'];y=by[d+8]['metrics'][k]['mean'];values[k]={'first':x,'opposite':y,'relative_difference':None if x is None or y is None or x+y==0 else (y-x)/((x+y)/2)}
   pairs.append({'candidate':name,'pair':[d,d+8],'metrics':values})
 summary={}
 for name in variants:
  rows=[r for r in records if r['candidate']==name];ps=[p for p in pairs if p['candidate']==name];summary[name]={'component_mean_luminance':{k:float(np.mean([r['metrics'][k]['mean'] for r in rows if r['metrics'][k]['mean'] is not None])) for k in ('whole_unit',)+COMPONENTS},'component_mean_abs_opposite_pair_imbalance':{k:float(np.mean([abs(p['metrics'][k]['relative_difference']) for p in ps if p['metrics'][k]['relative_difference'] is not None])) for k in ('whole_unit',)+COMPONENTS},'d2_d6_whole_unit_mean':float(np.mean([r['metrics']['whole_unit']['mean'] for r in rows if 2<=r['direction']<=6])),'d10_d14_whole_unit_mean':float(np.mean([r['metrics']['whole_unit']['mean'] for r in rows if 10<=r['direction']<=14]))}
 report={'format':'rome2aoe2.camera-facing-frontal-studio-audit','version':1,'release_eligible':False,'profile':profile['name'],'scale':'FAST/x2 diagnostic only','pose':{'category':'idle','sample_fraction':a.sample_fraction,'blender_frame':sample},'camera':{'direction':V.tolist(),'horizontal_azimuth_degrees':az,'elevation_degrees':camera_elevation},'variants':{'v5-control':'unchanged V5 side-biased key','exact-frontal':f'key parallel to camera direction; elevation {camera_elevation:.6f} degrees','front-moderate-elevation':f'horizontally camera-centered; elevation {moderate} degrees','broad-frontal-studio':f'seven front-facing samples spanning +/-18 degrees azimuth and {moderate-7}..{moderate+7} degrees elevation; normalized weights; display-domain soft-source approximation'},'broad_weights_sum':sum(w for _,w in variants['broad-frontal-studio']),'invariants':{'camera':'fixed','FacetRoot':'production mapping unchanged','directions':16,'materials':'unchanged V5 pipeline','shield':'V4 policy unchanged','weapon':'V5 policy unchanged','environment':'unchanged and world-fixed','scale':'400x400 x2','animation':'single frozen idle pose','directional_exposure_compensation':False,'production_assets_modified':False},'summary':summary,'records':records,'opposite_pairs':pairs};(a.output/'camera-facing-studio-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
