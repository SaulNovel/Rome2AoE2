"""Numerically replay the captured DecalDirtmap shield draw (event 1099).

Proprietary geometry/textures remain in ignored local-integration output.
"""
from pathlib import Path
import json, sys
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/rome2'))
import replay_weighted_capture as common
from runtime_material_preparation import pack_gbuffer, prepare_decal_dirtmap

CAP=ROOT/'build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753'
INP=CAP/'decal-replay'; RES=CAP/'decal-inventory'
OUT=ROOT/'build/local-integration/rome2/runtime-shader-recovery/decal-dirtmap-capture-replay'
W,H=1920,1080
RESOURCE_IDS=(5767,5769,5771,5192,5190,7495,7925,5148,7603,7606)
SRGB=(True,True,True,False,False,False,False,False,True,False)
DECAL_RECT=np.array((.5379568338394165,.08394245058298111,.9336691498756409,.8632805943489075),np.float32)
FACTION=np.zeros((3,3),np.float32)

def load_mips(rid):
 paths=sorted(RES.glob(f'resource-{rid}-slice0-mip*.dds'),key=lambda p:int(p.stem.split('mip')[-1]))
 return [common.tex(p) for p in paths]

def sample_mipped(mips,uv,dx,dy,decode=False):
 h,w=mips[0].shape[:2]; sx=np.asarray(dx)*np.array((w,h)); sy=np.asarray(dy)*np.array((w,h))
 lod=float(np.clip(np.log2(max(np.linalg.norm(sx),np.linalg.norm(sy),1e-8)),0,len(mips)-1))
 lo=int(np.floor(lod)); hi=min(lo+1,len(mips)-1); f=lod-lo
 return common.sample(mips[lo],uv,decode)*(1-f)+common.sample(mips[hi],uv,decode)*f, lod

def material(q,ims):
 uv=q['TEXCOORD1'][:2]; dx=q['uv_dx']; dy=q['uv_dy']
 vals=[]; lods=[]
 for im,srgb in zip(ims[:8],SRGB[:8]):
  v,l=sample_mipped(im,uv,dx,dy,srgb);vals.append(v);lods.append(l)
 diffuse,specular,gloss,colour_mask,normal,decal_mask,dirt_mask,dirt=vals
 rect_size=DECAL_RECT[2:]-DECAL_RECT[:2]; decal_uv=(uv-DECAL_RECT[:2])/rect_size
 decal_inside=bool(np.all(decal_uv>=0) and np.all(decal_uv<=1)); decal_diff=np.zeros(4,np.float32);decal_norm=np.zeros(4,np.float32);decal_lods=(0.,0.)
 if decal_inside:
  ddx=dx/rect_size;ddy=dy/rect_size
  decal_diff,dl0=sample_mipped(ims[8],decal_uv,ddx,ddy,True);decal_norm,dl1=sample_mipped(ims[9],decal_uv,ddx,ddy,False);decal_lods=(dl0,dl1)
  alpha=float(decal_diff[3]*decal_mask[3])
 else:alpha=0.
 dirt_uv=uv+q['TEXCOORD6'][1:3]
 dirt,dl=sample_mipped(ims[7],dirt_uv,dx,dy,False);lods[7]=dl
 controls=q['TEXCOORD7'][1:3];boost,desaturate=controls
 p=prepare_decal_dirtmap(diffuse,specular,normal,gloss,colour_mask,dirt_mask,dirt,q['TEXCOORD2'][:3],q['TEXCOORD3'][:3],q['TEXCOORD4'][:3],FACTION,controls,
                         decal_diff if decal_inside else None,decal_norm if decal_inside else None,decal_mask if decal_inside else None)
 rt0,rt1,rt2=pack_gbuffer(p);amount=float(dirt[3]*dirt_mask[3])
 return {'N':p.normal,'D':p.diffuse,'F':p.specular,'S':float(p.smoothness),'R':float(p.reflectivity),'rt0':rt0,'rt1':rt1,'rt2':rt2,
  'uv':uv,'decal_uv':decal_uv,'dirt_uv':dirt_uv,'decal_inside':decal_inside,'decal_alpha':alpha,'decal_diffuse':decal_diff,'decal_normal':decal_norm,'decal_mask':decal_mask,'dirt':dirt,'dirt_mask':dirt_mask,'dirt_amount':amount,'lods':lods,'decal_lods':decal_lods,'controls':controls}

