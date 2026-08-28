"""Assemble the Asset Editor Hastati glTF exports on one canonical armature.

This is deliberately an assembly script: it consumes resolved JSON metadata and
already-converted glTF files.  It does not read RMV2 or VMD files.
"""
import json
import math
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[2]
AE = ROOT / "build/community_tool_investigation/asset-editor-hastati-components"
META_ROOT = ROOT / "build/local-integration/rome2/cross-unit-calibration/units/hastati"
OUT = ROOT / "build/local-integration/rome2/hastati-static-assembly"
AXIS = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
AXIS_INV = AXIS.inverted()

FILES = {
    "skin": AE / "skin/roman_skin1_shape1.gltf",
    "tunic": AE / "tunic/e3_tunic.gltf",
    "cuirass": AE / "cuirass/italian_square_muscled_cuirass_a.gltf",
    "helmet": AE / "helmet/roman_montefortino.gltf",
    "crest": AE / "crest/black_feather_03.gltf",
    "shield": AE / "shield/roman_early_scutum.gltf",
    "gladius": AE / "gladius/roman_gladius.gltf",
    "pilum": AE / "pilum/roman_pilum_light.gltf",
}
WEIGHTED = ("skin", "tunic", "cuirass", "helmet")
RIGID = {"shield": "weapon_03", "gladius": "weapon_02", "pilum": "weapon_05"}
BONES = {"weapon_02": "bn_weapon_02", "weapon_03": "bn_weapon_03", "weapon_05": "bn_weapon_05"}
STATIC_POSE = ROOT / "build/local-integration/rome2/animation-v5/sws_stand-frame-0.pose.json"


def mat_rows(matrix):
    return [[float(matrix[r][c]) for c in range(4)] for r in range(4)]


def import_component(name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(FILES[name]))
    added = [o for o in bpy.data.objects if o not in before]
    for o in added:
        o.name = f"{name}__{o.name}"
        o["hastati_component"] = name
    return added


def evaluated_vertices(objects):
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    result = {}
    for obj in objects:
        if obj.type != "MESH" or not obj.vertex_groups:
            continue
        ev = obj.evaluated_get(dg)
        result[obj.name] = [ev.matrix_world @ v.co for v in ev.to_mesh().vertices]
        ev.to_mesh_clear()
    return result


def max_vertex_delta(before, objects):
    after = evaluated_vertices(objects)
    delta = 0.0
    for name, points in before.items():
        if len(points) != len(after[name]):
            raise RuntimeError(f"vertex count changed during consolidation: {name}")
        delta = max(delta, max(((a - b).length for a, b in zip(points, after[name])), default=0.0))
    return delta


def consolidate(imports):
    canonical = next(o for o in imports["skin"] if o.type == "ARMATURE")
    canonical.name = "rome_man_game"
    weighted_meshes = [o for key in WEIGHTED for o in imports[key] if o.type == "MESH" and o.vertex_groups]
    before = evaluated_vertices(weighted_meshes)
    duplicate_arms = []
    for key in WEIGHTED:
        for obj in imports[key]:
            if obj.type == "ARMATURE" and obj != canonical:
                duplicate_arms.append(obj)
            if obj.type != "MESH" or not obj.vertex_groups:
                continue
            for mod in obj.modifiers:
                if mod.type == "ARMATURE":
                    mod.object = canonical
            if obj.parent and obj.parent.type == "ARMATURE":
                world = obj.matrix_world.copy()
                obj.parent = canonical
                obj.matrix_world = world
    for arm in duplicate_arms:
        bpy.data.objects.remove(arm, do_unlink=True)
    delta = max_vertex_delta(before, weighted_meshes)
    if delta > 1.0e-5:
        raise RuntimeError(f"armature consolidation changed evaluated geometry by {delta}")
    return canonical, delta


def resolved_metadata():
    assets = json.loads((META_ROOT / "assets.json").read_text(encoding="utf-8"))
    by_model = {Path(e["source_model"]).stem.lower(): e for e in assets["exports"]}
    expected = {
        "shield": "roman_early_scutum", "gladius": "roman_gladius", "pilum": "roman_pilum_light"
    }
    result = {}
    for component, stem in expected.items():
        row = by_model[stem]
        origin = next(o for o in row["origins"] if o.get("attach_point"))
        result[component] = {
            "selected_component": row["source_model"],
            "attachment_name": origin["attach_point"],
            "slot_path": origin["slot_path"],
            "local_transform": mat_rows(Matrix.Identity(4)),
        }
    helmet = by_model["roman_montefortino"]
    hdoc = json.loads(Path(helmet["gltf"]).read_text(encoding="utf-8"))
    attachment = next(
        a for m in hdoc["materials"]
        for a in m.get("extras", {}).get("rome2aoe2", {}).get("attachments", [])
        if a["name"] == "crest_centre"
    )
    rows = attachment["matrix"]
    local = Matrix((rows[0], rows[1], rows[2], (0, 0, 0, 1)))
    result["crest"] = {
        "selected_component": "variantmeshes/_variantmodels/man/crests/black_feather_03.rigid_model_v2",
        "attachment_name": "crest_centre", "slot_path": "type/helmets/helmets/top_crests",
        "source_bone_id": attachment["bone_id"], "local_transform": mat_rows(local),
    }
    return result


