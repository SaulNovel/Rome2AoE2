"""Raster-replay Rome II event 1247 from captured PostVS interpolants.

Inputs and proprietary resources stay under ignored build output.  This tool
contains only generic replay/equation logic and deliberately exposes every
intermediate used for validation.
"""
from pathlib import Path
import json, math, struct, sys

ROOT=Path(__file__).resolve().parents[2]
import numpy as np
import bpy

CAP=ROOT/"build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753"
sys.path.insert(0, str(ROOT / "src/rome2"))
from runtime_material_preparation import pack_gbuffer, prepare_weighted
INP=CAP/"weighted-replay"; RES=CAP/"resources-export"
OUT=ROOT/"build/local-integration/rome2/runtime-shader-recovery/weighted-capture-replay"
SUN_DIR=np.array((.752204835,-.368124515,.546509087),np.float32)
SUN=np.array((4744.829102,4335.678711,3330.588623),np.float32)
AMBIENT=np.array((((.757388592,.619574547,.428393602),(.589906037,.479111701,.287942886)),
                  ((.746249497,1.065410614,1.176159620),(.051749278,.068555206,.074733950)),
                  ((.670795798,.542214215,.412173957),(.670795798,.826110303,1.176159620))),np.float32)
CAMERA=np.array((245.62332153320312,366.6048889160156,-421.8184814453125),np.float32)

def srgb(x):
 x=np.asarray(x,np.float32); return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)
def norm(x): return x/np.maximum(np.linalg.norm(x,axis=-1,keepdims=True),1e-20)
def cross2(a,b): return a[0]*b[1]-a[1]*b[0]
def tex(path):
 im=bpy.data.images.load(str(path),check_existing=False); im.colorspace_settings.name='Non-Color'
 q=np.empty(len(im.pixels),np.float32); im.pixels.foreach_get(q); q=q.reshape(im.size[1],im.size[0],4)[::-1].copy()
 bpy.data.images.remove(im); return q
def sample(im,uv,decode=False):
 h,w=im.shape[:2]; x=uv[...,0]*w-.5; y=uv[...,1]*h-.5
 x0=np.floor(x).astype(int); y0=np.floor(y).astype(int); fx=(x-x0)[...,None]; fy=(y-y0)[...,None]
 x0%=w; y0%=h; x1=(x0+1)%w; y1=(y0+1)%h
 q=im[y0,x0]*(1-fx)*(1-fy)+im[y0,x1]*fx*(1-fy)+im[y1,x0]*(1-fx)*fy+im[y1,x1]*fx*fy
 if decode: q[...,:3]=srgb(q[...,:3])
 return q
def decode_ufloat(v,b):
 e=(v>>b)&31; m=v&((1<<b)-1)
 return np.where(e==0,m*np.float32(2**(1-15-b)),(1+m/np.float32(1<<b))*np.exp2(e.astype(np.float32)-15))
def r11(path,w=1920,h=1080):
 p=np.fromfile(path,'<u4').reshape(h,w)
 return np.stack((decode_ufloat(p&0x7ff,6),decode_ufloat((p>>11)&0x7ff,6),decode_ufloat((p>>22)&0x3ff,5)),-1)
def bgra(path,w=1920,h=1080):
 p=np.fromfile(path,np.uint8).reshape(h,w,4); return p[..., [2,1,0,3]]
def load_cube(path):
 raw=path.read_bytes(); off=148; faces=[]
 for face in range(6):
  levels=[]
  for mip in range(9):
   n=max(1,256>>mip); p=np.frombuffer(raw,'<u4',n*n,off).reshape(n,n); off+=n*n*4
   levels.append(np.stack((decode_ufloat(p&0x7ff,6),decode_ufloat((p>>11)&0x7ff,6),decode_ufloat((p>>22)&0x3ff,5)),-1))
  faces.append(levels)
 return faces