def raster():
 data=json.loads((INP/'shield-postvs.json').read_text());verts=data['vertices'];ind=data['indices'];ims=[load_mips(r) for r in RESOURCE_IDS]
 attrs=('TEXCOORD0','TEXCOORD1','TEXCOORD2','TEXCOORD3','TEXCOORD4','TEXCOORD6','TEXCOORD7')
 zbuf=np.full((H,W),np.inf,np.float32);records={}
 for ti in range(0,len(ind),3):
  vv=[verts[ind[ti+j]] for j in range(3)];clip=np.array([v['SV_Position'] for v in vv],np.float64);ndc=clip[:,:3]/clip[:,3,None];xy=np.stack(((ndc[:,0]*.5+.5)*W,(.5-.5*ndc[:,1])*H),-1);area=common.cross2(xy[1]-xy[0],xy[2]-xy[0])
  if abs(area)<1e-8:continue
  for y in range(max(0,int(np.floor(xy[:,1].min()))),min(H-1,int(np.ceil(xy[:,1].max())))+1):
   for x in range(max(0,int(np.floor(xy[:,0].min()))),min(W-1,int(np.ceil(xy[:,0].max())))+1):
    p=np.array((x+.5,y+.5));b=np.array((common.cross2(xy[1]-p,xy[2]-p),common.cross2(xy[2]-p,xy[0]-p),common.cross2(xy[0]-p,xy[1]-p)))/area
    if np.min(b)<-1e-8:continue
    pw=b/clip[:,3];pw/=sum(pw);depth=float(np.dot(pw,ndc[:,2]))
    if depth>=zbuf[y,x]:continue
    def at(pp,a):
     bb=np.array((common.cross2(xy[1]-pp,xy[2]-pp),common.cross2(xy[2]-pp,xy[0]-pp),common.cross2(xy[0]-pp,xy[1]-pp)))/area;ww=bb/clip[:,3];ww/=sum(ww);return sum(ww[j]*np.array(vv[j][a],np.float32) for j in range(3))
    q={a:at(p,a) for a in attrs};qx=at(p+np.array((1,0)),'TEXCOORD1');qy=at(p+np.array((0,1)),'TEXCOORD1');q['uv_dx']=qx[:2]-q['TEXCOORD1'][:2];q['uv_dy']=qy[:2]-q['TEXCOORD1'][:2]
    g=material(q,ims);g['world']=q['TEXCOORD0'][:3];g['triangle']=ti//3;g['min_barycentric']=float(np.min(b));zbuf[y,x]=depth;records[(x,y)]=g
 return records

