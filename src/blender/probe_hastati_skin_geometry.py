"""Recover exact evaluated-triangle UV derivatives for selected skin pixels."""
import json,sys
from pathlib import Path
import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src/blender'))
import render_hastati_runtime_parity as rp
import render_cross_unit_set_a as cu
AUD=rp.OUT/'skin-integration-audit'

def cross(a,b):return a[0]*b[1]-a[1]*b[0]
def bary(xy,p):
 area=cross(xy[1]-xy[0],xy[2]-xy[0]);return np.array((cross(xy[1]-p,xy[2]-p),cross(xy[2]-p,xy[0]-p),cross(xy[0]-p,xy[1]-p)))/area if abs(area)>1e-12 else None

def main():
 points=[q['pixel'] for q in json.loads((AUD/'report.json').read_text())['traces']]
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit('hastati');cu.configure_camera(bpy.context.scene,rp.FACET_AZIMUTH,30,8.5,12);scene=bpy.context.scene;cam=scene.camera;deps=bpy.context.evaluated_depsgraph_get();P=np.array(cam.calc_matrix_camera(depsgraph=deps,x=rp.RESOLUTION,y=rp.RESOLUTION,scale_x=1,scale_y=1));V=np.array(cam.matrix_world.inverted());results=[]
 for pi,(px,py) in enumerate(points):
  best=None
  for obj in scene.objects:
   if obj.type!='MESH':continue
   ev=obj.evaluated_get(deps);mesh=ev.to_mesh();mesh.calc_loop_triangles();uvlayer=mesh.uv_layers.active
   if not uvlayer:ev.to_mesh_clear();continue
   M=np.array(ev.matrix_world)
   for ti,tri in enumerate(mesh.loop_triangles):
    mat=obj.material_slots[tri.material_index].material if tri.material_index<len(obj.material_slots) else None;name=mat.name.split('.')[0] if mat else ''
    if name not in ('roman_body1','roman_1_head'):continue
    world=[];clip=[]
    for vi in tri.vertices:
     q=np.r_[mesh.vertices[vi].co[:],1];w=M@q;c=P@(V@w);world.append(w[:3]);clip.append(c)
    clip=np.array(clip);ndc=clip[:,:3]/clip[:,3,None];xy=np.stack(((ndc[:,0]*.5+.5)*rp.RESOLUTION,(.5-.5*ndc[:,1])*rp.RESOLUTION),-1);p=np.array((px+.5,py+.5));b=bary(xy,p)
    if b is None or np.min(b)<-1e-6:continue
    pw=b/clip[:,3];pw/=sum(pw);depth=float(np.dot(pw,ndc[:,2]));uvs=np.array([uvlayer.data[li].uv[:] for li in tri.loops])
    def at(pp):
     bb=bary(xy,pp);ww=bb/clip[:,3];ww/=sum(ww);return sum(ww[i]*uvs[i] for i in range(3))
    uv=at(p);dx=at(p+np.array((1,0)))-uv;dy=at(p+np.array((0,1)))-uv
    row={'pixel':[px,py],'object':obj.name,'material':name,'triangle':ti,'uv':uv.tolist(),'uv_dx':dx.tolist(),'uv_dy':dy.tolist(),'depth':depth,'source_model':'variantmeshes/_variantmodels/man/skin/roman_skin1_shape1.rigid_model_v2'}
    if best is None or depth<best['depth']:best=row
   ev.to_mesh_clear()
  results.append(best)
 (AUD/'geometry-probes.json').write_text(json.dumps(results,indent=2)+'\n')
if __name__=='__main__':main()