def cube_sample(cube,d,lod):
 d=np.asarray(d,np.float32); axis=int(np.argmax(np.abs(d))); pos=d[axis]>=0; a=abs(d[axis]); x,y,z=d
 if axis==0: face=0 if pos else 1; u=(-z if pos else z)/a; v=-y/a
 elif axis==1: face=2 if pos else 3; u=x/a; v=(z if pos else -z)/a
 else: face=4 if pos else 5; u=(x if pos else -x)/a; v=-y/a
 lo=int(np.floor(np.clip(lod,0,8))); hi=min(lo+1,8); f=np.clip(lod,0,8)-lo
 def one(level):
  im=cube[face][level]; n=im.shape[0]; px=(u*.5+.5)*n-.5; py=(v*.5+.5)*n-.5
  x0=int(np.floor(px)); y0=int(np.floor(py)); fx=px-x0; fy=py-y0
  x0=max(0,min(n-1,x0)); y0=max(0,min(n-1,y0)); x1=min(n-1,x0+1); y1=min(n-1,y0+1)
  return im[y0,x0]*(1-fx)*(1-fy)+im[y0,x1]*fx*(1-fy)+im[y1,x0]*(1-fx)*fy+im[y1,x1]*fx*fy
 return one(lo)*(1-f)+one(hi)*f
def erf_ca(x):
 a=.140012; xx=x*x; return np.sign(x)*np.sqrt(max(0,1-np.exp(-xx*(4/math.pi+a*xx)/(1+a*xx))))
def erfinv_ca(x):
 a=.140012; ln=np.log(max(1e-20,1-x*x)); t=2/(math.pi*a)+ln*.5
 return np.sign(x)*np.sqrt(max(0,np.sqrt(max(0,t*t-ln/a))-t))
def facet(s,angle):
 q=.02+.9799*s*s; sigma=max(.0001,math.radians(1)/(math.sqrt(2)*max(erfinv_ca(q),1e-12)))
 return .5*(erf_ca((angle+math.radians(1))/(sigma*math.sqrt(2)))-erf_ca((angle-math.radians(1))/(sigma*math.sqrt(2))))

def material(uv,N,T,B,ims):
 dif=sample(ims[0],uv,True); spe=sample(ims[1],uv,True); nor=sample(ims[2],uv,False); glo=sample(ims[3],uv,True)
 p=prepare_weighted(dif,spe,nor,glo,N,T,B); rt0,rt1,rt2=pack_gbuffer(p)
 return {'alpha':float(p.alpha),'N':p.normal,'D':p.diffuse,'F':p.specular,'S':float(p.smoothness),'R':float(p.reflectivity),
         'rt0':rt0,'rt1':rt1,'rt2':rt2}

def lighting(g,cube):
 N=norm(2*g['rt0'][:3]-1); D=g['rt1'][:3]**2; S=float(g['rt0'][3]); R=float(g['rt1'][3]); F=g['rt2'][:3]
 V=norm(CAMERA-g['world']); L=norm(-SUN_DIR); refl=norm(2*np.dot(N,V)*N-V)
 nd=max(0,float(np.dot(N,L))); angle=math.acos(np.clip(np.dot(refl,L),-1,1)); drop=math.cos(math.radians(1))
 surface=R+(1-R)*max(0,float(np.dot(L,-V)))**60
 dr=np.clip((np.dot(N,L)+drop)/drop,0,1)*facet(S,angle)*surface
 esurf=R+(1-R)*max(0,float(np.dot(refl,-V)))**60
 er=max(R,np.clip((np.dot(N,refl)+drop)/drop,0,1)*facet(S,0)*esurf)
 env=cube_sample(cube,refl,(1-S)*8)
 Na=norm(N*np.array((1,4,1),np.float32)); amb=sum(Na[i]**2*AMBIENT[i,1 if Na[i]<0 else 0] for i in range(3))
 direct_spec=dr*F*SUN; direct_diff=D*nd*SUN*.004*(1-max(dr,R)); ambient=amb*D*.004*(1-R); envspec=env*er*F*2.5
 return {'normal':N,'view':V,'reflection':refl,'ndotl':nd,'environment_sample':env,'ambient':ambient,
         'direct_diffuse':direct_diff,'direct_specular':direct_spec,'environment_specular':envspec,
         'hdr':np.maximum(0,ambient+direct_diff+direct_spec+envspec)}