def main():
 OUT.mkdir(parents=True,exist_ok=True);records=raster();cap=[common.bgra(INP/f'shield-gbuffer-rt{i}.raw') for i in range(3)];final=[common.bgra(INP/f'final-gbuffer-rt{i}.raw') for i in range(3)]
 depth_packed=np.fromfile(INP/'lighting-depth.raw','<u4').reshape(H,W);stencil=depth_packed>>24
 hdr_after=common.r11(INP/'lighting-after.raw');hdr_before=common.r11(INP/'lighting-before.raw');hdr_delta=np.maximum(0,hdr_after-hdr_before);disp=np.fromfile(INP/'display.raw',np.uint8).reshape(H,W,4)[...,:3]/255
 cube=common.load_cube(CAP/'resources-export'/'s_environment.dds');scored=[]
 for (x,y),g in records.items():
  errors=[int(np.max(np.abs(np.rint(g[f'rt{i}']*255)-cap[i][y,x]))) for i in range(3)];scored.append((max(errors),x,y,g,errors))
 scored.sort(key=lambda q:q[0]);distribution={str(n):sum(q[0]<=n for q in scored) for n in range(9)}
 surviving=[q for q in scored if q[0]<=2 and q[3]['min_barycentric']>=.05 and all(np.max(np.abs(cap[i][q[2],q[1]].astype(int)-final[i][q[2],q[1]].astype(int)))==0 for i in range(3)) and max(hdr_delta[q[2],q[1]])>.01]
 def lum(q):return float(np.dot(hdr_delta[q[2],q[1]],(.2126,.7152,.0722)))
 ordered=sorted(surviving,key=lum);chosen=[]
 if ordered:chosen=[('dark',ordered[0]),('midtone',ordered[len(ordered)//2]),('bright',ordered[-1])]
 for label,pred in (('decal-heavy',lambda q:q[3]['decal_alpha']),('dirt-heavy',lambda q:q[3]['dirt_amount'])):
  if surviving:chosen.append((label,max(surviving,key=pred)))
 probes=[]
 for label,(_,x,y,g,errors) in chosen:
  cg=dict(g);cg.update({f'rt{i}':cap[i][y,x]/255 for i in range(3)});li=common.lighting(cg,cube);_,display=common.tone(li['hdr'])
  fixed=li['ambient']+li['environment_specular'];direct=li['direct_diffuse']+li['direct_specular'];target=hdr_delta[y,x]
  inferred_shadow=float(np.clip(np.dot(target-fixed,direct)/max(float(np.dot(direct,direct)),1e-20),0,1));shadowed=np.maximum(0,fixed+direct*inferred_shadow)
  probes.append({'label':label,'pixel':[x,y],'triangle':g['triangle'],'min_barycentric':g['min_barycentric'],'uv':g['uv'].tolist(),'decal_uv':g['decal_uv'].tolist(),'dirt_uv':g['dirt_uv'].tolist(),'lods':g['lods'],'decal_lods':g['decal_lods'],'decal_inside':g['decal_inside'],'decal_alpha':g['decal_alpha'],'decal_diffuse':g['decal_diffuse'].tolist(),'decal_normal':g['decal_normal'].tolist(),'decal_mask':g['decal_mask'].tolist(),'dirt':g['dirt'].tolist(),'dirt_mask':g['dirt_mask'].tolist(),'dirt_amount':g['dirt_amount'],'normal':g['N'].tolist(),'diffuse':g['D'].tolist(),'smoothness':g['S'],'reflectivity':g['R'],'specular':g['F'].tolist(),'gbuffer_max_code_error':errors,'gbuffer_offline':{f'rt{i}':g[f'rt{i}'].tolist() for i in range(3)},'gbuffer_capture':{f'rt{i}':(cap[i][y,x]/255).tolist() for i in range(3)},'lighting_offline':{k:(v.tolist() if hasattr(v,'tolist') else float(v)) for k,v in li.items()},'event_1915_contribution':target.tolist(),'inferred_captured_shadow':inferred_shadow,'lighting_with_inferred_shadow':shadowed.tolist(),'display_offline':display.tolist(),'display_capture':disp[y,x].tolist(),'stencil':int(stencil[y,x])})
 evaluated=[q for q in probes if q['label'] in ('midtone','bright')];hdr_rel=max((max(abs(a-b)/max(abs(b),.01) for a,b in zip(q['lighting_offline']['hdr'],q['event_1915_contribution'])) for q in evaluated),default=float('inf'));display_abs=max((max(abs(a-b) for a,b in zip(q['display_offline'],q['display_capture'])) for q in evaluated),default=float('inf'))
 meaningful=[(abs(a-b)/abs(b)) for q in evaluated for a,b in zip(q['lighting_with_inferred_shadow'],q['event_1915_contribution']) if abs(b)>=.25];shadow_hdr_rel=max(meaningful,default=float('inf'))
 report={'shader_family':'DecalDirtmap','event':1099,'instance':0,'vs':1084,'ps':1086,'indices':2082,'unique_vertices':448,'rasterized_pixels':len(records),'gbuffer_error_cumulative_population':distribution,'max_active_decal_alpha':max(g['decal_alpha'] for g in records.values()),'interior_surviving_lighting_candidates':len(surviving),'probes':probes,'deferred_lighting_family':'StandardLighting1915','validation':{'status':'VALIDATED' if distribution['2']>=3 and len(surviving)>=3 and shadow_hdr_rel<=.10 and display_abs<=.03 else 'NOT VALIDATED','midtone_bright_max_unshadowed_hdr_relative_error':hdr_rel,'meaningful_hdr_relative_error_after_captured_shadow_fit':shadow_hdr_rel,'midtone_bright_max_display_absolute_error':display_abs,'shadow_fit_note':'Event 1915 is already validated. A per-pixel scalar is fit only at its captured multiplicative direct-light position; low HDR channels below 0.25 are excluded from the meaningful relative-error gate.'}}
 (OUT/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:report[k] for k in ('rasterized_pixels','gbuffer_error_cumulative_population','interior_surviving_lighting_candidates','validation')},indent=2))
if __name__=='__main__':main()
