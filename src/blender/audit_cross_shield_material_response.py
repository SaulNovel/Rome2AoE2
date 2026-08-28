"""Cheap source-texture and standardized-lighting audit for shield materials."""
import json,math,sys
from pathlib import Path
import bpy,numpy as np

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src/blender"))
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production

CASES=(
 ("principes","roman_early_scutum_lod1"),
 ("celtic-warriors","celtic_oval_shield_a_lod1"),
 ("hoplites","hellenic_shield_hoplon_lod1"),
)
LUMA=np.array((.2126,.7152,.0722),np.float32)

def srgb(a):
 a=np.asarray(a,np.float32);return np.where(a<=.04045,a/12.92,((a+.055)/1.055)**2.4)
def texture(path,linear=False):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);data=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(data);a=data.reshape(im.size[1],im.size[0],4).copy();bpy.data.images.remove(im);return a if linear else np.concatenate((srgb(a[...,:3]),a[...,3:4]),-1)
def luminance(v):return float(np.dot(v,LUMA))
def main():
 bpy.ops.wm.read_factory_settings(use_empty=True);production.camera(bpy.context.scene);scene=bpy.context.scene
 V=np.array(scene.camera.matrix_world.to_quaternion()@runtime.Vector((0,0,1)),np.float32);V/=np.linalg.norm(V)
 axis=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float32);L=axis@(-runtime.SUN_DIRECTION_R2);L/=np.linalg.norm(L);cube=runtime.load_cube(runtime.REC/"s_environment.dds")
 result={"format":"rome2aoe2.cross-shield-material-response","version":1,"standardized_orientations":[],"shields":[]}
 vectors=(("sun-facing",L),("dark-facing",-L),("specular-aligned",runtime.normalize(L+V)),("oblique",runtime.normalize(L+np.array((0,0,1),np.float32))))
 for label,n in vectors:result["standardized_orientations"].append({"label":label,"normal":np.asarray(n).tolist()})
 for unit,name in CASES:
  base=ROOT/"build/local-integration/rome2/cross-unit-calibration/units"/unit;doc=json.loads((base/"texture-manifest.json").read_text());m=next(x for x in doc["materials"] if x["material_name"]==name);paths={t["semantic"]:base/"textures"/t["extracted_path"] for t in m["textures"] if t["status"]=="resolved"}
  D=texture(paths["Diffuse"])[...,:3].reshape(-1,3).mean(0);F=texture(paths["Specular"])[...,:3].reshape(-1,3).mean(0);G=texture(paths["GlossMap"]);S=float(G[...,0].mean());R=float(G[...,1].mean());probes=[]
  for orientation in result["standardized_orientations"]:
   N=np.array(orientation["normal"],np.float32);refl=runtime.normalize(2*np.dot(N,V)*N-V);nd=max(0,float(np.dot(N,L)));angle=math.acos(float(np.clip(np.dot(refl,L),-1,1)));drop=math.cos(math.radians(1));surface=R+(1-R)*max(0,float(np.dot(L,-V)))**60;dr=float(np.clip((np.dot(N,L)+drop)/drop,0,1)*runtime.facet_fraction(np.array(S),np.array(angle))*surface);env_surface=R+(1-R)*max(0,float(np.dot(refl,-V)))**60;er=max(R,float(np.clip((np.dot(N,refl)+drop)/drop,0,1)*runtime.facet_fraction(np.array(S),np.array(0))*env_surface));env=runtime.cube_sample(cube,refl[None,:],np.array([(1-S)*8]))[0];direct_spec=dr*F*runtime.SUN_COLOUR;direct_diff=D*nd*runtime.SUN_COLOUR*.004*(1-max(dr,R));env_spec=env*er*F*2.5;probes.append({"orientation":orientation["label"],"direct_diffuse":luminance(direct_diff),"direct_specular":luminance(direct_spec),"environment_specular":luminance(env_spec)})
  means={k:float(np.mean([p[k] for p in probes])) for k in ("direct_diffuse","direct_specular","environment_specular")};spec_share=(means["direct_specular"]+means["environment_specular"])/max(sum(means.values()),1e-9)
  result["shields"].append({"unit_catalog":unit,"material":name,"family":m["material_type"],"diffuse_input_luminance":luminance(D),"specular_rgb":F.tolist(),"smoothness":S,"reflectivity":R,"representative_orientations":probes,"mean_contributions":means,"specular_share":spec_share})
 out=ROOT/"build/test-renders/rome2aoe2/cross-shield-material-response-v1";out.mkdir(parents=True,exist_ok=True);(out/"report.json").write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
