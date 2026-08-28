"""FAST/x2 per-direction scalar HDR exposure-normalization diagnostic."""
import argparse,json,math,shutil,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'src/blender'),str(ROOT/'src/rome2')]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
import audit_whole_unit_opposite_lighting as prior
from aoe2.facet_mapping import soldier_yaw_degrees
LUMA=np.array((.2126,.7152,.0722),np.float32);COMPONENTS=('body','armour','helmet','crest','shield','melee_weapon')
def args():
 p=argparse.ArgumentParser();p.add_argument('--input-blend',type=Path,required=True);p.add_argument('--static-input',type=Path,required=True);p.add_argument('--source-aov-root',type=Path,required=True);p.add_argument('--full-diffuse-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--sample-fraction',type=float,default=.5);return p.parse_args(sys.argv[sys.argv.index('--')+1:])
def arrays_at(a,d):
 arrays={n:np.load(a.source_aov_root/f'direction-{d:02d}'/f'{n}.npy') for n in exact.exact_materials.RAW_AOVS};arrays['diffuse_raw']=np.load(a.full_diffuse_root/f'direction-{d:02d}'/'diffuse_raw.npy');return arrays
def display_stats(image,mask):
 active=mask&(image[...,3]>.001);v=(image[...,:3]@LUMA)[active]
 if not len(v):return {'pixels':0,'mean':None,'median':None,'p95':None,'approaching_display_limit_percent':None,'clipped_percent':None}
 return {'pixels':int(len(v)),'mean':float(v.mean()),'median':float(np.median(v)),'p95':float(np.percentile(v,95)),'approaching_display_limit_percent':float(100*np.count_nonzero(v>=.98)/len(v)),'clipped_percent':float(100*np.count_nonzero(v>=.999)/len(v))}
