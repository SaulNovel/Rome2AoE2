"""FAST/x2 fixed-unit orbit-camera and coherent studio-rig diagnostic."""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender'),str(ROOT/'src/rome2')]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
import audit_whole_unit_opposite_lighting as prior
from aoe2.facet_mapping import soldier_yaw_degrees
COMPONENTS=('body','armour','helmet','crest','shield','melee_weapon')
def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--production-alpha-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sample-fraction',type=float,default=.5);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def silhouette(reference,candidate):
 a=reference>.001;b=candidate>.001;inter=np.count_nonzero(a&b);union=np.count_nonzero(a|b);diff=a^b
 def geom(mask):
  ys,xs=np.where(mask);return {'bbox':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)],'centroid':[float(xs.mean()),float(ys.mean())],'pixels':int(len(xs))}
 ga=geom(a);gb=geom(b);return {'intersection_over_union':float(inter/union),'reference':ga,'orbit':gb,'centroid_difference':[gb['centroid'][0]-ga['centroid'][0],gb['centroid'][1]-ga['centroid'][1]],'discrepant_pixels':int(np.count_nonzero(diff)),'discrepancy_percent_of_union':float(100*np.count_nonzero(diff)/union),'maximum_binary_discrepancy':int(diff.max())}
def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);doc=json.loads(a.static_input.read_text());shutil.copyfile(doc['texture_manifest'],a.output/'texture-manifest.json');bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);bpy.context.view_layer.update();camera=scene.camera;base_camera=camera.matrix_world.copy();root=bpy.data.objects['Rome2AoE2_FacetRoot'];root.rotation_euler[2]=0;arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;sample=start+(end-start)*a.sample_fraction;scene.frame_set(int(sample),subframe=sample-int(sample));runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';texture_root=Path(doc['texture_root']);profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities'];records=[];silhouettes=[]
 for d in range(16):
  theta=math.radians(soldier_yaw_degrees(d));orbit=Matrix.Rotation(-theta,4,'Z');camera.matrix_world=orbit@base_camera;root.rotation_euler[2]=0;bpy.context.view_layer.update();work=a.output/'aov'/f'direction-{d:02d}';runtime.OUT=a.output;runtime.AOV=work;work.mkdir(parents=True,exist_ok=True);arrays={n:runtime.render_aov(scene,a.output,n,texture_root) for n in exact.exact_materials.RAW_AOVS};roles=runtime.render_aov(scene,a.output,'semantic_role',texture_root);active=arrays['diffuse_raw'][...,3]>.001;reference=np.load(a.production_alpha_root/f'direction-{d:02d}'/'diffuse_raw.npy')[...,3];proof=silhouette(reference,arrays['diffuse_raw'][...,3]);proof.update({'direction':d,'facet_yaw_degrees':math.degrees(theta),'camera_orbit_degrees':-math.degrees(theta)});silhouettes.append(proof)
  if proof['intersection_over_union']<.999 or proof['discrepant_pixels']>8:raise RuntimeError(f'orbit camera silhouette mismatch D{d}: {proof}')
  masks={'whole_unit':active}
  for c in COMPONENTS:masks[c]=prior.component_mask(scene,texture_root,c)&active
  masks['shield']=(roles[...,0]>.5)&active;masks['melee_weapon']=(roles[...,1]>.5)&(roles[...,0]<.5)&active
  variants={'orbit-camera-key':{'key':-math.degrees(theta),'environment':0.0},'orbit-full-studio':{'key':-math.degrees(theta),'environment':-math.degrees(theta)}}
  for name,spec in variants.items():
   path=a.output/f'{name}-d{d:02d}.png';metrics=runtime.shade(scene,arrays,environment_yaw_degrees=spec['environment'],key_yaw_offset_degrees=spec['key'],readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=path.name,diagnostics=False,metric_masks=masks);image=prior.rgba(path);records.append({'candidate':name,'direction':d,'yaw':math.degrees(theta),'camera_orbit_degrees':-math.degrees(theta),'output':str(path),'metrics':{k:prior.stats(image,v) for k,v in masks.items()},'shader_metrics':metrics})
 # Reuse the exact freshly regenerated V5 control evidence without rerendering.
 control_report=json.loads((a.production_alpha_root.parent/'shadow-side-complement-audit.json').read_text())
 records.extend({k:v for k,v in r.items() if k!='shader_metrics'} for r in control_report['records'] if r['candidate']=='v5-control')
 pairs=[]
 for name in ('v5-control','orbit-camera-key','orbit-full-studio'):
  by={r['direction']:r for r in records if r['candidate']==name}
  for d in range(8):
   values={}
   for k in by[d]['metrics']:
    x=by[d]['metrics'][k]['mean'];y=by[d+8]['metrics'][k]['mean'];values[k]={'first':x,'opposite':y,'relative_difference':None if x is None or y is None or x+y==0 else (y-x)/((x+y)/2)}
   pairs.append({'candidate':name,'pair':[d,d+8],'metrics':values})
 report={'format':'rome2aoe2.orbit-camera-studio-rig-audit','version':1,'release_eligible':False,'profile':profile['name'],'resolution':[400,400],'pose':{'category':'idle','sample_fraction':a.sample_fraction,'blender_frame':sample,'facet_root_yaw_degrees':0},'matrix_derivation':{'production_view':'C^-1 R(theta) p','required_equivalence':"C_orbit^-1 p = C^-1 R(theta) p",'solution':'C_orbit = R(-theta) C','implementation':'camera.matrix_world = Rz(-theta) @ base_camera.matrix_world','key':'L_orbit = Rz(-theta) L','canonical_theta':'(292.5 - 22.5*i) mod 360'},'variants':{'v5-control':'production fixed camera/light/environment with FacetRoot rotation','orbit-camera-key':'fixed unit; actual camera and dominant key orbit by Rz(-theta); ambient cube and reflection environment remain V5 world-fixed','orbit-full-studio':'fixed unit; actual camera, dominant key, ambient cube, and reflection environment orbit by Rz(-theta)'},'silhouette_validation':silhouettes,'silhouette_pass':all(x['intersection_over_union']>=.999 and x['discrepant_pixels']<=8 for x in silhouettes),'semantic_ownership':{'shield_and_melee_weapon':'frontmost semantic-role AOV','whole_unit':'frontmost alpha','other_components':'isolated silhouette intersected with full alpha; overlap limitation'},'records':records,'opposite_pairs':pairs};(a.output/'orbit-camera-studio-rig-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