def apply_static_pose(armature):
    """Apply one already-decoded validated pose, without creating an Action."""
    pose = json.loads(STATIC_POSE.read_text(encoding="utf-8-sig"))
    desired = {b["name"]: armature.matrix_world.inverted() @ AXIS @ Matrix(b["world_matrix"]) for b in pose["bones"]}
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    for row in pose["bones"]:
        pb = armature.pose.bones[row["name"]]
        parent_name = pb.parent.name if pb.parent else None
        pb.matrix_basis = pb.bone.convert_local_to_pose(
            desired[row["name"]], pb.bone.matrix_local,
            parent_matrix=desired[parent_name] if parent_name else Matrix.Identity(4),
            parent_matrix_local=pb.parent.bone.matrix_local if pb.parent else Matrix.Identity(4),
            invert=True,
        )
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    if armature.animation_data and armature.animation_data.action:
        raise RuntimeError("static assembly must not contain an animation Action")
    return {"source": str(STATIC_POSE.relative_to(ROOT)), "frame_index": pose["frame_index"],
            "animation_data_created": False, "keyframes_created": False}


def attach(imports, armature, metadata):
    report = {}
    specs = {"crest": ("bn_head", Matrix(metadata["crest"]["local_transform"]))}
    specs.update({k: (BONES[v], Matrix.Identity(4)) for k, v in RIGID.items()})
    for component, (bone_name, local) in specs.items():
        meshes = [o for o in imports[component] if o.type == "MESH"]
        wrapper = bpy.data.objects.new(f"attachment__{metadata[component]['attachment_name']}", None)
        bpy.context.scene.collection.objects.link(wrapper)
        wrapper["vmd_local_transform"] = json.dumps(metadata[component]["local_transform"])
        con = wrapper.constraints.new("CHILD_OF")
        con.target, con.subtarget, con.inverse_matrix = armature, bone_name, Matrix.Identity(4)
        wrapper.matrix_basis = local @ AXIS_INV
        for mesh in meshes:
            mesh.parent = wrapper
            mesh.matrix_parent_inverse = Matrix.Identity(4)
            mesh.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        bone_world = armature.matrix_world @ armature.pose.bones[bone_name].matrix
        report[component] = {
            **metadata[component], "target_bone": bone_name,
            "bone_transform": mat_rows(bone_world),
            "final_object_transform": mat_rows(wrapper.matrix_world),
            "axis_conversion": "local @ Rome-to-Blender inverse basis",
            "manual_visual_placement": False,
        }
    return report


def purge_helpers(imports):
    del imports
    for obj in list(bpy.data.objects):
        if obj.type == "MESH" and not obj.vertex_groups and obj.name.lower().endswith("icosphere"):
            bpy.data.objects.remove(obj, do_unlink=True)


def solid_material():
    mat = bpy.data.materials.get("Assembly Solid") or bpy.data.materials.new("Assembly Solid")
    mat.diffuse_color = (0.55, 0.58, 0.62, 1)
    mat.use_nodes = True
    bs = mat.node_tree.nodes.get("Principled BSDF")
    bs.inputs["Base Color"].default_value = mat.diffuse_color
    bs.inputs["Roughness"].default_value = 0.65
    return mat


def setup_scene():
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Assembly World")
    scene.world.color = (0.055, 0.055, 0.055)
    bpy.ops.object.light_add(type="AREA", location=(3.5, -4.5, 5.5))
    bpy.context.object.data.energy = 850
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 5.0
    bpy.ops.object.light_add(type="AREA", location=(-3, 2, 3))
    bpy.context.object.data.energy = 400
    bpy.context.object.data.size = 4.0


def mesh_bounds(objects):
    pts = [o.matrix_world @ Vector(c) for o in objects if o.type == "MESH" and not o.hide_render for c in o.bound_box]
    return Vector([min(p[i] for p in pts) for i in range(3)]), Vector([max(p[i] for p in pts) for i in range(3)])