def load_masks(root,d):return {p.stem:np.load(p) for p in (root/f'direction-{d:02d}').glob('*.npy')}
def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);doc=json.loads(a.static_input.read_text());shutil.copyfile(doc['texture_manifest'],a.output/'texture-manifest.json');bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);root=bpy.data.objects['Rome2AoE2_FacetRoot'];arm=next(o for o in scene.objects if o.type=='ARMATURE');start,end=arm.animation_data.action.frame_range;sample=start+(end-start)*a.sample_fraction;scene.frame_set(int(sample),subframe=sample-int(sample));runtime.RESOLUTION=400;scene.render.resolution_x=scene.render.resolution_y=400;scene.render.resolution_percentage=100;scene.render.film_transparent=True;scene.render.image_settings.file_format='OPEN_EXR';scene.render.image_settings.color_mode='RGBA';scene.render.image_settings.color_depth='32';scene.render.image_settings.exr_codec='ZIP';scene.display_settings.display_device='sRGB';scene.view_settings.view_transform='Raw';texture_root=Path(doc['texture_root']);profile=json.loads((ROOT/'config/render_profiles/aoe2_infantry_animation_production_v5_equipment_readability.json').read_text());caps=profile['render_capabilities'];measurements=[]
 for d in range(16):
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(d));bpy.context.view_layer.update();arrays=arrays_at(a,d);roles=np.load(a.source_aov_root/f'direction-{d:02d}'/'semantic_role.npy');active=arrays['diffuse_raw'][...,3]>.001;runtime.OUT=a.output;runtime.AOV=a.output/'mask-aov'/f'direction-{d:02d}';runtime.AOV.mkdir(parents=True,exist_ok=True);isolated={c:prior.component_mask(scene,texture_root,c)&active for c in COMPONENTS};shield=(roles[...,0]>.5)&active;weapon=(roles[...,1]>.5)&(roles[...,0]<.5)&active;helmet=isolated['helmet']&~shield&~weapon;crest=isolated['crest']&~shield&~weapon;armour=isolated['armour']&~shield&~weapon&~helmet&~crest;body=isolated['body']&~shield&~weapon&~helmet&~crest&~armour;masks={'whole_unit':active,'body':body,'armour':armour,'helmet':helmet,'crest':crest,'shield':shield,'melee_weapon':weapon,'reference_body_armour':body|armour};mask_root=a.output/'masks'/f'direction-{d:02d}';mask_root.mkdir(parents=True,exist_ok=True)
  for k,v in masks.items():np.save(mask_root/f'{k}.npy',v)
  metrics=runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],exposure_gain=1,output_name=f'v5-control-d{d:02d}.png',diagnostics=False,metric_masks=masks);measurements.append(metrics['hdr_reference']['reference_body_armour']['trimmed_mean_10_90'])
 target=float(np.median(measurements));gains={'v5-control':[1.0]*16,'symmetric-normalization':[float(np.clip(target/x,.85,1.25)) for x in measurements],'lift-only-normalization':[float(np.clip(max(1,target/x),1,1.25)) for x in measurements]};records=[]
 for d in range(16):
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(d));bpy.context.view_layer.update();arrays=arrays_at(a,d);roles=np.load(a.source_aov_root/f'direction-{d:02d}'/'semantic_role.npy');masks=load_masks(a.output/'masks',d)
  for name,values in gains.items():
   gain=values[d];path=a.output/f'{name}-d{d:02d}.png';metrics=runtime.shade(scene,arrays,readability_fill=.6,semantic_role_aov=roles,shield_readability=caps['shield_readability'],weapon_readability=caps['weapon_readability'],exposure_gain=gain,output_name=path.name,diagnostics=False,metric_masks=masks);image=prior.rgba(path);records.append({'candidate':name,'direction':d,'yaw':soldier_yaw_degrees(d),'gain':gain,'measurement':measurements[d],'output':str(path),'metrics':{k:display_stats(image,v) for k,v in masks.items()},'hdr_reference':metrics['hdr_reference'],'whole_display':{'approaching_percent':metrics['clipped_pixel_percentage'],'highlight_p95':metrics['highlight_p95']}})
 pairs=[]
 for name in gains:
  by={r['direction']:r for r in records if r['candidate']==name}
  for d in range(8):
   values={}
   for k in ('whole_unit',*COMPONENTS):
    x=by[d]['metrics'][k]['mean'];y=by[d+8]['metrics'][k]['mean'];values[k]={'first':x,'opposite':y,'relative_difference':None if x is None or y is None or x+y==0 else (y-x)/((x+y)/2)}
   pairs.append({'candidate':name,'pair':[d,d+8],'metrics':values})
 safety={}
 for name in gains:
  rows=[r for r in records if r['candidate']==name];total=sum(r['metrics']['whole_unit']['pixels'] for r in rows)
  safety[name]={'whole_approaching_display_limit_percent':sum(r['metrics']['whole_unit']['pixels']*r['metrics']['whole_unit']['approaching_display_limit_percent'] for r in rows)/total,'whole_clipped_percent':sum(r['metrics']['whole_unit']['pixels']*r['metrics']['whole_unit']['clipped_percent'] for r in rows)/total,'whole_highlight_p95_range':[min(r['metrics']['whole_unit']['p95'] for r in rows),max(r['metrics']['whole_unit']['p95'] for r in rows)],'helmet_highlight_p95_range':[min(r['metrics']['helmet']['p95'] for r in rows if r['metrics']['helmet']['p95'] is not None),max(r['metrics']['helmet']['p95'] for r in rows if r['metrics']['helmet']['p95'] is not None)],'sword_highlight_p95_range':[min(r['metrics']['melee_weapon']['p95'] for r in rows),max(r['metrics']['melee_weapon']['p95'] for r in rows)]}
 report={'format':'rome2aoe2.directional-exposure-normalization-audit','version':1,'release_eligible':False,'profile':profile['name'],'resolution':[400,400],'pose':{'category':'idle','sample_fraction':a.sample_fraction,'blender_frame':sample},'normalization':{'reference_mask':'frontmost-derived body plus armour; shield, melee weapon, helmet, crest, background and cast shadow excluded','statistic':'10%-90% trimmed arithmetic mean of pre-exposure linear HDR luminance','measurements':measurements,'target':'median of the 16 directional measurements','target_value':target,'policies':{'symmetric-normalization':'clamp(target/measurement, 0.85, 1.25)','lift-only-normalization':'clamp(max(1,target/measurement), 1.00, 1.25)'},'application':'one scalar multiplies complete V5 main-sprite HDR immediately before unchanged display/tone conversion','gains':gains,'clamp_hits':{k:{'lower':sum(abs(x-(.85 if k=='symmetric-normalization' else 1))<1e-8 for x in v),'upper':sum(abs(x-1.25)<1e-8 for x in v)} for k,v in gains.items() if k!='v5-control'}},'variants':{k:{} for k in gains},'safety':safety,'records':records,'opposite_pairs':pairs};(a.output/'directional-exposure-normalization-audit.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
if __name__=='__main__':main()