def tone(hdr):
 lut=np.frombuffer((RES/"g_scurve_texture_sampler.bin").read_bytes(),'<f2').astype(np.float32)
 M=np.array(((.4124564,.2126729,.0193339),(.3575761,.7151522,.1191920),(.1804375,.0721750,.9503041)),np.float32)
 xyz=hdr@M; total=max(float(sum(xyz)),1e-8); Y=np.clip(xyz[1],0,15.5625); x=xyz[0]/total; y=max(xyz[1]/total,1e-8)
 lb=-3.; lw=1.1630859375; black=.0009994507; white=15.5625; c=np.clip((math.log10(max(Y,.011))-lb)/(lw-lb),0,1)*255
 i=int(math.floor(c)); curve=lut[i]*(1-(c-i))+lut[min(i+1,255)]*(c-i); mapped=(10**(curve*(lw-lb)+lb)-black)/(white-black)
 X=mapped*x/y; Z=mapped*(1-x-y)/y
 rgb=np.array((X,mapped,Z))@np.array(((3.2404542,-.9692660,.0556434),(-1.5371385,1.8760108,-.2040259),(-.4985314,.0415560,1.0572252)),np.float32)
 display=np.sqrt(np.clip(rgb*1.2,0,1))*np.array((.964706,.996078,1),np.float32)
 return np.maximum(rgb,0),display