def camera_for(objects, view="full", focus=None):
    lo, hi = mesh_bounds(objects)
    center = Vector(focus[0]) if focus else (lo + hi) * 0.5
    span = float(focus[1]) if focus else max(hi - lo)
    if view == "full":
        location = center + Vector((3.8, -5.8, 2.5)).normalized() * span * 3.0
        scale = span * 1.22
    else:
        location = center + Vector((2.2, -3.2, 1.5)).normalized() * span * 3.2
        scale = span * 1.35
    bpy.ops.object.camera_add(location=location)
    cam = bpy.context.object
    cam.data.type, cam.data.ortho_scale = "ORTHO", scale
    cam.rotation_euler = (center - location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    return cam


def render(path, objects, mode, focus=None):
    scene = bpy.context.scene
    old_camera = scene.camera
    cam = camera_for(objects, "full" if mode != "close" else "close", focus)
    scene.render.filepath = str(path)
    scene.render.engine = "BLENDER_WORKBENCH" if mode in ("solid", "wire") else "BLENDER_EEVEE"
    if scene.render.engine == "BLENDER_WORKBENCH":
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "SINGLE"
        scene.display.shading.single_color = (0.58, 0.61, 0.66)
        scene.display.shading.show_shadows = True
        scene.display.shading.show_cavity = True
        scene.display.shading.show_xray = False
        scene.display.shading.show_specular_highlight = False
        scene.display.shading.show_shadows = True
        scene.display.shading.type = "SOLID"
        for o in bpy.context.scene.objects:
            if o.type == "MESH": o.show_wire = mode == "wire"
    wire_mods = []
    if mode == "wire":
        for o in objects:
            mod = o.modifiers.new("proof_wireframe", "WIREFRAME")
            mod.thickness = 0.0012
            mod.use_replace = True
            wire_mods.append((o, mod))
    bpy.ops.render.render(write_still=True)
    for o, mod in wire_mods:
        o.modifiers.remove(mod)
    for o in bpy.context.scene.objects:
        if o.type == "MESH": o.show_wire = False
    bpy.data.objects.remove(cam, do_unlink=True)
    scene.camera = old_camera


def validate(armature, imports, consolidation_delta, attachments):
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE"]
    weighted = [o for o in bpy.context.scene.objects if o.type == "MESH" and o.vertex_groups]
    rows = []
    for o in weighted:
        mods = [m for m in o.modifiers if m.type == "ARMATURE"]
        rows.append({"object": o.name, "component": o.get("hastati_component"),
                     "vertex_group_count": len(o.vertex_groups),
                     "armature_modifiers": [{"name": m.name, "object": m.object.name if m.object else None} for m in mods],
                     "parent": o.parent.name if o.parent else None,
                     "parent_type": o.parent_type})
    if len(armatures) != 1 or len(armature.data.bones) != 50:
        raise RuntimeError(f"expected one 50-bone armature, got {[(a.name,len(a.data.bones)) for a in armatures]}")
    if any(m["object"] != armature.name for r in rows for m in r["armature_modifiers"]):
        raise RuntimeError("a weighted mesh still targets a duplicate armature")
    return {"format": "rome2aoe2.hastati-static-assembly", "version": 1,
            "source_conversion": "Asset Editor glTF only", "armature_count": 1,
            "canonical_armature": armature.name, "bone_count": len(armature.data.bones),
            "weighted_mesh_objects": rows, "consolidation_max_evaluated_vertex_delta": consolidation_delta,
            "attachments": attachments, "manual_visual_placement": False}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imports = {name: import_component(name) for name in FILES}
    armature, delta = consolidate(imports)
    purge_helpers(imports)
    static_pose = apply_static_pose(armature)
    metadata = resolved_metadata()
    attachments = attach(imports, armature, metadata)
    setup_scene()
    all_meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    report = validate(armature, imports, delta, attachments)
    report["static_pose"] = static_pose
    original_materials = {o.name: [m for m in o.data.materials] for o in all_meshes}
    solid = solid_material()
    for o in all_meshes:
        o.data.materials.clear(); o.data.materials.append(solid)
    render(OUT / "complete-hastati-solid.png", all_meshes, "solid")
    render(OUT / "complete-hastati-wireframe.png", all_meshes, "wire")
    for o in all_meshes:
        o.data.materials.clear()
        for m in original_materials[o.name]: o.data.materials.append(m)
    sys_path = str(ROOT / "src/blender")
    import sys
    if sys_path not in sys.path: sys.path.insert(0, sys_path)
    from render_material_reconstruction_v1 import reconstruct, TEST
    reconstruct(META_ROOT, TEST["neutral"], True)
    render(OUT / "complete-hastati-current-materials.png", all_meshes, "materials")
    close_sets = {
        "helmet-crest": ([o for o in all_meshes if o.get("hastati_component") in ("helmet", "crest")], (attachments["crest"]["final_object_transform"][0][3], attachments["crest"]["final_object_transform"][1][3], attachments["crest"]["final_object_transform"][2][3]), .72),
        "shield-hand": ([o for o in all_meshes if o.get("hastati_component") in ("skin", "shield")], armature.pose.bones["bn_lefthand"].matrix.translation, .78),
        "gladius": ([o for o in all_meshes if o.get("hastati_component") in ("skin", "gladius")], armature.pose.bones["bn_righthand"].matrix.translation, .68),
        "pilum": ([o for o in all_meshes if o.get("hastati_component") in ("skin", "pilum")], armature.pose.bones["bn_weapon_05"].matrix.translation, .82),
    }
    for name, (objects, center, scale) in close_sets.items():
        hidden = {o: o.hide_render for o in all_meshes}
        for o in all_meshes: o.hide_render = o not in objects
        render(OUT / f"close-{name}-attachment.png", objects, "close", (center, scale))
        for o, value in hidden.items(): o.hide_render = value
    (OUT / "assembly-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "complete-hastati.blend"))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
