"""Assemble and render a manifest-selected Rome II unit without animation."""
import argparse
import json
import math
import os
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
sys.path.insert(0, str(ROOT / "src"))
import render_hastati_runtime_parity as runtime  # noqa: E402
import rome2_exact_material_backend as exact_materials  # noqa: E402
from crest_attachment import mesh_for_asset, seat_crest  # noqa: E402
from weapon_grip import AttachmentClass, classify_rigid_attachment, solve_weapon_grip  # noqa: E402
from rome2.rmv2_named_attachment import named_attachment_local  # noqa: E402


def load_texture_manifest(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("format") != "rome2aoe2.texture-manifest" or document.get("version") != 1:
        raise ValueError("unsupported texture manifest format/version")
    if not isinstance(document.get("materials"), list):
        raise ValueError("texture manifest requires materials")
    return document


AXIS = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
AXIS_INV = AXIS.inverted()
BONES = {"weapon_01": "bn_weapon_01", "weapon_02": "bn_weapon_02",
         "weapon_03": "bn_weapon_03", "weapon_04": "bn_weapon_04", "weapon_05": "bn_weapon_05"}


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def rows(matrix):
    return [[float(matrix[r][c]) for c in range(4)] for r in range(4)]


def import_assets(document):
    imports = {}
    for record in document["exports"]:
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(Path(record["gltf"]).resolve()))
        added = [obj for obj in bpy.data.objects if obj not in before]
        for obj in added:
            obj.name = f"{record['component']}__{obj.name}"
            obj["source_asset"] = record["source_path"]
            obj["manifest_component"] = record["component"]
            if record.get("socket"):
                obj["attachment_role"] = record["component"]
        imports[record["component"]] = (record, added)
    return imports


def purge_export_helpers(imports):
    removed = []
    for _, objects in imports.values():
        for obj in list(objects):
            if obj.type == "MESH" and "icosphere" in obj.name.casefold() and not obj.vertex_groups:
                removed.append(obj.name)
                objects.remove(obj)
                bpy.data.objects.remove(obj, do_unlink=True)
    return removed


def evaluated_vertices(objects):
    bpy.context.view_layer.update()
    graph = bpy.context.evaluated_depsgraph_get()
    result = {}
    for obj in objects:
        if obj.type != "MESH" or not obj.vertex_groups:
            continue
        evaluated = obj.evaluated_get(graph)
        mesh = evaluated.to_mesh()
        result[obj.name] = [evaluated.matrix_world @ vertex.co for vertex in mesh.vertices]
        evaluated.to_mesh_clear()
    return result