def main():
 OUT.mkdir(parents=True,exist_ok=True); d=json.load(open(INP/"postvs-selected.json")); verts=d['vertices']; ind=d['indices']; W=1920; H=1080
 attrs=('TEXCOORD0','TEXCOORD1','TEXCOORD2','TEXCOORD3','TEXCOORD5')
 zbuf=np.full((H,W),np.inf,np.float32); records={}
 ims=[tex(RES/f"cuirass_0{i}_{name}.dds") for i,name in enumerate(('s_diffuse_map','s_specular_colour_map','s_normal_map','s_gloss_map'))]
 for ti in range(0,len(ind),3):
  vv=[verts[ind[ti+j]] for j in range(3)]; clip=np.array([v['SV_Position'] for v in vv],np.float64); ndc=clip[:,:3]/clip[:,3,None]
  xy=np.stack(((ndc[:,0]*.5+.5)*W,(.5-.5*ndc[:,1])*H),-1); area=cross2(xy[1]-xy[0],xy[2]-xy[0])
  if abs(area)<1e-8: continue
  x0=max(0,int(np.floor(xy[:,0].min()))); x1=min(W-1,int(np.ceil(xy[:,0].max()))); y0=max(0,int(np.floor(xy[:,1].min()))); y1=min(H-1,int(np.ceil(xy[:,1].max())))
  for y in range(y0,y1+1):
   for x in range(x0,x1+1):
    p=np.array((x+.5,y+.5)); b=np.array((cross2(xy[1]-p,xy[2]-p),cross2(xy[2]-p,xy[0]-p),cross2(xy[0]-p,xy[1]-p)))/area
    if np.min(b)<-1e-8: continue
    invw=b/clip[:,3]; invw/=sum(invw); depth=float(np.dot(invw,ndc[:,2]))
    if depth>=zbuf[y,x]: continue
    q={a:sum(invw[j]*np.array(vv[j][a],np.float32) for j in range(3)) for a in attrs}; g=material(q['TEXCOORD1'][:2],q['TEXCOORD2'][:3],q['TEXCOORD3'][:3],q['TEXCOORD5'][:3],ims)
    if g['alpha']<128/255: continue
    g['world']=q['TEXCOORD0'][:3]; g['uv']=q['TEXCOORD1'][:2]; g['triangle']=ti//3; zbuf[y,x]=depth; records[(x,y)]=g
 cap=[bgra(INP/f"gbuffer-rt{i}.raw") for i in range(3)]; finalgb=[bgra(INP/f"gbuffer-final-rt{i}.raw") for i in range(3)]; cube=load_cube(RES/"s_environment.dds"); hdr_cap=r11(INP/"lighting-hdr-rt0.raw"); hdr_before=r11(INP/"lighting-hdr-before-1915.raw"); hdr_delta=np.maximum(0,hdr_cap-hdr_before); tone_cap=r11(INP/"tonemapped-hdr-rt0.raw"); disp=np.fromfile(INP/"display-rt0.raw",np.uint8).reshape(H,W,4)[...,:3]/255
 valid=[]; scored=[]
 for (x,y),g in records.items():
  predicted=[g['rt0'],g['rt1'],g['rt2']]; errors=[float(np.max(np.abs(np.rint(q*255)-cap[i][y,x]))) for i,q in enumerate(predicted)]
  scored.append((max(errors),x,y,g,errors))
  if max(errors)<=2: valid.append((x,y,g,errors))
 scored.sort(key=lambda q:q[0])
 if not valid: valid=[(x,y,g,e) for _,x,y,g,e in scored[:3]]
 surviving=[q for q in valid if all(np.max(np.abs(cap[i][q[1],q[0]].astype(int)-finalgb[i][q[1],q[0]].astype(int)))==0 for i in range(3))]
 # Choose dark/mid/bright by the isolated captured event-1915 contribution.
 litset=surviving if surviving else valid; litset.sort(key=lambda q:float(np.dot(hdr_delta[q[1],q[0]],(.2126,.7152,.0722))))
 chosen=[litset[0],litset[len(litset)//2],litset[-1]]; labels=('dark','midtone','bright')
 probes=[]
 for label,(x,y,g,errors) in zip(labels,chosen):
  li=lighting(g,cube); tm,display=tone(li['hdr'])
  probes.append({'label':label,'pixel':[x,y],'uv':g['uv'].tolist(),'triangle':g['triangle'],
   'gbuffer_offline':{k:g[k].tolist() for k in ('rt0','rt1','rt2')},'gbuffer_capture':{'rt0':(cap[0][y,x]/255).tolist(),'rt1':(cap[1][y,x]/255).tolist(),'rt2':(cap[2][y,x]/255).tolist()},'gbuffer_max_code_error':errors,
   'lighting_offline':{k:(v.tolist() if hasattr(v,'tolist') else float(v)) for k,v in li.items()},'hdr_capture_before_1915':hdr_before[y,x].tolist(),'hdr_capture_after_1915':hdr_cap[y,x].tolist(),'event_1915_hdr_contribution':hdr_delta[y,x].tolist(),
   'tonemapped_no_bloom_offline':tm.tolist(),'tonemapped_capture_with_bloom':tone_cap[y,x].tolist(),'display_offline_no_godrays':display.tolist(),'display_capture':disp[y,x].tolist()})
 allerr=np.array([[np.max(np.abs(np.rint(g['rt0']*255)-cap[0][y,x])),np.max(np.abs(np.rint(g['rt1']*255)-cap[1][y,x])),np.max(np.abs(np.rint(g['rt2']*255)-cap[2][y,x]))] for x,y,g in records.values()]) if False else None
 exact_count=sum(1 for q in scored if q[0]<=2)
 evaluated=[q for q in probes if q['label']!='dark']
 hdr_rel=max(max(abs(a-b)/max(abs(b),.01) for a,b in zip(q['lighting_offline']['hdr'],q['event_1915_hdr_contribution'])) for q in evaluated)
 display_abs=max(max(abs(a-b) for a,b in zip(q['display_offline_no_godrays'],q['display_capture'])) for q in evaluated)
 result={'event':1247,'instance':d['instance'],'rasterized_pixels':len(records),'exact_gbuffer_pixels':exact_count,'best_gbuffer_max_code_errors':[float(q[0]) for q in scored[:10]],'surviving_pixels_at_lighting':len(surviving),'acceptance_threshold_unorm_codes':2,'probes':probes,
         'validation':{'status':'VALIDATED' if exact_count and surviving and hdr_rel<=.10 and display_abs<=.03 else 'NOT VALIDATED','midtone_bright_max_hdr_relative_error':float(hdr_rel),'midtone_bright_max_display_absolute_error':float(display_abs)},
         'cube_mip_means':[[float(np.mean(cube[f][m])) for m in range(9)] for f in range(6)],
         'limitations':['If surviving_pixels_at_lighting is zero, the selected instance is fully overwritten before deferred lighting and its final RGB cannot be compared','event-1915 capture includes exact cascaded/baked shadow and cloud modulation not replayed here','event-2341 capture includes bloom','event-2399 capture includes god rays/background; display comparison is diagnostic only']}
 json.dump(result,open(OUT/"report.json","w"),indent=2)

if __name__=='__main__': main()
