"""FAST/x2 diagnostic preserving V5 and adding diffuse-only lower-tail complement."""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender'),str(ROOT/'src/rome2')]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
import audit_whole_unit_opposite_lighting as prior
from aoe2.facet_mapping import soldier_yaw_degrees
COMPONENTS=('body','armour','helmet','crest','shield','melee_weapon')
def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--source-aov-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sample-fraction',type=float,default=.5);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def arrays_at(root,d):return {n:np.load(root/f'direction-{d:02d}'/f'{n}.npy') for n in exact.exact_materials.RAW_AOVS}
def weighted(records,key):
 total=sum(r['shader_metrics']['body_luminance']['pixels'] for r in records);return sum(r['shader_metrics']['body_luminance']['pixels']*r['shader_metrics']['complementary_diffuse'][key] for r in records)/total
def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);doc=json.loads(a.static_input.read_text());shutil.copyfile(doc['texture_manifest'],a.output/'texture-manifest.json');bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);root=bpy.data.objects['Rome2AoE2_FacetRoot'];arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;sample=start+(end-start)*a.sample_fraction;scene.frame_set(int(sample),subframe=sample-int(sample));runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';texture_root=Path(doc['texture_root']);profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities']
 percentiles=[]
 for d in range(16):
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(d));bpy.context.view_layer.update();arrays=arrays_at(a.source_aov_root,d);roles=np.load(a.source_aov_root/f'direction-{d:02d}'/'semantic_role.npy');runtime.OUT=a.output;runtime.AOV=a.output/'full-aov'/f'direction-{d:02d}';runtime.AOV.mkdir(parents=True,exist_ok=True);arrays['diffuse_raw']=runtime.render_aov(scene,a.output,'diffuse_raw',texture_root);m=runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],complementary_diffuse={'strength':0,'threshold':1,'transition_width':.1},output_name=f'probe-d{d:02d}.png',diagnostics=False);percentiles.append(m['complementary_diffuse']['current_direct_irradiance_percentiles'])
 p25=float(np.median([p['25'] for p in percentiles]));p45=float(np.median([p['45'] for p in percentiles]));threshold=(p25+p45)/2;width=(p45-p25)/2
 candidates={'v5-control':0.0,'complement-weak':.18,'complement-medium':.30,'complement-strong':.42};records=[]
 for d in range(16):
  yaw=soldier_yaw_degrees(d);root.rotation_euler[2]=math.radians(yaw);bpy.context.view_layer.update();arrays=arrays_at(a.source_aov_root,d);arrays['diffuse_raw']=np.load(a.output/'full-aov'/f'direction-{d:02d}'/'diffuse_raw.npy');roles=np.load(a.source_aov_root/f'direction-{d:02d}'/'semantic_role.npy');active=arrays['diffuse_raw'][...,3]>.001;runtime.OUT=a.output;runtime.AOV=a.output/'component-aov'/f'direction-{d:02d}';runtime.AOV.mkdir(parents=True,exist_ok=True);masks={'whole_unit':active}
  for c in COMPONENTS:masks[c]=prior.component_mask(scene,texture_root,c)&active
  masks['shield']=(roles[...,0]>.5)&active;masks['melee_weapon']=(roles[...,1]>.5)&(roles[...,0]<.5)&active
  for name,strength in candidates.items():
   path=a.output/f'{name}-d{d:02d}.png';metrics=runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],complementary_diffuse=None if strength==0 else {'strength':strength,'threshold':threshold,'transition_width':width},output_name=path.name,diagnostics=False,metric_masks=masks);image=prior.rgba(path);records.append({'candidate':name,'direction':d,'yaw':yaw,'output':str(path),'metrics':{k:prior.stats(image,v) for k,v in masks.items()},'shader_metrics':metrics})
 pairs=[]
 for name in candidates:
  by={r['direction']:r for r in records if r['candidate']==name}
  for d in range(8):
   values={}
   for k in by[d]['metrics']:
    first=by[d]['metrics'][k]['mean'];opposite=by[d+8]['metrics'][k]['mean'];values[k]={'first':first,'opposite':opposite,'relative_difference':None if first is None or opposite is None or first+opposite==0 else (opposite-first)/((opposite+first)/2)}
   pairs.append({'candidate':name,'pair':[d,d+8],'metrics':values})
 control={r['direction']:r for r in records if r['candidate']=='v5-control'};bright_directions=sorted(control,key=lambda d:control[d]['metrics']['whole_unit']['mean'],reverse=True)[:4];summary={}
 for name,strength in candidates.items():
  rows=[r for r in records if r['candidate']==name]
  if strength==0:summary[name]={'strength':0,'brightest_direction_quartile':bright_directions,'bright_quartile_mean_display_change':0,'max_already_bright_linear_change':0};continue
  summary[name]={'strength':strength,'zero_weight_percent':weighted(rows,'zero_percent'),'partial_weight_percent':weighted(rows,'partial_percent'),'full_weight_percent':weighted(rows,'full_percent'),'nonzero_correction_percent':weighted(rows,'corrected_nonzero_percent'),'brightest_direction_quartile':bright_directions,'bright_quartile_mean_display_change':float(np.mean([r['metrics']['whole_unit']['mean']-control[r['direction']]['metrics']['whole_unit']['mean'] for r in rows if r['direction'] in bright_directions])),'bright_already_lit_mean_linear_change':weighted(rows,'bright_mean_linear_addition'),'max_already_bright_linear_change':max(r['shader_metrics']['complementary_diffuse']['bright_max_linear_addition'] for r in rows),'mean_abs_opposite_pair_imbalance':float(np.mean([abs(p['metrics']['whole_unit']['relative_difference']) for p in pairs if p['candidate']==name]))}
 report={'format':'rome2aoe2.shadow-side-complement-audit','version':1,'release_eligible':False,'profile':profile['name'],'resolution':[400,400],'pose':{'category':'idle','sample_fraction':a.sample_fraction,'blender_frame':sample},'mirrored_key':{'camera_vertical_symmetry_plane':'span(normalize(Vxy), world +Z)','plane_normal':'normalize(cross(world +Z, normalize(Vxy)))','transformation':'Lmirror = normalize(L - 2*dot(L, plane_normal)*plane_normal)','invariants':['same world-Z component/elevation','same magnitude and photometry','current key unchanged','environment unchanged','no mirrored specular']},'lower_tail':{'current_scalar':'luminance(ndotl * sun_colour * .004 * (1-max(current_direct_reflection, material_reflectivity)))','opposite_scalar':'luminance(max(0,dot(N,Lmirror)) * sun_colour * .004 * (1-material_reflectivity))','weight':'smoothstep((threshold + width - current_scalar)/(2*width)), clamped to [0,1]','correction':'strength * weight * max(0, opposite_scalar-current_scalar)','application':'existing V5 HDR + prepared diffuse albedo * correction','threshold_derivation':{'policy':'median across directions of current-direct p25/p45; full below p25, partial p25-p45, exactly zero above p45','p25':p25,'p45':p45,'threshold':threshold,'transition_width':width}},'candidates':candidates,'summary':summary,'semantic_ownership':{'shield_and_melee_weapon':'frontmost semantic-role AOV','whole_unit':'frontmost alpha','other_components':'isolated silhouette intersected with full alpha; overlap limitation'},'records':records,'opposite_pairs':pairs};(a.output/'shadow-side-complement-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
