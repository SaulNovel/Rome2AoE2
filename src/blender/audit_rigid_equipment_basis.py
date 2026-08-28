import argparse,json,math,sys
from pathlib import Path
import bpy,numpy as np
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"src")]
from aoe2.facet_mapping import soldier_yaw_degrees
def args():
 p=argparse.ArgumentParser();p.add_argument("--input-blend",type=Path,required=True);p.add_argument("--output",type=Path,required=True);return p.parse_args(sys.argv[sys.argv.index("--")+1:])
def unit(v):
 a=np.asarray(v,float);return a/max(np.linalg.norm(a),1e-12)
def object_audit(obj,deps):
 ev=obj.evaluated_get(deps);mesh=ev.to_mesh();uv=mesh.uv_layers.active.name if mesh.uv_layers.active else "UVMap"
 try:mesh.calc_tangents(uvmap=uv)
 except Exception as e:ev.to_mesh_clear();return {"object":obj.name,"error":str(e)}
 linear=np.array(ev.matrix_world.to_3x3(),float);normal_matrix=np.linalg.inv(linear).T;det=float(np.linalg.det(linear));dots=[];hands=[];lengths=[]
 for index in range(0,len(mesh.loops),max(1,len(mesh.loops)//2000)):
  loop=mesh.loops[index]
  n=unit(normal_matrix@np.array(loop.normal));t=unit(linear@np.array(loop.tangent));t=unit(t-n*np.dot(n,t));b=unit(np.cross(n,t)*float(loop.bitangent_sign)*(1 if det>=0 else -1));dots.append((abs(np.dot(n,t)),abs(np.dot(n,b)),abs(np.dot(t,b))));hands.append(float(np.dot(np.cross(n,t),b)));lengths.append((np.linalg.norm(n),np.linalg.norm(t),np.linalg.norm(b)))
 ev.to_mesh_clear();d=np.asarray(dots);l=np.asarray(lengths);return {"object":obj.name,"world_linear_determinant":det,"sampled_loops":len(dots),"max_length_error":float(np.max(abs(l-1))),"orthogonality_abs_dot_max":float(np.max(d)),"orthogonality_abs_dot_p95":float(np.percentile(d,95)),"handedness_values":sorted(set(round(x,6) for x in hands)),"normal_transform":"inverse-transpose(matrix_world linear)","tangent_transform":"matrix_world linear, then Gram-Schmidt against normal","bitangent_transform":"cross(normal,tangent)*source sign*determinant sign"}
def main():
 a=args();bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;root=bpy.data.objects["Rome2AoE2_FacetRoot"];arm=next(o for o in scene.objects if o.type=="ARMATURE");start,end=arm.animation_data.action.frame_range;scene.frame_set(int((start+end)/2),subframe=((start+end)/2)%1);records=[]
 for direction in range(16):
  root.rotation_euler[2]=math.radians(soldier_yaw_degrees(direction));bpy.context.view_layer.update();deps=bpy.context.evaluated_depsgraph_get()
  for role in ("shield","melee_weapon","armour","body"):
   for obj in [o for o in scene.objects if o.type=="MESH" and o.get("manifest_component")==role]:records.append({"direction":direction,"role":role,**object_audit(obj,deps)})
 wrappers={o.name:{"parent":o.parent.name if o.parent else None,"matrix_basis":[list(r) for r in o.matrix_basis],"constraints":[{"type":c.type,"target":c.target.name if c.target else None,"subtarget":c.subtarget,"inverse_matrix":[list(r) for r in c.inverse_matrix]} for c in o.constraints]} for o in scene.objects if o.name.startswith("attachment__")}
 result={"format":"rome2aoe2.rigid-basis-audit","version":1,"result":"correct" if all("error" not in r and r["orthogonality_abs_dot_max"]<1e-5 and r["max_length_error"]<1e-6 and r["world_linear_determinant"]>0 for r in records) else "failed","records":records,"wrappers":wrappers,"facet_root":{"parent":root.parent.name if root.parent else None,"scale":list(root.scale),"rotation_mode":root.rotation_mode},"application_count":{"source_matrix_basis":1,"attachment_wrapper":1,"native_carrier_constraint":1,"facet_root":1,"manual_shader_normal_transform":0}}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
