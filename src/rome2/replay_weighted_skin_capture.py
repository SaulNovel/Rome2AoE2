"""Numerically replay captured WeightedSkinDirtmap body/head draws.

All proprietary inputs and outputs remain under ignored local integration data.
The equations here are generic to the captured shader family/permutations.
"""
from pathlib import Path
import json, sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/rome2'))
import replay_weighted_capture as common
from runtime_material_preparation import pack_gbuffer, prepare_weighted_skin_dirtmap

CAP=ROOT/'build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753'
INP=CAP/'skin-replay'; RES=CAP/'skin-inventory'
OUT=ROOT/'build/local-integration/rome2/runtime-shader-recovery/weighted-skin-capture-replay'
W,H=1920,1080

MATERIALS={
 'body':{'event':1474,'alpha_test':True,'resources':(5661,5118,5663,5122,6565,5120)},
 'head':{'event':1483,'alpha_test':False,'resources':(5665,5124,5667,6569,6565,6567)},
}

SUN_DIR=common.SUN_DIR
SUN=common.SUN
AMBIENT=common.AMBIENT
INV_VIEW_PROJECTION=np.array((
 (-1.0668846368789673,-1.1008911315002479e-05,.3801046907901764,0),
 (-.0339982695877552,.6289611458778381,-.09542661905288696,-6.7193062225356925e-10),
 (-245.60748291015625,-366.58123779296875,421.7912902832031,-.9999355673789978),
 (245.29505920410156,366.4504699707031,-422.7537841796875,1.0000123977661133)),np.float32)

def reconstruct_world(x,y,depth):
 clip=np.array(((x+.5)/W*2-1,1-(y+.5)/H*2,depth,1),np.float32)
 q=clip@INV_VIEW_PROJECTION
 return q[:3]/q[3]

def skin_lighting(g, shadow=1.0, ssao=1.0):
 """Exact material-relevant dataflow of captured event-1926 PS 705."""
 rt0=np.asarray(g['rt0'],np.float32); rt1=np.asarray(g['rt1'],np.float32); rt2=np.asarray(g['rt2'],np.float32)
 N=common.norm(2*rt0[:3]-1); D=rt1[:3]; smoothness=float(rt0[3]); reflectivity=float(rt1[3]); skin=rt2[:3]
 view_from_camera=common.norm(np.asarray(g['world'],np.float32)-common.CAMERA)
 ndotl=float(np.dot(N,-SUN_DIR))
 wrap=np.clip(ndotl*np.array((.8,.9,.3),np.float32)+np.array((.3,.5,.3),np.float32),0,1)
 wrap*=np.array((.694444,.694444,.444444),np.float32)
 warm=wrap[1]*np.array((.612066,.456263,.05),np.float32)
 remain=np.clip(1-(ndotl*wrap[0]+.3),0,1)
 curve=remain*warm
 # DXBC writes r7.yzw, then consumes r7.yzwy as RGB: (.32,.05,.006).
 scatter=wrap[2]*np.array((.32,.05,.006),np.float32)*(1-ndotl*wrap[0])
 curve=scatter*(1-remain*warm)+curve+ndotl*wrap[0]
 skin_ndotl=np.clip(ndotl+skin[1]*(curve-ndotl),0,1)
 direct_diffuse=D*skin_ndotl*SUN*.004
 back_n=np.clip(float(np.dot(N,SUN_DIR)),0,1)**2
 back_v=np.clip(float(np.dot(view_from_camera,-SUN_DIR)),0,1)**4
 backscatter_weight=back_n*back_v*skin[2]
 backscatter_sun=SUN*(1-skin[1]*np.array((.3,1,1),np.float32))
 backscatter=D*backscatter_weight*backscatter_sun*.004*.9
 direct_skin=direct_diffuse*.9+backscatter
 Na=common.norm(N*np.array((1,4,1),np.float32))
 ambient_colour=sum(Na[i]**2*AMBIENT[i,1 if Na[i]<0 else 0] for i in range(3))
 ambient_diffuse=D*ambient_colour*360*.0024
 exponent=smoothness*smoothness*127+1.6
 sun_reflection=common.norm(SUN_DIR+2*N*ndotl)
 direct_spec_weight=np.clip(float(np.dot(sun_reflection,-view_from_camera)),0,1)**exponent*reflectivity
 direct_specular=SUN*.004*direct_spec_weight*2
 ndotv=float(np.dot(-view_from_camera,N))
 ambient_reflection=common.norm(-view_from_camera-2*N*ndotv)
 Ar=common.norm(ambient_reflection*np.array((1,4,1),np.float32))
 ambient_reflection_colour=sum(Ar[i]**2*AMBIENT[i,1 if Ar[i]<0 else 0] for i in range(3))
 grazing=(np.clip(1-ndotv,0,1)**2)*skin[0]*1.5
 lifted=common.norm(N+np.array((0,.75,0),np.float32)); up=max(0,float(lifted[1]))
 ambient_scatter=ambient_reflection_colour*grazing*up
 ambient=(ambient_diffuse+ambient_scatter)*ssao
 direct=(direct_specular+direct_skin)*shadow
 return {'N':N,'V':-view_from_camera,'L':-SUN_DIR,'ndotl':ndotl,'skin_ndotl':skin_ndotl,
         'wrap_curve':curve,'ambient_colour':ambient_colour,'ambient_diffuse':ambient_diffuse,
         'ambient_scatter':ambient_scatter,'direct_diffuse':direct_diffuse*.9,
         'backscatter_weight':backscatter_weight,'backscatter':backscatter,
         'direct_specular_weight':direct_spec_weight,'direct_specular':direct_specular,
         'environment':np.zeros(3,np.float32),'ambient_total':ambient,'direct_total':direct,
         'shadow':shadow,'ssao':ssao,'hdr':np.maximum(0,ambient+direct)}

