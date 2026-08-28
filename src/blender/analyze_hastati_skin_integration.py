"""Trace frozen production skin inputs and generate contribution diagnostics."""
import json,math,sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src/blender'));sys.path.insert(0,str(ROOT/'src/rome2'))
import render_hastati_runtime_parity as rp
import render_cross_unit_set_a as cu
import replay_weighted_capture as common

AUD=rp.OUT/'skin-integration-audit';CAP=ROOT/'build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753';RES=CAP/'skin-inventory';ASSET=ROOT/'build/local-integration/rome2/cross-unit-calibration/units/hastati'
MATERIALS={'roman_body1':{'routing':0,'ids':(5661,5118,5663,5122,6565,5120)},'roman_1_head':{'routing':1,'ids':(5665,5124,5667,6569,6565,6567)}}

def mips(rid):return [common.tex(p) for p in sorted(RES.glob(f'resource-{rid}-mip*.dds'),key=lambda p:int(p.stem.split('mip')[-1]))]
def sample_mipped(ms,uv,dx,dy,srgb=False):
 h,w=ms[0].shape[:2];rho=max(np.linalg.norm(dx*np.array((w,h))),np.linalg.norm(dy*np.array((w,h))),1e-8);lod=float(np.clip(np.log2(rho),0,len(ms)-1));lo=int(np.floor(lod));hi=min(lo+1,len(ms)-1);f=lod-lo
 return common.sample(ms[lo],uv,srgb)*(1-f)+common.sample(ms[hi],uv,srgb)*f,lod
def vec(v):return v.tolist() if hasattr(v,'tolist') else float(v)

def lighting(N,D,S,R,skin,V,L):
 nd=float(np.dot(N,L));wrap=np.clip(nd*np.array((.8,.9,.3),np.float32)+np.array((.3,.5,.3),np.float32),0,1)*np.array((.694444,.694444,.444444),np.float32)
 warm=wrap[1]*np.array((.612066,.456263,.05),np.float32);remain=np.clip(1-(nd*wrap[0]+.3),0,1);curve=remain*warm;scatter=wrap[2]*np.array((.32,.05,.006),np.float32)*(1-nd*wrap[0]);curve=scatter*(1-remain*warm)+curve+nd*wrap[0]
 skin_nd=np.clip(nd+skin[1]*(curve-nd),0,1);direct_diff=D*skin_nd*rp.SUN_COLOUR*.004*.9
 back_n=max(0,float(np.dot(N,-L)))**2;back_v=max(0,float(np.dot(-V,L)))**4;back_w=back_n*back_v*skin[2];back=D*back_w*rp.SUN_COLOUR*(1-skin[1]*np.array((.3,1,1),np.float32))*.004*.9
 Na=rp.normalize(N*np.array((1,4,1),np.float32));amb=sum(Na[i]**2*rp.AMBIENT[i,1 if Na[i]<0 else 0] for i in range(3));ambient_diff=D*amb*360*.0024
 exponent=S*S*127+1.6;sun_refl=rp.normalize((-L)+2*N*nd);spec_w=max(0,float(np.dot(sun_refl,V)))**exponent*R;direct_spec=rp.SUN_COLOUR*.004*spec_w*2
 ndv=float(np.dot(V,N));ar=rp.normalize(V-2*N*ndv);Ar=rp.normalize(ar*np.array((1,4,1),np.float32));ramb=sum(Ar[i]**2*rp.AMBIENT[i,1 if Ar[i]<0 else 0] for i in range(3));grazing=np.clip(1-ndv,0,1)**2*skin[0]*1.5;lift=rp.normalize(N+np.array((0,.75,0),np.float32));ambient_scatter=ramb*grazing*max(0,float(lift[1]));hdr=np.maximum(0,ambient_diff+ambient_scatter+direct_diff+back+direct_spec)
 return {'N':N,'V':V,'L':L,'raw_ndotl':nd,'wrap':wrap,'wrapped_curve':curve,'skin_ndotl':skin_nd,'ambient_cube_rgb':amb,'ambient_diffuse':ambient_diff,'ambient_grazing_scatter':ambient_scatter,'direct_diffuse':direct_diff,'backscatter':back,'direct_specular':direct_spec,'hdr':hdr}