def consolidate(imports):
    weighted = [(record, objects) for record, objects in imports.values() if record.get("skeleton")]
    armatures = [obj for _, objects in weighted for obj in objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("selected static assembly has no weighted canonical armature")
    canonical = armatures[0]
    canonical.name = "rome_man_game"
    meshes = [obj for _, objects in weighted for obj in objects if obj.type == "MESH" and obj.vertex_groups]
    before = evaluated_vertices(meshes)
    for _, objects in weighted:
        for obj in objects:
            if obj.type != "MESH" or not obj.vertex_groups:
                continue
            world = obj.matrix_world.copy()
            for modifier in obj.modifiers:
                if modifier.type == "ARMATURE":
                    modifier.object = canonical
            if obj.parent and obj.parent.type == "ARMATURE":
                obj.parent = canonical
                obj.matrix_world = world
    for armature in armatures[1:]:
        bpy.data.objects.remove(armature, do_unlink=True)
    after = evaluated_vertices(meshes)
    delta = max((max(((a - b).length for a, b in zip(points, after[name])), default=0.0)
                 for name, points in before.items()), default=0.0)
    if delta > 1.0e-5:
        raise RuntimeError(f"armature consolidation changed geometry by {delta}")
    return canonical, delta


def apply_pose(armature, path):
    pose = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    desired = {row["name"]: armature.matrix_world.inverted() @ AXIS @ Matrix(row["world_matrix"])
               for row in pose["bones"]}
    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    for row in pose["bones"]:
        bone = armature.pose.bones[row["name"]]
        parent = bone.parent.name if bone.parent else None
        bone.matrix_basis = bone.bone.convert_local_to_pose(
            desired[row["name"]], bone.bone.matrix_local,
            parent_matrix=desired[parent] if parent else Matrix.Identity(4),
            parent_matrix_local=bone.parent.bone.matrix_local if bone.parent else Matrix.Identity(4),
            invert=True)
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()
    if armature.animation_data and armature.animation_data.action:
        raise RuntimeError("static conversion unexpectedly created an Action")
    return {"source": str(path), "frame": pose["frame_index"], "action_created": False}


def helmet_attachment(imports, socket):
    record, _ = imports["helmet"]
    gltf = json.loads(Path(record["gltf"]).read_text(encoding="utf-8"))
    matches = [attachment for material in gltf.get("materials", [])
               for attachment in material.get("extras", {}).get("rome2aoe2", {}).get("attachments", [])
               if attachment.get("name") == socket]
    if not matches:
        raise RuntimeError(f"selected helmet has no {socket} attachment")
    return matches[0]


def attach(imports, armature, blade_capability):
    report = {}
    crest_wrapper = None
    for component, (record, objects) in imports.items():
        socket = record.get("socket")
        if not socket:
            continue
        meshes = [obj for obj in objects if obj.type == "MESH"]
        wrapper = bpy.data.objects.new(f"attachment__{socket}", None)
        bpy.context.scene.collection.objects.link(wrapper)
        constraint = wrapper.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.inverse_matrix = Matrix.Identity(4)
        if socket.startswith("crest_"):
            attachment = helmet_attachment(imports, socket)
            constraint.subtarget = "bn_head"
            local = Matrix(named_attachment_local(attachment["matrix"]))
            wrapper.matrix_basis = AXIS @ local @ AXIS_INV
            crest_wrapper = wrapper
            carrier = "bn_head"
        else:
            if socket not in BONES or BONES[socket] not in armature.pose.bones:
                raise RuntimeError(f"unsupported or absent attachment carrier {socket}")
            constraint.subtarget = BONES[socket]
            wrapper.matrix_basis = AXIS_INV
            carrier = BONES[socket]
        for mesh in meshes:
            source_local = mesh.matrix_basis.copy()
            mesh.parent = wrapper
            mesh.matrix_parent_inverse = Matrix.Identity(4)
            mesh.matrix_basis = source_local
        report[component] = {"socket": socket, "carrier": carrier,
                             "source_asset": record["source_path"], "manual_transform": False,
                             "source_local_transforms": {mesh.name: rows(mesh.matrix_basis) for mesh in meshes}}
        if component == "melee_weapon":
            attachment_class = classify_rigid_attachment(meshes, socket)
            if attachment_class != AttachmentClass.ONE_HANDED_BLADE:
                raise RuntimeError(f"melee attachment is not a validated one-handed blade: {attachment_class.value}")
            report[component]["grip_solver"] = solve_weapon_grip(
                meshes, wrapper, armature, record["source_path"], socket, attachment_class,
                [obj for obj in bpy.context.scene.objects
                 if obj.type == "MESH" and obj.get("manifest_component") == "body"],
                blade_capability)
            if not report[component]["grip_solver"]["validated"]:
                raise RuntimeError(f"source-driven one-handed grip validation failed: {report[component]['grip_solver']}")
            report[component]["grip_solver"]["final_local_transforms"] = {
                mesh.name: rows(mesh.matrix_basis) for mesh in meshes}
    if "crest" in imports:
        if crest_wrapper is None:
            raise RuntimeError("crest selection has no source crest attachment")
        helmet_asset = imports["helmet"][0]["source_path"]
        crest_asset = imports["crest"][0]["source_path"]
        report["crest"]["contact_solver"] = seat_crest(
            armature, mesh_for_asset(helmet_asset, "helmet"), mesh_for_asset(crest_asset, "crest"),
            crest_wrapper, 0, helmet_asset, crest_asset, "crest_centre")
    return report


def bounds():
    points = [obj.matrix_world @ Vector(corner) for obj in bpy.context.scene.objects
              if obj.type == "MESH" and obj.name != "conversion_ground" for corner in obj.bound_box]
    low = Vector(tuple(min(point[index] for point in points) for index in range(3)))
    high = Vector(tuple(max(point[index] for point in points) for index in range(3)))
    return low, high


def review_profile():
    path = ROOT / "config/render_profiles/infantry_static_review_v1.json"
    return json.loads(path.read_text(encoding="utf-8")), path


def studio():
    profile, profile_path = review_profile()
    camera_profile = profile["camera"]
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    # Match the approved Hastati production transform.  AgX Medium High
    # Contrast was the remaining source of crushed cloth, skin, and shield
    # values in the generic preview despite correct source textures.
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.65
    scene.view_settings.gamma = 1.0
    # Lighting and display are evaluated by the exact captured-runtime backend.
    # Blender lamps/world would be dead presentation state and are deliberately
    # omitted so the report cannot imply that they influence the result.
    low, high = bounds(); center = (low + high) * .5
    bpy.ops.mesh.primitive_plane_add(size=max(8.0, max(high - low) * 3), location=(center.x, center.y, low.z - .015))
    ground = bpy.context.object; ground.name = "conversion_ground"
    material = bpy.data.materials.new("conversion_ground_material"); material.diffuse_color = (.055, .06, .065, 1)
    ground.data.materials.append(material)
    camera_data = bpy.data.cameras.new("fixed_conversion_camera")
    camera = bpy.data.objects.new("fixed_conversion_camera", camera_data); scene.collection.objects.link(camera)
    scene.camera = camera; camera.data.type = "ORTHO"
    camera.data.ortho_scale = max(high - low) * camera_profile["orthographic_span_multiplier"]
    distance = camera_profile["distance"]
    elevation = math.radians(camera_profile["elevation_degrees"])
    azimuth = math.radians(camera_profile["azimuth_degrees"])
    target = Vector((center.x, center.y, low.z + (high.z - low.z) * camera_profile["target_height_fraction"]))
    camera.location = target + Vector((distance * math.cos(elevation) * math.cos(azimuth),
                                       distance * math.cos(elevation) * math.sin(azimuth),
                                       distance * math.sin(elevation)))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return {"profile": profile["name"], "status": profile["status"],
            "profile_path": str(profile_path), "configuration": profile,
            "camera": {"fixed": True, "ortho_scale": camera.data.ortho_scale,
                       "geometry_derived_target": list(target)}, "ground_z": ground.location.z}


def exact_material_report(document):
    manifest = load_texture_manifest(document["texture_manifest"])
    families = sorted({row["material_type"] for row in manifest["materials"]})
    return {"backend": "rome2_exact_material_backend",
            "preparation": "runtime_material_preparation",
            "lighting_display": "frozen captured Rome II runtime backend",
            "families": families, "approximations": [],
            "faction_colours": document["faction_colours"]}


def exact_render(scene, document, output, filename, size, *, environment_yaw_degrees=None,
                 readability_fill=0.0, shield_readability=None, weapon_readability=None):
    runtime.OUT = output
    runtime.AOV = output / "aov-working" / str(os.getpid())
    runtime.OUT.mkdir(parents=True, exist_ok=True); runtime.AOV.mkdir(parents=True, exist_ok=True)
    runtime.RESOLUTION = size
    scene.render.resolution_x = scene.render.resolution_y = size
    scene.render.resolution_percentage = 100; scene.render.film_transparent = True
    scene.render.image_settings.file_format = "OPEN_EXR"; scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"; scene.render.image_settings.exr_codec = "ZIP"
    scene.display_settings.display_device = "sRGB"; scene.view_settings.view_transform = "Raw"
    scene.view_settings.look = "None"; scene.view_settings.exposure = 0; scene.view_settings.gamma = 1
    arrays = {name: runtime.render_aov(scene, output, name, Path(document["texture_root"]))
              for name in exact_materials.RAW_AOVS}
    semantic_role = runtime.render_aov(scene, output, "semantic_role", Path(document["texture_root"])) if shield_readability or weapon_readability else None
    profile, _ = review_profile()
    if environment_yaw_degrees is None:
        environment_yaw_degrees = profile["lighting"]["environment_yaw_degrees"]
    runtime.shade(scene, arrays,
                  environment_yaw_degrees=environment_yaw_degrees,
                  readability_fill=readability_fill,
                  semantic_role_aov=semantic_role, shield_readability=shield_readability,
                  weapon_readability=weapon_readability,
                  output_name=filename, diagnostics=False)
    return str(output / filename)


def render_views(document, output, armature):
    scene = bpy.context.scene; outputs = []
    root = bpy.data.objects.new("manifest_unit_direction_root", None)
    scene.collection.objects.link(root)
    armature_world = armature.matrix_world.copy()
    armature.parent = root
    armature.matrix_world = armature_world
    ground = bpy.data.objects.get("conversion_ground")
    if ground is not None:
        ground.hide_render = True
    for angle in document["directions"]:
        root.rotation_euler[2] = math.radians(angle)
        bpy.context.view_layer.update()
        outputs.append(exact_render(scene, document, output, f"static-{angle:03d}.png", 900))
    root.rotation_euler[2] = math.radians(document["directions"][0])
    bpy.context.view_layer.update()
    outputs.append(exact_render(scene, document, output, "static-diagnostic.png", 1400))
    root.rotation_euler[2] = 0.0
    return outputs


def main():
    args = arguments(); document = json.loads(args.input.read_text(encoding="utf-8"))
    blade_capability = document.get("one_handed_blade_capability")
    if blade_capability not in {"one_handed_blade_v2_full_source_frame",
                                "one_handed_blade_v3_source_frame_forward_corrected"}:
        raise RuntimeError("static assembly requires explicit supported one-handed blade semantics")
    args.output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    imports = import_assets(document)
    removed_helpers = purge_export_helpers(imports)
    armature, delta = consolidate(imports)
    pose = apply_pose(armature, document["static_pose"])
    attachments = attach(imports, armature, blade_capability)
    material_report = exact_material_report(document)
    studio_report = studio()
    outputs = render_views(document, args.output, armature)
    blend = args.output / "static-unit.blend"; bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {"format": "rome2aoe2.static-assembly-report", "version": 1,
              "unit": document["unit"], "manifest_hash": document["manifest_hash"],
              "armature": armature.name, "bone_count": len(armature.data.bones),
              "armature_consolidation_max_delta": delta, "static_pose": pose,
              "removed_export_helpers": removed_helpers,
              "attachments": attachments, "materials": material_report, "studio": studio_report,
              "outputs": {"previews": outputs, "blend": str(blend)}, "actions": len(bpy.data.actions)}
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
