"""Numeric captured-vs-Blender basis probes for the runtime-parity proof."""
import json, math, sys
from pathlib import Path
import bpy
import numpy as np
from mathutils import Vector, Matrix

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"src/blender"))
import render_cross_unit_set_a as cu
CAP=ROOT/"build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753/basis-probes.json"
OUT=ROOT/"build/local-integration/rome2/runtime-parity-proof/basis-comparison.json"
REC=ROOT/"build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753/resources-export"
TARGETS={1247:("italian_square_muscled_cuirass_","cuirass_02_s_normal_map.dds"),1418:("roman_montefortino","helmet_02_s_normal_map.dds"),1602:("E3_tunic","tunic_03_s_normal_map.dds")}
AXIS=np.array(((1,0,0),(0,0,-1),(0,1,0)),np.float64); SUN=np.array((.752204835,-.368124515,.546509087)); CAM=np.array((245.6233215,366.6048889,-421.8184814))

def norm(v):
 v=np.asarray(v,dtype=np.float64); return v/max(np.linalg.norm(v),1e-12)
def sample_image(path,uv):
 im=bpy.data.images.load(str(path),check_existing=False); im.colorspace_settings.name="Non-Color"; w,h=im.size; data=np.empty(len(im.pixels),np.float32); im.pixels.foreach_get(data); data=data.reshape(h,w,4)
 x=int(math.floor((uv[0]%1)*w))%w; y=int(math.floor((uv[1]%1)*h))%h; value=data[y,x].copy(); bpy.data.images.remove(im); return value
def values(v): return [round(float(x),8) for x in v]

def main():
 cap=json.loads(CAP.read_text()); bpy.ops.wm.read_factory_settings(use_empty=True); root,_=cu.import_unit("hastati"); cu.configure_camera(bpy.context.scene,112.5,30,8.5,12); dg=bpy.context.evaluated_depsgraph_get(); bpy.context.view_layer.update()
 camera_v=norm(np.array(bpy.context.scene.camera.matrix_world.to_quaternion()@Vector((0,0,1))))
 result={"rome_to_blender":AXIS.tolist(),"captured_instance_rotation":"identity","probes":[]}
 for event,(material,normal_file) in TARGETS.items():
  cp=next(x for x in cap[str(event)]["probes"] if x["label"]=="center"); uv=cp["uv"]
  best=None
  for obj in bpy.context.scene.objects:
   if obj.type!='MESH' or not any(slot.material and slot.material.name.split('.')[0]==material for slot in obj.material_slots):continue
   eo=obj.evaluated_get(dg); mesh=eo.to_mesh(); mesh.calc_tangents(uvmap=mesh.uv_layers.active.name); layer=mesh.uv_layers.active.data
   for poly in mesh.polygons:
    if obj.material_slots[poly.material_index].material.name.split('.')[0]!=material:continue
    for li in poly.loop_indices:
     luv=layer[li].uv; du=min(abs(luv.x-uv[0]),1-abs(luv.x-uv[0])); dv=min(abs(luv.y-uv[1]),1-abs(luv.y-uv[1])); score=du*du+dv*dv
     if best is None or score<best[0]:
      loop=mesh.loops[li]; M=eo.matrix_world.to_3x3(); N=norm(M@loop.normal); T=norm(M@loop.tangent); B=norm(np.cross(N,T)*loop.bitangent_sign); pos=np.array(eo.matrix_world@mesh.vertices[loop.vertex_index].co); best=(score,N,T,B,pos,float(loop.bitangent_sign),[float(luv.x),float(luv.y)])
   eo.to_mesh_clear()
  tex=sample_image(REC/normal_file,uv); tx=2*(float(tex[3])+.5/255)-1; ty=2*(float(tex[1])+.5/255)-1; tz=math.sqrt(max(0,1-tx*tx-ty*ty)); tangent=np.array((tx,ty,tz))
  cN=norm(AXIS@np.array(cp["N"])); cT=norm(AXIS@np.array(cp["T"])); cB=norm(AXIS@np.array(cp["B"])); cFinal=norm(tx*cT+ty*cB+tz*cN); cV=norm(AXIS@(CAM-np.array(cp["position"]))); cR=norm(2*np.dot(cFinal,cV)*cFinal-cV)
  _,oN,oT,oB,oPos,sign,ouv=best; oFinal=norm(tx*oT+ty*oB+tz*oN); oR=norm(2*np.dot(oFinal,camera_v)*oFinal-camera_v); L=norm(AXIS@(-SUN))
  result["probes"].append({"event":event,"material":material,"uv_captured":values(uv),"uv_offline":values(ouv),"uv_distance":math.sqrt(best[0]),"decoded_tangent_normal":values(tangent),"captured":{"position":values(AXIS@np.array(cp["position"])),"N":values(cN),"T":values(cT),"B":values(cB),"handedness":cp["handedness"],"final_normal":values(cFinal),"view":values(cV),"ndotl":float(np.dot(cFinal,L)),"reflection":values(cR)},"offline":{"position":values(oPos),"N":values(oN),"T":values(oT),"B":values(oB),"bitangent_sign":sign,"handedness":float(np.dot(norm(np.cross(oT,oB)),oN)),"final_normal":values(oFinal),"view":values(camera_v),"ndotl":float(np.dot(oFinal,L)),"reflection":values(oR)}})
 OUT.write_text(json.dumps(result,indent=2)+"\n")

if __name__=="__main__":main()