def tone_trace(hdr):
 lut=np.frombuffer((rp.REC/'g_scurve_texture_sampler.bin').read_bytes(),'<f2').astype(np.float32);M=np.array(((.4124564,.2126729,.0193339),(.3575761,.7151522,.1191920),(.1804375,.0721750,.9503041)),np.float32);xyz=hdr@M;total=max(float(sum(xyz)),1e-8);Y=np.clip(xyz[1],0,15.5625);x=xyz[0]/total;y=max(xyz[1]/total,1e-8);lb=-3.;lw=1.1630859375;black=.0009994507;white=15.5625;c=np.clip((math.log10(max(Y,.011))-lb)/(lw-lb),0,1)*255;i=int(math.floor(c));curve=lut[i]*(1-(c-i))+lut[min(i+1,255)]*(c-i);mapped=(10**(curve*(lw-lb)+lb)-black)/(white-black);X=mapped*x/y;Z=mapped*(1-x-y)/y;pre=np.maximum(np.array((X,mapped,Z))@np.array(((3.2404542,-.9692660,.0556434),(-1.5371385,1.8760108,-.2040259),(-.4985314,.0415560,1.0572252)),np.float32),0);display=np.sqrt(np.clip(pre*1.2,0,1))*np.array((.964706,.996078,1),np.float32)
 return {'xyz':xyz,'logyxy_input':{'luminance_Y':float(Y),'chroma_x':float(x),'chroma_y':float(y)},'scurve_coordinate':float(c),'mapped_luminance':float(mapped),'rgb_before_final_display':pre,'final_rgb':display}

