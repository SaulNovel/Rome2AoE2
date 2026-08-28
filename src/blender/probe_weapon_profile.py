import json, sys
from pathlib import Path
import bpy, numpy as np

blend = Path(sys.argv[sys.argv.index("--") + 1]); output = Path(sys.argv[sys.argv.index("--") + 2])
bpy.ops.wm.open_mainfile(filepath=str(blend.resolve()))
mesh = next(o for o in bpy.data.objects if o.type == "MESH" and o.get("manifest_component") == "melee_weapon")
wrapper = mesh.parent; inv = wrapper.matrix_world.inverted()
points = np.asarray([tuple(inv @ (mesh.matrix_world @ v.co)) for v in mesh.data.vertices])
center = points.mean(0); _,_,vectors=np.linalg.svd(points-center,full_matrices=False); axis=vectors[0]
p=(points-center)@axis; radial=np.linalg.norm(points-center-np.outer(p,axis),axis=1)
edges=np.linspace(p.min(),p.max(),49); rows=[]
for i in range(48):
 mask=(p>=edges[i])&(p<edges[i+1] if i<47 else p<=edges[i+1])
 rows.append({"mid":float((edges[i]+edges[i+1])/2),"count":int(mask.sum()),
              "r_max":float(radial[mask].max()) if mask.any() else 0,
              "r_p90":float(np.percentile(radial[mask],90)) if mask.any() else 0})
output.write_text(json.dumps({"range":[float(p.min()),float(p.max())],"rows":rows},indent=2))
