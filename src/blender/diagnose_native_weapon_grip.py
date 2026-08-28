"""Compare authoritative and heuristic one-handed weapon transforms."""
import argparse, json, math, shutil, sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "src/blender"), str(ROOT / "src/rome2")]
import assemble_manifest_static as exact
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees


def args():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,required=True); p.add_argument("--output",type=Path,required=True); p.add_argument("--metrics-only",action="store_true")
    return p.parse_args(sys.argv[sys.argv.index("--")+1:])


def rows(m): return [[float(m[r][c]) for c in range(4)] for r in range(4)]


def geometry_frame(mesh, wrapper):
    inv=wrapper.matrix_world.inverted(); points=np.asarray([tuple(inv@(mesh.matrix_world@v.co)) for v in mesh.data.vertices],np.float64)
    center=points.mean(0); _,_,vectors=np.linalg.svd(points-center,full_matrices=False); longitudinal=vectors[0]
    if longitudinal[0]<0: longitudinal=-longitudinal
    q=(points-center)@longitudinal; radial=points-center-np.outer(q,longitudinal)
    edges=np.linspace(q.min(),q.max(),49); bands=[]
    for i in range(2,46):
        hit=(q>=edges[i])&(q<edges[i+1])
        if np.count_nonzero(hit)>=4: bands.append((np.percentile(np.linalg.norm(radial[hit],axis=1),90),hit))
    hit=max(bands,key=lambda x:x[0])[1]; cross=radial[hit]; _,_,rv=np.linalg.svd(cross-cross.mean(0),full_matrices=False)
    lateral=rv[0]; lateral-=longitudinal*np.dot(lateral,longitudinal); lateral/=np.linalg.norm(lateral)
    normal=np.cross(longitudinal,lateral); normal/=np.linalg.norm(normal)
    low=center+longitudinal*q.min(); high=center+longitudinal*q.max()
    return {"longitudinal":longitudinal.tolist(),"lateral":lateral.tolist(),"flat_normal":normal.tolist(),
            "handle_endpoint_local":low.tolist(),"blade_tip_local":high.tolist(),
            "handle_endpoint_to_grip":float(np.linalg.norm(low)),"blade_tip_to_grip":float(np.linalg.norm(high)),
            "orthogonality_max_error":float(max(abs(np.dot(longitudinal,lateral)),abs(np.dot(longitudinal,normal)),abs(np.dot(lateral,normal))))}


def hand_distance(arm, wrapper):
    body=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("manifest_component")=="body"]
    graph=bpy.context.evaluated_depsgraph_get(); points=[]
    for source in body:
        group=source.vertex_groups.get("bn_righthand")
        if not group: continue
        ids={v.index for v in source.data.vertices if any(g.group==group.index and g.weight>.01 for g in v.groups)}
        ev=source.evaluated_get(graph); mesh=ev.to_mesh(); points.extend(tuple(ev.matrix_world@mesh.vertices[i].co) for i in ids); ev.to_mesh_clear()
    socket=np.asarray(tuple(wrapper.matrix_world.translation)); surface=float(np.linalg.norm(np.asarray(points)-socket,axis=1).min()) if points else None
    bone=arm.matrix_world@arm.pose.bones["bn_righthand"].matrix.translation
    return surface,float((bone-wrapper.matrix_world.translation).length)


def main():
    a=args(); spec=json.loads(a.input.read_text()); a.output.mkdir(parents=True,exist_ok=True)
    static_doc=json.loads(Path(spec["static_input"]).read_text()); shutil.copyfile(static_doc["texture_manifest"],a.output/"texture-manifest.json")
    source=Matrix(spec["source_local_transform"]); full_frame=Matrix(spec["full_frame_local_transform"]); records=[]
    for clip in spec["clips"]:
        bpy.ops.wm.open_mainfile(filepath=str(Path(clip["blend"]).resolve())); scene=bpy.context.scene; production.camera(scene)
        arm=next(o for o in scene.objects if o.type=="ARMATURE"); action=arm.animation_data.action; start,end=action.frame_range
        wrapper=bpy.data.objects["attachment__weapon_02"]; mesh=next(o for o in scene.objects if o.type=="MESH" and o.get("manifest_component")=="melee_weapon")
        current=mesh.matrix_basis.copy(); phases=[start,(start+end)*.45,end]
        modes=["source","current","full-frame"] if clip.get("selected") else ["full-frame"]
        for mode in modes:
            # Geometry may translate the detected grip to the socket. Rotation
            # and roll remain the complete source/VMD/native-carrier frame.
            mesh.matrix_basis=source.copy() if mode=="source" else (full_frame.copy() if mode=="full-frame" else current.copy())
            local_reference=mesh.matrix_basis.copy()
            for phase_index,value in enumerate(phases):
                whole=int(value); scene.frame_set(whole,subframe=value-whole); bpy.context.view_layer.update()
                frame=geometry_frame(mesh,wrapper); surface,bone=hand_distance(arm,wrapper)
                for direction in (0,4,8,12) if clip.get("selected") else (0,):
                    bpy.data.objects["Rome2AoE2_FacetRoot"].rotation_euler[2]=math.radians(soldier_yaw_degrees(direction)); bpy.context.view_layer.update()
                    name=f"{clip['name']}-{mode}-phase-{phase_index}-direction-{direction:02d}.png"
                    if not a.metrics_only: exact.exact_render(scene,static_doc,a.output,name,384)
                    records.append({"clip":clip["name"],"mode":mode,"phase":phase_index,"blender_frame":float(value),"direction":direction,
                                    "output":str(a.output/name),"hand_surface_to_grip":surface,"hand_bone_origin_to_grip":bone,
                                    "weapon_local_transform":rows(mesh.matrix_basis),"local_transform_invariant":max(abs(mesh.matrix_basis[r][c]-local_reference[r][c]) for r in range(4) for c in range(4))==0,
                                    "geometry_frame":frame})
        mesh.matrix_basis=current
    report_name="weapon-grip-metrics.json" if a.metrics_only else "weapon-grip-diagnostic.json"
    (a.output/report_name).write_text(json.dumps({"format":"rome2aoe2.weapon-grip-diagnostic","version":1,
        "authority":"RMV v_pivot + VMD weapon_02 + native bn_weapon_02 carrier provide full translation and rotation; geometry is validation only",
        "capability_current":"one_handed_blade_v1 longitudinal anatomy alignment; roll not explicitly constrained or validated",
        "capability_proposed":"one_handed_blade_v2 geometry grip translation + source-authoritative full rotation/roll; geometry validates longitudinal/lateral/flat axes without rotating source",
        "records":records},indent=2,sort_keys=True)+"\n")

if __name__=="__main__": main()