def main():
 routing=np.load(AUD/'routing.npy');uv=np.load(AUD/'uv.npy')[...,:2];raw={n:np.load(AUD/f'{n}.npy') for n in ('raw_diffuse','raw_normal','raw_gloss','raw_skin_mask','raw_dirt_mask','raw_dirt')};D=np.load(rp.AOV/'diffuse.npy')[...,:3];N=rp.normalize(np.load(rp.AOV/'normal.npy')[...,:3]*2-1);params=np.load(rp.AOV/'params.npy');production_hdr=np.load(rp.AOV/'hdr_linear.npy');actualmask=np.load(rp.AOV/'specular.npy')[...,:3];family=np.load(rp.AOV/'family.npy')
 amount_aov=raw['raw_dirt'][...,2]*raw['raw_dirt_mask'][...,0];oldmask=raw['raw_skin_mask'][...,:3]*(1-.99*amount_aov)[...,None]
 final=common.tex(rp.OUT/'runtime-parity-f03-pre-skin-mask-fix.png')
 routed_skin=family[...,0]>.5;body=(routing[...,0]>.5)&routed_skin;ys,xs=np.where(body);ymin,ymax=ys.min(),ys.max();interior=body.copy();interior[[0,-1]]=False;interior[:,[0,-1]]=False;interior&=np.roll(body,1,0)&np.roll(body,-1,0)&np.roll(body,1,1)&np.roll(body,-1,1)
 leg=interior&(np.indices(body.shape)[0]>ymin+.55*(ymax-ymin));upper=interior&(np.indices(body.shape)[0]<ymin+.58*(ymax-ymin));rgb=final[...,:3];lum=rgb@np.array((.2126,.7152,.0722));cool=rgb[...,2]-rgb[...,0];warm=rgb[...,0]-rgb[...,2]
 def choose(mask,score,maximum=True):
  ids=np.argwhere(mask);vals=score[mask];k=int(np.argmax(vals) if maximum else np.argmin(vals));return tuple(ids[k])
 pA=choose(leg&(lum>.04),cool);dark_candidates=leg&(lum>.005);pB=choose(dark_candidates if np.any(dark_candidates) else leg,lum,False);pC=choose(leg,warm);pD=choose(upper,warm);points=[('grey_blue_leg',pA),('dark_grey_leg',pB),('warm_leg_arm',pC),('warm_arm_hand',pD)]
 geometry={tuple(q['pixel']):q for q in json.loads((AUD/'geometry-probes.json').read_text())} if (AUD/'geometry-probes.json').exists() else {}
 bpy.ops.wm.read_factory_settings(use_empty=True);cu.configure_camera(bpy.context.scene,rp.FACET_AZIMUTH,30,8.5,12);V=np.array(bpy.context.scene.camera.matrix_world.to_quaternion()@Vector((0,0,1)),np.float32);V/=np.linalg.norm(V);axis=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float32);L=axis@(-rp.SUN_DIRECTION_R2);L/=np.linalg.norm(L)
 cache={m:[mips(i) for i in q['ids']] for m,q in MATERIALS.items()};traces=[]
 for label,(y,x) in points:
  material='roman_body1' if routing[y,x,0]>.5 else 'roman_1_head';ms=cache[material];geo=geometry.get((x,y));q=np.array(geo['uv']) if geo else uv[y,x];dx=np.array(geo['uv_dx']) if geo else uv[y,x+1]-q;dy=np.array(geo['uv_dy']) if geo else uv[y+1,x]-q
  explicit=[];lods=[]
  for k,(srgb,scale) in enumerate(((True,1),(False,1),(True,1),(False,1),(False,4),(False,1))):
   bq=q*scale;bdx=dx*scale;bdy=dy*scale;sq=np.array((bq[0],1-bq[1]));sdx=np.array((bdx[0],-bdx[1]));sdy=np.array((bdy[0],-bdy[1]));v,l=sample_mipped(ms[k],sq,sdx,sdy,srgb);explicit.append(v);lods.append(l)
  dif,nor,glo,dm,dirt,skin=explicit;amount=float(dirt[3]*dm[3]);material_D=dif[:3]+amount*(np.array((.03,.025,.02),np.float32)-dif[:3]);li_old=lighting(N[y,x],D[y,x],float(params[y,x,0]),float(params[y,x,1]),oldmask[y,x],V,L);li=lighting(N[y,x],D[y,x],float(params[y,x,0]),float(params[y,x,1]),actualmask[y,x],V,L);tone=tone_trace(li['hdr'])
  blender=[raw['raw_diffuse'][y,x,:3],raw['raw_normal'][y,x,:2],raw['raw_gloss'][y,x,:2],raw['raw_dirt_mask'][y,x,:1],raw['raw_dirt'][y,x,:3],raw['raw_skin_mask'][y,x,:3]]
  explicit_relevant=[dif[:3],nor[[3,1]],glo[:2],dm[3:4],dirt[[0,1,3]],skin[:3]]
  traces.append({'label':label,'pixel':[int(x),int(y)],'object':geo['object'] if geo else None,'source_model':geo['source_model'] if geo else None,'triangle':geo['triangle'] if geo else None,'material':material,'uv':q.tolist(),'uv_dx':dx.tolist(),'uv_dy':dy.tolist(),'source':{'blender_aov':{n:vec(v) for n,v in zip(('diffuse_linear','normal_AG_linear','gloss_RG_linear_srgb_view','dirt_mask_A_linear','dirt_RGA_linear','skin_mask_RGB_linear'),blender)},'explicit_sampler':{n:vec(v) for n,v in zip(('diffuse_linear','normal_AG_linear','gloss_RG_linear_srgb_view','dirt_mask_A_linear','dirt_RGA_linear','skin_mask_RGB_linear'),explicit_relevant)},'explicit_lods':lods,'max_abs_sampler_differences':{n:float(np.max(np.abs(a-b))) for n,a,b in zip(('diffuse','normal_AG','gloss_RG','dirt_mask_A','dirt_RGA','skin_mask_RGB'),blender,explicit_relevant)},'dirt_amount':amount},'material_output':{'D':D[y,x].tolist(),'explicit_D':material_D.tolist(),'world_N':N[y,x].tolist(),'smoothness':float(params[y,x,0]),'reflectivity':float(params[y,x,1]),'skin_mask_required':raw['raw_skin_mask'][y,x,:3].tolist(),'skin_mask_actual_corrected_aov':actualmask[y,x].tolist(),'skin_mask_current_buggy_aov':oldmask[y,x].tolist(),'rt0_equivalent':np.r_[N[y,x]*.5+.5,params[y,x,0]].tolist(),'rt1_equivalent':np.r_[D[y,x],params[y,x,1]].tolist(),'rt2_required':np.r_[actualmask[y,x],actualmask[y,x,2]].tolist()},'lighting_current_buggy_mask':{k:vec(v) for k,v in li_old.items()},'lighting_correct_mask':{k:vec(v) for k,v in li.items()},'production_corrected_hdr':production_hdr[y,x].tolist(),'production_corrected_display_trace':{k:vec(v) if not isinstance(v,dict) else v for k,v in tone_trace(production_hdr[y,x]).items()},'display_correct_mask':{k:vec(v) if not isinstance(v,dict) else v for k,v in tone.items()},'current_render_rgb':rgb[y,x].tolist()})
 offsets=json.loads((CAP/'skin-inventory'/'instance-offsets.json').read_text());unique=[]
 for row in offsets:
  o=row['dirt_offset']
  if o not in unique:unique.append(o)
 offset_rows=[]
 for off in [[0,0]]+unique:
  diffs=[];amounts=[]
  for t in traces:
   material=t['material'];ms=cache[material];q=np.array(t['uv']);dx=np.array(t['uv_dx']);dy=np.array(t['uv_dy']);dif=np.array(t['source']['explicit_sampler']['diffuse_linear']);dm=float(t['source']['explicit_sampler']['dirt_mask_A_linear'][0]);bq=q*4+off;sq=np.array((bq[0],1-bq[1]));sdx=np.array((dx[0]*4,-dx[1]*4));sdy=np.array((dy[0]*4,-dy[1]*4));dirt,_=sample_mipped(ms[4],sq,sdx,sdy,False);a=float(dirt[3]*dm);do=dif[:3]+a*(np.array((.03,.025,.02))-dif[:3]);diffs.append(do);amounts.append(a)
  offset_rows.append({'offset':off,'trace_D':[v.tolist() for v in diffs],'trace_dirt_amount':amounts})
 base=np.array(offset_rows[0]['trace_D']);allD=np.array([r['trace_D'] for r in offset_rows]);offset_summary={'maximum_channel_delta_from_zero':float(np.max(np.abs(allD-base[None]))),'maximum_luminance_delta_from_zero':float(np.max(np.abs((allD-base[None])@np.array((.2126,.7152,.0722))))),'rows':offset_rows}
 # Full-frame corrected skin contributions for the debug sheet.
 skin=raw['raw_skin_mask'][...,:3];nd=np.sum(N*L,axis=-1);wrap=np.clip(nd[...,None]*np.array((.8,.9,.3))+np.array((.3,.5,.3)),0,1)*np.array((.694444,.694444,.444444));warmc=wrap[...,1,None]*np.array((.612066,.456263,.05));remain=np.clip(1-(nd*wrap[...,0]+.3),0,1);curve=remain[...,None]*warmc;sc=wrap[...,2,None]*np.array((.32,.05,.006))*(1-nd*wrap[...,0])[...,None];curve=sc*(1-remain[...,None]*warmc)+curve+(nd*wrap[...,0])[...,None];snd=np.clip(nd[...,None]+skin[...,1,None]*(curve-nd[...,None]),0,1);direct=D*snd*rp.SUN_COLOUR*.004*.9;Na=rp.normalize(N*np.array((1,4,1)));amb=np.zeros_like(N);[amb.__iadd__(Na[...,i,None]**2*np.where((Na[...,i]<0)[...,None],rp.AMBIENT[i,1],rp.AMBIENT[i,0])) for i in range(3)];ad=D*amb*360*.0024;back_n=np.maximum(0,np.sum(N*(-L),axis=-1))**2;back_v=np.maximum(0,np.sum((-V)*L))**4;back=D*(back_n*back_v*skin[...,2])[...,None]*rp.SUN_COLOUR*(1-skin[...,1,None]*np.array((.3,1,1)))*.004*.9;ndv=np.sum(V*N,axis=-1);ar=rp.normalize(V-2*N*ndv[...,None]);Ar=rp.normalize(ar*np.array((1,4,1)));ramb=np.zeros_like(N);[ramb.__iadd__(Ar[...,i,None]**2*np.where((Ar[...,i]<0)[...,None],rp.AMBIENT[i,1],rp.AMBIENT[i,0])) for i in range(3)];graz=np.clip(1-ndv,0,1)**2*skin[...,0]*1.5;lift=rp.normalize(N+np.array((0,.75,0)));ags=ramb*graz[...,None]*np.maximum(0,lift[...,1,None]);exp=params[...,0]**2*127+1.6;sr=rp.normalize((-L)+2*N*nd[...,None]);sw=np.maximum(0,np.sum(sr*V,axis=-1))**exp*params[...,1];ds=rp.SUN_COLOUR*.004*sw[...,None]*2;hdr=np.maximum(0,ad+ags+direct+back+ds);mask=(routing[...,0]>.5)|(routing[...,1]>.5);alpha=mask[...,None].astype(np.float32)
 components={'a-source-linear-diffuse':raw['raw_diffuse'][...,:3],'b-skin-mask':skin,'c-world-normal':N*.5+.5,'d-raw-ndotl':np.repeat(np.clip(nd[...,None]*.5+.5,0,1),3,-1),'e-wrapped-skin-diffuse':direct/(1+direct),'f-six-colour-ambient-diffuse':ad/(1+ad),'g-grazing-ambient-scatter':ags/(1+ags),'h-backscatter':back/(1+back),'i-direct-specular':ds/(1+ds),'j-final-linear-hdr':hdr/(1+hdr)}
 for name,v in components.items():rp.png_rgba(AUD/f'{name}.png',np.concatenate((np.where(mask[...,None],v,0),alpha),-1))
 report={'verdict':'INTEGRATION BUG FOUND','bug':'WeightedSkinDirtmap skinMask was multiplied by (1-.99*dirtAmount) in the production specular AOV; captured RT2 requires untouched skinMask.xyzz.','routing_pixel_counts':json.loads((AUD/'routing.json').read_text())['pixel_counts'],'production_skin_lighting_pixel_count':int(np.count_nonzero(routed_skin)),'traces':traces,'dirt_offset_test':offset_summary}
 (AUD/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