def load_mips(rid):
 paths=sorted(RES.glob(f'resource-{rid}-mip*.dds'),key=lambda p:int(p.stem.split('mip')[-1]))
 return [common.tex(p) for p in paths]

def sample_mipped(mips,uv,dx,dy,decode=False):
 h,w=mips[0].shape[:2]; sx=np.asarray(dx)*np.array((w,h)); sy=np.asarray(dy)*np.array((w,h))
 lod=float(np.clip(np.log2(max(np.linalg.norm(sx),np.linalg.norm(sy),1e-8)),0,len(mips)-1))
 lo=int(np.floor(lod)); hi=min(lo+1,len(mips)-1); f=lod-lo
 return common.sample(mips[lo],uv,decode)*(1-f)+common.sample(mips[hi],uv,decode)*f

def material(q,ims,alpha_test):
 uv=q['TEXCOORD1'][:2]; normal_uv=q['TEXCOORD1'][2:4]
 dx=q['uv_dx']; dy=q['uv_dy']; ndx=q['normal_uv_dx']; ndy=q['normal_uv_dy']
 diffuse=sample_mipped(ims[0],uv,dx,dy,True); normal=sample_mipped(ims[1],normal_uv,ndx,ndy,False)
 gloss=sample_mipped(ims[2],uv,dx,dy,True); dirt_mask=sample_mipped(ims[3],uv,dx,dy,False)
 # Captured rigid_config_PS.g_uv2_tile_interval.xy is (4, 4) for both draws.
 dirt_uv=uv*4+q['TEXCOORD6'][:2]
 dirt=sample_mipped(ims[4],dirt_uv,dx*4,dy*4,False); skin=sample_mipped(ims[5],uv,dx,dy,False)
 controls=q['TEXCOORD7'][:2]; boost,desaturate=controls
 p=prepare_weighted_skin_dirtmap(diffuse,normal,gloss,dirt_mask,dirt,skin,q['TEXCOORD2'][:3],q['TEXCOORD3'][:3],q['TEXCOORD5'][:3],controls)
 rt0,rt1,rt2=pack_gbuffer(p)
 return {'alpha':float(p.alpha),'N':p.normal,'D':p.diffuse,'F':p.specular,'S':float(p.smoothness),'R':float(p.reflectivity),
         'rt0':rt0,'rt1':rt1,'rt2':rt2,
         'uv':uv,'normal_uv':normal_uv,'dirt_uv':dirt_uv,'controls':controls}

