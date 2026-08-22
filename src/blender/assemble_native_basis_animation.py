"""Consolidate Asset Editor-native weighted exports without retargeting."""
import argparse, hashlib, json, re, sys
from pathlib import Path
import bpy

EPSILON = 1e-6

def args():
    p=argparse.ArgumentParser(); p.add_argument("--input",type=Path,required=True); return p.parse_args(sys.argv[sys.argv.index("--")+1:])
def curves(action):
    if hasattr(action,"fcurves"): return list(action.fcurves)
    return [curve for layer in action.layers for strip in layer.strips for bag in strip.channelbags for curve in bag.fcurves]
def fingerprint(action):
    payload=sorted((c.data_path,c.array_index,[(float(p.co[0]),float(p.co[1]),p.interpolation) for p in c.keyframe_points]) for c in curves(action))
    return hashlib.sha256(json.dumps(payload,separators=(",",":")).encode()).hexdigest()
def matrix_delta(a,b): return max(abs(a[r][c]-b[r][c]) for r in range(4) for c in range(4))
def base(name): return re.sub(r"\.\d{3}$","",name)

def main():
    a=args(); doc=json.loads(a.input.read_text()); bpy.ops.wm.open_mainfile(filepath=str(Path(doc["static_blend"]).resolve()))
    static_arm=next(obj for obj in bpy.context.scene.objects if obj.type=="ARMATURE")
    weighted_keys={x["component"] for x in doc["classification"] if x["deformation"]=="weighted"}
    old_meshes=[o for o in bpy.context.scene.objects if o.type=="MESH" and o.get("manifest_component") in weighted_keys]
    material_map={}
    for o in old_meshes:
        for slot in o.material_slots:
            if slot.material:
                material_map[(o.get("manifest_component"),base(slot.material.name))]=[slot.material]
    canonical=None; action=None; before=None; comparisons=[]; imported_meshes=[]
    for record in doc["native_exports"]:
        existing=set(bpy.context.scene.objects); bpy.ops.import_scene.gltf(filepath=str(Path(record["gltf"]).resolve())); imported=set(bpy.context.scene.objects)-existing
        arms=[o for o in imported if o.type=="ARMATURE"]
        if len(arms)!=1: raise RuntimeError(f"expected one native armature for {record['component']}, got {len(arms)}")
        arm=arms[0]; current=arm.animation_data.action
        if canonical is None:
            canonical,action=arm,current; imported_action_name=action.name; before=fingerprint(action)
            action.name="AE_NATIVE__"+Path(doc["clip"]).stem
        else:
            names=[b.name for b in canonical.data.bones]; other=[b.name for b in arm.data.bones]
            parents=[b.parent.name if b.parent else None for b in canonical.data.bones]; other_parents=[b.parent.name if b.parent else None for b in arm.data.bones]
            if names!=other or parents!=other_parents: raise RuntimeError("INCOMPATIBLE_NATIVE_REST_BASIS: bone hierarchy mismatch")
            delta=max(matrix_delta(canonical.data.bones[n].matrix_local,arm.data.bones[n].matrix_local) for n in names)
            if delta>EPSILON: raise RuntimeError(f"INCOMPATIBLE_NATIVE_REST_BASIS: rest delta {delta}")
            comparisons.append({"component":record["component"],"bone_count":len(names),"parent_hierarchy_delta":0,"rest_matrix_max_delta":delta})
        for mesh in [o for o in imported if o.type=="MESH" and o.vertex_groups]:
            mesh["manifest_component"]=record["component"]
            key=(record["component"],base(mesh.name)); mats=material_map.get(key)
            if mats is None: raise RuntimeError(f"stable source mesh/material identity not found: {key}")
            mesh.data.materials.clear()
            for mat in mats: mesh.data.materials.append(mat)
            for mod in mesh.modifiers:
                if mod.type=="ARMATURE": mod.object=canonical
            if mesh.parent==arm: mesh.parent=canonical
            imported_meshes.append(mesh)
        for helper in [o for o in imported if o.type=="MESH" and not o.vertex_groups]: bpy.data.objects.remove(helper,do_unlink=True)
        if arm!=canonical: bpy.data.objects.remove(arm,do_unlink=True)
    for obj in old_meshes: bpy.data.objects.remove(obj,do_unlink=True)
    for obj in bpy.context.scene.objects:
        for con in obj.constraints:
            if con.type=="CHILD_OF" and con.target==static_arm:
                # Preserve the source attachment's physical rest placement
                # while expressing it in the authoritative native carrier
                # basis. This changes only the rigid wrapper, never bones.
                static_bone=static_arm.data.bones.get(con.subtarget); native_bone=canonical.data.bones.get(con.subtarget)
                if static_bone is None or native_bone is None: raise RuntimeError(f"native carrier absent: {con.subtarget}")
                obj.matrix_basis=native_bone.matrix_local.inverted()@static_bone.matrix_local@obj.matrix_basis
                con.target=canonical
    canonical.matrix_world=static_arm.matrix_world.copy(); bpy.data.objects.remove(static_arm,do_unlink=True)
    facet=bpy.data.objects.new("Rome2AoE2_FacetRoot",None); bpy.context.scene.collection.objects.link(facet); canonical.parent=facet
    start,end=action.frame_range; bpy.context.scene.frame_start=int(start); bpy.context.scene.frame_end=int(round(end))
    center=None
    if doc["category"] in {"walk","death"}:
        center_name="Rome2AoE2_LocomotionCenter" if doc["category"]=="walk" else "Rome2AoE2_DeathPreviewHorizontalCenter"
        center=bpy.data.objects.new(center_name,None); bpy.context.scene.collection.objects.link(center); center.parent=facet; canonical.parent=center
        sample_frames=sorted({float(p.co[0]) for c in curves(action) for p in c.keyframe_points})
        positions=[]
        for frame in sample_frames:
            whole=int(frame); bpy.context.scene.frame_set(whole,subframe=frame-whole); bpy.context.view_layer.update()
            point=(canonical.matrix_world@canonical.pose.bones["bn_hips"].matrix).translation; positions.append((frame,point.x,point.y))
        origin=positions[0]
        for frame,x,y in positions:
            center.location=(origin[1]-x,origin[2]-y,0); center.keyframe_insert(data_path="location",frame=frame,group="External locomotion centering")
        for c in curves(center.animation_data.action):
            for p in c.keyframe_points: p.interpolation="LINEAR"
    bpy.context.scene.frame_set(int(start))
    after=fingerprint(action)
    report={"format":"rome2aoe2.native-basis-assembly","version":1,"assembly_version":doc["assembly_version"],
            "classification":doc["classification"],"canonical_armature":canonical.name,"bone_count":len(canonical.data.bones),
            "requested_animation_clip":doc["clip"],"basis_export_clip":doc["native_exports"][0]["export"]["basis_export_clip"],
            "canonical_action_clip":doc["native_exports"][0]["export"]["canonical_action_clip"],
            "runner_reported_action_name":imported_action_name,"canonical_action_name":action.name,
            "canonical_action_identity":"exact requested clip + requested animation SHA-256 + imported curve fingerprint",
            "canonical_action_frame_range":[float(start),float(end)],
            "duplicate_armature_comparisons":comparisons,"action_fingerprint_before":before,"action_fingerprint_after":after,
            "action_fingerprint_preserved":before==after,"weighted_meshes":[{"component":m.get("manifest_component"),"name":m.name,
            "vertices":len(m.data.vertices),"vertex_groups":len(m.vertex_groups),"materials":[s.material.name for s in m.material_slots]} for m in imported_meshes],
            "material_backend":"rome2_exact_material_backend/runtime_material_preparation (preserved approved datablocks)",
            "motion_policy":{"category":doc["category"],"external_container":center.name if center else None,
            "horizontal_only":center is not None,"vertical_modified":False,"action_modified":False},
            "rigid_attachment_carriers":{o.name:[c.subtarget for c in o.constraints if c.type=="CHILD_OF"] for o in bpy.context.scene.objects if o.name.startswith("attachment__")}}
    if before!=after: raise RuntimeError("native Action fingerprint changed")
    Path(doc["output_blend"]).parent.mkdir(parents=True,exist_ok=True); bpy.ops.wm.save_as_mainfile(filepath=str(Path(doc["output_blend"]).resolve())); Path(doc["report"]).write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__": main()
