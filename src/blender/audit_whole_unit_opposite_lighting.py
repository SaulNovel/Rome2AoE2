"""FAST/x2-only whole-unit opposite-facing lighting audit and candidates."""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender'),str(ROOT/'src/rome2')]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees
LUMA=np.array((.2126,.7152,.0722),np.float32)
COMPONENTS=('body','armour','helmet','crest','shield','melee_weapon')

def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sample-fraction',type=float,default=.5);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def rgba(path):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);data=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(data);out=data.reshape((im.size[1],im.size[0],4))[::-1].copy();bpy.data.images.remove(im);return out
def component_mask(scene,texture_root,component):
 meshes=[o for o in scene.objects if o.type=='MESH'];hidden={o:o.hide_render for o in meshes}
 for o in meshes:o.hide_render=o.get('manifest_component')!=component
 mask=runtime.render_aov(scene,runtime.OUT,'diffuse_raw',texture_root)[...,3]>.001
 for o,v in hidden.items():o.hide_render=v
 return mask
def stats(image,mask):
 active=mask&(image[...,3]>.001);values=(image[...,:3]@LUMA)[active]
 if not len(values):return {'pixels':0,'mean':None,'median':None}
 return {'pixels':int(len(values)),'mean':float(values.mean()),'median':float(np.median(values)),'p10':float(np.percentile(values,10)),'p90':float(np.percentile(values,90))}
def blend(left,right,out,weight):
 a=rgba(left);b=rgba(right);result=a.copy();result[...,:3]=a[...,:3]*(1-weight)+b[...,:3]*weight
 runtime.png_rgba(out,result);return result
def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);doc=json.loads(a.static_input.read_text());shutil.copyfile(doc['texture_manifest'],a.output/'texture-manifest.json');bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);root=bpy.data.objects['Rome2AoE2_FacetRoot'];arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;sample=start+(end-start)*a.sample_fraction;scene.frame_set(int(sample),subframe=sample-int(sample));runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';texture_root=Path(doc['texture_root']);profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities'];records=[]
 candidates={'v5-control':{'fill':.6,'opposite_weight':0},'direction-independent-fill-0.90':{'fill':.9,'opposite_weight':0},'bilateral-key-fill-75-25':{'fill':.6,'opposite_weight':.25},'bilateral-symmetric-50-50':{'fill':.6,'opposite_weight':.5}}
 for d in range(16):
  yaw=soldier_yaw_degrees(d);root.rotation_euler[2]=math.radians(yaw);bpy.context.view_layer.update();work=a.output/'aov'/f'direction-{d:02d}';runtime.OUT=a.output;runtime.AOV=work;work.mkdir(parents=True,exist_ok=True);arrays={n:runtime.render_aov(scene,a.output,n,texture_root) for n in exact.exact_materials.RAW_AOVS};roles=runtime.render_aov(scene,a.output,'semantic_role',texture_root);active=arrays['diffuse_raw'][...,3]>.001;masks={'whole_unit':active}
  for c in COMPONENTS:masks[c]=component_mask(scene,texture_root,c)&active
  masks['shield']=(roles[...,0]>.5)&active;masks['melee_weapon']=(roles[...,1]>.5)&(roles[...,0]<.5)&active
  control=a.output/f'v5-control-d{d:02d}.png';opposite=a.output/f'opposite-illumination-d{d:02d}.png';runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=control.name,diagnostics=False,metric_masks=masks);runtime.shade(scene,arrays,illumination_yaw_offset_degrees=180,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=opposite.name,diagnostics=False)
  for name,spec in candidates.items():
   path=control
   if name=='direction-independent-fill-0.90':path=a.output/f'{name}-d{d:02d}.png';runtime.shade(scene,arrays,readability_fill=spec['fill'],semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],output_name=path.name,diagnostics=False)
   elif spec['opposite_weight']:
    path=a.output/f'{name}-d{d:02d}.png';blend(control,opposite,path,spec['opposite_weight'])
   image=rgba(path);records.append({'candidate':name,'direction':d,'yaw':yaw,'output':str(path),'metrics':{k:stats(image,m) for k,m in masks.items()}})
 pairs=[]
 for name in candidates:
  by={r['direction']:r for r in records if r['candidate']==name}
  for d in range(8):pairs.append({'candidate':name,'left_direction':d,'opposite_direction':d+8,'metrics':{k:{'left':by[d]['metrics'][k]['mean'],'opposite':by[d+8]['metrics'][k]['mean'],'relative_difference':None if not by[d]['metrics'][k]['mean'] or not by[d+8]['metrics'][k]['mean'] else (by[d+8]['metrics'][k]['mean']-by[d]['metrics'][k]['mean'])/((by[d+8]['metrics'][k]['mean']+by[d]['metrics'][k]['mean'])/2)} for k in by[d]['metrics']}})
 report={'format':'rome2aoe2.whole-unit-opposite-lighting-audit','version':1,'release_eligible':False,'profile':profile['name'],'resolution':[400,400],'scale':'FAST/x2 only','pose':{'category':'idle','sample_fraction':a.sample_fraction,'blender_frame':sample},'candidate_math':{'v5-control':'H(N,V,L,E)+0.60*D with unchanged V4 shield and V5 weapon terms','direction-independent-fill-0.90':'H(N,V,L,E)+0.90*D with unchanged equipment terms','bilateral-key-fill-75-25':'0.75*C(L,E)+0.25*C(Rz(pi)L,Rz(pi)E), display-domain diagnostic blend','bilateral-symmetric-50-50':'0.50*C(L,E)+0.50*C(Rz(pi)L,Rz(pi)E), display-domain diagnostic blend'},'semantic_ownership':{'shield':'frontmost semantic-role AOV','melee_weapon':'frontmost semantic-role AOV','whole_unit':'frontmost full alpha','body_armour_helmet_crest':'isolated component silhouette intersected with full-unit alpha; possible overlap contamination recorded as limitation'},'transform_chain':{'facet_root':'rotates complete evaluated geometry about world Z','basis':'deformed world-space N/T/B after FacetRoot','sun':'captured Rome-II vector converted once to Blender world space; not root-relative','ambient_cube':'world-space N rotated only by environment yaw before anisotropic cube weights','environment':'world-space reflected view vector transformed to Rome-II cube basis','view':'fixed orthographic camera world forward','normal_map':'tangent-space sample applied to evaluated world N/T/B','readability':'orientation-independent pre-albedo diffuse term; V4/V5 equipment floors retain semantic eligibility'},'candidates':candidates,'records':records,'opposite_pairs':pairs};(a.output/'whole-unit-opposite-lighting-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