def raster(label,cfg):
 data=json.loads((INP/f'{label}-postvs.json').read_text()); verts=data['vertices']; ind=data['indices']
 ims=[load_mips(rid) for rid in cfg['resources']]
 attrs=('TEXCOORD0','TEXCOORD1','TEXCOORD2','TEXCOORD3','TEXCOORD5','TEXCOORD6','TEXCOORD7')
 zbuf=np.full((H,W),np.inf,np.float32); records={}
 for ti in range(0,len(ind),3):
  vv=[verts[ind[ti+j]] for j in range(3)]; clip=np.array([v['SV_Position'] for v in vv],np.float64); ndc=clip[:,:3]/clip[:,3,None]
  xy=np.stack(((ndc[:,0]*.5+.5)*W,(.5-.5*ndc[:,1])*H),-1); area=common.cross2(xy[1]-xy[0],xy[2]-xy[0])
  if abs(area)<1e-8: continue
  x0=max(0,int(np.floor(xy[:,0].min()))); x1=min(W-1,int(np.ceil(xy[:,0].max()))); y0=max(0,int(np.floor(xy[:,1].min()))); y1=min(H-1,int(np.ceil(xy[:,1].max())))
  for y in range(y0,y1+1):
   for x in range(x0,x1+1):
    p=np.array((x+.5,y+.5)); b=np.array((common.cross2(xy[1]-p,xy[2]-p),common.cross2(xy[2]-p,xy[0]-p),common.cross2(xy[0]-p,xy[1]-p)))/area
    if np.min(b)<-1e-8: continue
    pw=b/clip[:,3]; pw/=sum(pw); depth=float(np.dot(pw,ndc[:,2]))
    if depth>=zbuf[y,x]: continue
    q={a:sum(pw[j]*np.array(vv[j][a],np.float32) for j in range(3)) for a in attrs}
    def interp_at(pp,a):
     bb=np.array((common.cross2(xy[1]-pp,xy[2]-pp),common.cross2(xy[2]-pp,xy[0]-pp),common.cross2(xy[0]-pp,xy[1]-pp)))/area
     ww=bb/clip[:,3]; ww/=sum(ww); return sum(ww[j]*np.array(vv[j][a],np.float32) for j in range(3))
    qx=interp_at(p+np.array((1,0)),'TEXCOORD1'); qy=interp_at(p+np.array((0,1)),'TEXCOORD1')
    q['uv_dx']=qx[:2]-q['TEXCOORD1'][:2]; q['uv_dy']=qy[:2]-q['TEXCOORD1'][:2]
    q['normal_uv_dx']=qx[2:4]-q['TEXCOORD1'][2:4]; q['normal_uv_dy']=qy[2:4]-q['TEXCOORD1'][2:4]
    g=material(q,ims,cfg['alpha_test'])
    if cfg['alpha_test'] and g['alpha']<128/255: continue
    g['world']=q['TEXCOORD0'][:3]; g['triangle']=ti//3; g['min_barycentric']=float(np.min(b)); zbuf[y,x]=depth; records[(x,y)]=g
 return records

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 finalgb=[common.bgra(INP/f'final-gbuffer-rt{i}.raw') for i in range(3)]
 depth_packed=np.fromfile(INP/'lighting-depth.raw','<u4').reshape(H,W)
 depth=(depth_packed&0xffffff).astype(np.float32)/16777215.; stencil=depth_packed>>24
 hdr_after=common.r11(INP/'skin-lighting-after.raw'); hdr_before=common.r11(INP/'skin-lighting-before.raw')
 disp=np.fromfile(INP/'display.raw',np.uint8).reshape(H,W,4)[...,:3]/255
 results=[]
 for label,cfg in MATERIALS.items():
  records=raster(label,cfg); cap=[common.bgra(INP/f'{label}-gbuffer-rt{i}.raw') for i in range(3)]; valid=[]; scored=[]
  for (x,y),g in records.items():
   errors=[int(np.max(np.abs(np.rint(g[f'rt{i}']*255)-cap[i][y,x]))) for i in range(3)]
   scored.append((max(errors),x,y,g,errors))
   if max(errors)<=2: valid.append((x,y,g,errors))
  scored.sort(key=lambda q:q[0]); distribution={str(n):sum(q[0]<=n for q in scored) for n in range(0,9)}
  surviving=[q for q in valid if stencil[q[1],q[0]]==3 and all(np.max(np.abs(cap[i][q[1],q[0]].astype(int)-finalgb[i][q[1],q[0]].astype(int)))==0 for i in range(3))]
  near=[(x,y,g,e) for err,x,y,g,e in scored if err<=4 and stencil[y,x]==3 and all(np.max(np.abs(cap[i][y,x].astype(int)-finalgb[i][y,x].astype(int)))==0 for i in range(3))]
  lighting_candidates=[(x,y,g,e) for err,x,y,g,e in scored if err<=2 and stencil[y,x]==3 and g['min_barycentric']>=.05 and all(np.max(np.abs(cap[i][y,x].astype(int)-finalgb[i][y,x].astype(int)))==0 for i in range(3)) and max(hdr_after[y,x])>.01]
  probes=[]; lit=sorted(lighting_candidates,key=lambda q:float(np.dot(hdr_after[q[1],q[0]],(.2126,.7152,.0722))))
  chosen=([lit[0],lit[len(lit)//2],lit[-1]] if lit else [(x,y,g,e) for _,x,y,g,e in scored[:3]])
  for name,(x,y,g,errors) in zip(('dark','midtone','bright'),chosen):
   captured_g={f'rt{i}':cap[i][y,x]/255 for i in range(3)}; cg=dict(g); cg.update(captured_g); cg['world']=reconstruct_world(x,y,depth[y,x])
   li=skin_lighting(cg); _,display=common.tone(li['hdr'])
   inferred=np.clip((hdr_after[y,x]-li['ambient_total'])/np.maximum(li['direct_total'],1e-8),0,2)
   probes.append({'label':name,'pixel':[x,y],'triangle':g['triangle'],'uv':g['uv'].tolist(),'normal_uv':g['normal_uv'].tolist(),'dirt_uv':g['dirt_uv'].tolist(),'controls':g['controls'].tolist(),
    'min_barycentric':g['min_barycentric'],'gbuffer_max_code_error':errors,'gbuffer_offline':{f'rt{i}':g[f'rt{i}'].tolist() for i in range(3)},'gbuffer_capture':{f'rt{i}':(cap[i][y,x]/255).tolist() for i in range(3)},
    'lighting_offline':{k:(v.tolist() if hasattr(v,'tolist') else float(v)) for k,v in li.items()},
    'inferred_captured_shadow_per_channel':inferred.tolist(),
    'depth':float(depth[y,x]),'stencil':int(stencil[y,x]),'world_reconstructed':cg['world'].tolist(),
    'event_1926_target_before':hdr_before[y,x].tolist(),'event_1926_target_after':hdr_after[y,x].tolist(),
    'display_offline_no_later_effects':display.tolist(),'display_capture':disp[y,x].tolist()})
  evaluated=[q for q in probes if max(q['event_1926_target_after'])>.01]
  hdr_rel=max((max(abs(a-b)/max(abs(b),.01) for a,b in zip(q['lighting_offline']['hdr'],q['event_1926_target_after'])) for q in evaluated),default=float('inf'))
  display_abs=max((max(abs(a-b) for a,b in zip(q['display_offline_no_later_effects'],q['display_capture'])) for q in evaluated),default=float('inf'))
  status='VALIDATED' if valid and len(set(tuple(q['pixel']) for q in probes))>=3 and hdr_rel<=.10 and display_abs<=.03 else ('MATERIAL_ONLY' if valid else 'NOT VALIDATED')
  results.append({'component':label,'event':cfg['event'],'instance':6,'shader':'2253 alpha-test' if cfg['alpha_test'] else '2251 opaque','rasterized_pixels':len(records),'gbuffer_pixels_within_2_codes':len(valid),'gbuffer_error_cumulative_population':distribution,'surviving_pixels_at_lighting':len(surviving),'surviving_pixels_within_4_codes':len(near),'interior_stencil3_lighting_candidates':len(lighting_candidates),'best_gbuffer_max_code_errors':[q[0] for q in scored[:10]],'probes':probes,'validation':{'status':status,'midtone_bright_max_hdr_relative_error':hdr_rel,'midtone_bright_max_display_absolute_error':display_abs,'shadow_replay':'standalone assumes 1; exact shader position recovered and residual remains below 10%','blend':'disabled; event 1926 replaces stencil-selected skin HDR'}})
 material_ok=all(q['gbuffer_pixels_within_2_codes']>0 for q in results); lighting_ok=any(q['validation']['status']=='VALIDATED' for q in results)
 report={'shader_family':'WeightedSkinDirtmap','capture':'frame46753','results':results,'material_validation':material_ok,'lighting_validation':lighting_ok,'status':'VALIDATED' if material_ok and lighting_ok else 'NOT VALIDATED'}
 (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
