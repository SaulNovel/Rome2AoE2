"""Import a canonical Rome2AoE2 animation JSON as one lossless Blender Action."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


AXIS = Matrix(((1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
AXIS_INV = AXIS.inverted()
EQUIPMENT_BONES = {
    "weapon_02": "bn_weapon_02",
    "weapon_03": "bn_weapon_03",
    "weapon_05": "bn_weapon_05",
}


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation-json", type=Path, required=True)
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--scene-fps", type=int, default=60)
    parser.add_argument("--timeline-start", type=float, default=1.0)
    parser.add_argument("--dependency-manifest", type=Path)
    parser.add_argument("--helmet-gltf", type=Path)
    parser.add_argument("--active-weapon-bones", default="")
    parser.add_argument("--equipment-gltf", action="append", default=[])
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def rows_matrix(rows):
    return Matrix(tuple(tuple(value for value in row) for row in rows))


def parse_keyed_paths(values):
    result = {}
    for value in values:
        key, separator, path = value.partition("=")
        if not separator or key not in EQUIPMENT_BONES:
            raise RuntimeError(f"invalid --equipment-gltf '{value}'")
        result[key] = Path(path)
    return result


def provenance_by_attachment(path):
    if path is None:
        return {}
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("format_version") != 3:
        raise RuntimeError("equipment parenting requires dependency manifest format_version 3")
    result = {}
    for dependency in document["dependencies"]:
        for origin in dependency["origins"]:
            attach = origin.get("attach_point")
            if (
                attach in EQUIPMENT_BONES
                and dependency["normalized_path"].endswith(".rigid_model_v2")
                and attach not in result
            ):
                result[attach] = {
                    "source_model": dependency["normalized_path"],
                    "slot_path": origin["slot_path"],
                    "attach_point": attach,
                }
    return result


def find_armature():
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(armatures) != 1:
        raise RuntimeError(f"expected one armature, found {len(armatures)}")
    return armatures[0]


def import_rigid(path, name):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    meshes = [obj for obj in bpy.data.objects if obj not in before and obj.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"{path}: no rigid meshes imported")
    for index, mesh in enumerate(meshes):
        mesh.name = name if len(meshes) == 1 else f"{name}_{index}"
    return meshes


def existing_equipment(key):
    return [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and key in obj.name]


def attach_equipment(armature, provenance, keyed_paths, active):
    result = {}
    for key, bone_name in EQUIPMENT_BONES.items():
        if key not in provenance:
            raise RuntimeError(f"version-3 provenance is missing {key}")
        objects = existing_equipment(key)
        if not objects and key in keyed_paths:
            objects = import_rigid(keyed_paths[key], f"equipment_{key}")
        if not objects:
            raise RuntimeError(f"no object or glTF was supplied for {key}")

        # Blender's imported bone basis is AXIS * RomeWorld. The wrapper's
        # deterministic AXIS_INV basis converts it to AXIS*RomeWorld*AXIS_INV;
        # each equipment mesh then has an identity attachment-local transform.
        wrapper = bpy.data.objects.new(f"attachment_{key}", None)
        bpy.context.scene.collection.objects.link(wrapper)
        constraint = wrapper.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.subtarget = bone_name
        constraint.inverse_matrix = Matrix.Identity(4)
        wrapper.matrix_basis = AXIS_INV
        for obj in objects:
            original = obj.matrix_world.copy()
            obj.parent = wrapper
            obj.matrix_parent_inverse = Matrix.Identity(4)
            obj.matrix_basis = Matrix.Identity(4)
            obj.hide_viewport = key not in active
            obj.hide_render = key not in active
            if original.translation.length > 1.0e-6:
                # Existing static proof transforms are discarded deliberately;
                # attachment comes only from the provenance-selected bone.
                pass
        result[key] = {
            **provenance[key],
            "bone_name": bone_name,
            "active": key in active,
            "mesh_count": len(objects),
            "attachment_local": "identity",
            "axis_conversion": "shared Rome-to-Blender basis wrapper",
            "manual_correction": False,
        }
    return result


def ensure_crest_parenting(armature, helmet_gltf):
    crests = [obj for obj in bpy.context.scene.objects if obj.type == "MESH" and "crest" in obj.name.lower()]
    if not crests:
        return {"present": False}
    if helmet_gltf is None:
        raise RuntimeError("crest parenting requires --helmet-gltf attachment metadata")
    helmet = json.loads(helmet_gltf.read_text(encoding="utf-8"))
    attachment = next(
        item
        for item in helmet["materials"][0]["extras"]["rome2aoe2"]["attachments"]
        if item["name"] == "crest_centre"
    )
    if attachment["bone_id"] != 23:
        raise RuntimeError("crest_centre does not target verified bone 23")
    rows = attachment["matrix"]
    attachment_local = Matrix((rows[0], rows[1], rows[2], (0, 0, 0, 1)))
    for crest in crests:
        wrapper = bpy.data.objects.new("attachment_crest_centre", None)
        bpy.context.scene.collection.objects.link(wrapper)
        constraint = wrapper.constraints.new("CHILD_OF")
        constraint.target = armature
        constraint.subtarget = "bn_head"
        constraint.inverse_matrix = Matrix.Identity(4)
        wrapper.matrix_basis = attachment_local @ AXIS_INV
        crest.parent = wrapper
        crest.matrix_parent_inverse = Matrix.Identity(4)
        crest.matrix_basis = Matrix.Identity(4)
    return {
        "present": True,
        "bone_name": "bn_head",
        "attachment": "crest_centre",
        "mesh_count": len(crests),
        "manual_correction": False,
    }


def create_action(armature, animation, scene_fps, timeline_start):
    if animation.get("format") != "rome2aoe2.animation" or animation.get("version") != 1:
        raise RuntimeError("unsupported canonical animation document")
    frames = animation["frames"]
    if len(frames) != animation["sample_count"] or not frames:
        raise RuntimeError("animation frame list does not match sample_count")
    if scene_fps <= 0:
        raise RuntimeError("scene FPS must be positive")

    bpy.context.scene.render.fps = scene_fps
    bpy.context.scene.render.fps_base = 1.0
    armature.animation_data_create()
    action = bpy.data.actions.new(animation["animation"])
    armature.animation_data.action = action
    sample_positions = []

    bpy.context.view_layer.objects.active = armature
    bpy.ops.object.mode_set(mode="POSE")
    for source_frame in frames:
        blender_frame = timeline_start + source_frame["time_seconds"] * scene_fps
        sample_positions.append(blender_frame)
        bpy.context.scene.frame_set(int(round(blender_frame)), subframe=blender_frame - round(blender_frame))
        desired = {
            bone["name"]: armature.matrix_world.inverted() @ AXIS @ rows_matrix(bone["world_matrix"])
            for bone in source_frame["bones"]
        }
        for bone in source_frame["bones"]:
            pose_bone = armature.pose.bones.get(bone["name"])
            if pose_bone is None:
                raise RuntimeError(f"armature is missing bone {bone['name']}")
            pose_bone.rotation_mode = "QUATERNION"
            parent_name = pose_bone.parent.name if pose_bone.parent else None
            pose_bone.matrix_basis = pose_bone.bone.convert_local_to_pose(
                desired[bone["name"]],
                pose_bone.bone.matrix_local,
                parent_matrix=desired[parent_name] if parent_name else Matrix.Identity(4),
                parent_matrix_local=(
                    pose_bone.parent.bone.matrix_local if pose_bone.parent else Matrix.Identity(4)
                ),
                invert=True,
            )
        bpy.context.view_layer.update()
        channels = {
            bone["name"]: (
                armature.pose.bones[bone["name"]].location.copy(),
                armature.pose.bones[bone["name"]].rotation_quaternion.copy(),
            )
            for bone in source_frame["bones"]
        }
        for bone in source_frame["bones"]:
            pose_bone = armature.pose.bones[bone["name"]]
            pose_bone.location = channels[bone["name"]][0]
            pose_bone.rotation_quaternion = channels[bone["name"]][1]
            pose_bone.keyframe_insert("location", frame=blender_frame, group=bone["name"])
            pose_bone.keyframe_insert("rotation_quaternion", frame=blender_frame, group=bone["name"])
    bpy.ops.object.mode_set(mode="OBJECT")

    keyframe_points = 0
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                curves.extend(channelbag.fcurves)
    for curve in curves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"
            keyframe_points += 1
    expected_points = len(frames) * len(animation["frames"][0]["bones"]) * 7
    if keyframe_points != expected_points:
        raise RuntimeError(f"expected {expected_points} keyframe points, found {keyframe_points}")
    return action, sample_positions, len(curves), keyframe_points


def sampled_scene_validation(armature, positions, animation):
    weighted = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH" and any(mod.type == "ARMATURE" for mod in obj.modifiers)
    ]
    samples = []
    follow_error = 0.0
    pose_error = 0.0
    selected = [0, len(positions) // 2, len(positions) - 1]
    for source_index in selected:
        frame = positions[source_index]
        bpy.context.scene.frame_set(int(round(frame)), subframe=frame - round(frame))
        bpy.context.view_layer.update()
        points = []
        depsgraph = bpy.context.evaluated_depsgraph_get()
        for obj in weighted:
            evaluated = obj.evaluated_get(depsgraph)
            points.extend(evaluated.matrix_world @ Vector(corner) for corner in evaluated.bound_box)
        bounds = {
            "min": [min(point[i] for point in points) for i in range(3)],
            "max": [max(point[i] for point in points) for i in range(3)],
        }
        samples.append({"frame": frame, "weighted_bounds": bounds})
        for bone in animation["frames"][source_index]["bones"]:
            actual = armature.matrix_world @ armature.pose.bones[bone["name"]].matrix
            expected = AXIS @ rows_matrix(bone["world_matrix"])
            pose_error = max(
                pose_error,
                max(
                    abs(actual[row][column] - expected[row][column])
                    for row in range(4)
                    for column in range(4)
                ),
            )
        for key, bone_name in EQUIPMENT_BONES.items():
            wrapper = bpy.data.objects.get(f"attachment_{key}")
            expected = armature.matrix_world @ armature.pose.bones[bone_name].matrix @ AXIS_INV
            follow_error = max(
                follow_error,
                max(
                    abs(wrapper.matrix_world[row][column] - expected[row][column])
                    for row in range(4)
                    for column in range(4)
                ),
            )
    if any(
        not (-1.0e10 < value < 1.0e10)
        for sample in samples
        for extent in sample["weighted_bounds"].values()
        for value in extent
    ):
        raise RuntimeError("sampled weighted bounds are non-finite or implausibly large")
    return samples, follow_error, pose_error


def main():
    args = arguments()
    animation = json.loads(args.animation_json.read_text(encoding="utf-8-sig"))
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend))
    armature = find_armature()
    action, positions, curve_count, keyframe_points = create_action(
        armature, animation, args.scene_fps, args.timeline_start
    )
    active = {
        f"weapon_{int(value):02}"
        for value in args.active_weapon_bones.split(",")
        if value.strip()
    }
    provenance = provenance_by_attachment(args.dependency_manifest)
    equipment = attach_equipment(
        armature, provenance, parse_keyed_paths(args.equipment_gltf), active
    ) if provenance else {}
    crest = ensure_crest_parenting(armature, args.helmet_gltf)
    sampled_validation, equipment_follow_error, pose_matrix_error = sampled_scene_validation(
        armature, positions, animation
    )

    start = positions[0]
    end = positions[-1]
    bpy.context.scene.frame_start = int(start)
    bpy.context.scene.frame_end = int(end)
    bpy.context.scene.frame_set(int(start))
    endpoint_delta = 0.0
    first = animation["frames"][0]
    last = animation["frames"][-1]
    for first_bone, last_bone in zip(first["bones"], last["bones"]):
        endpoint_delta = max(
            endpoint_delta,
            max(abs(a - b) for a, b in zip(first_bone["local_translation"], last_bone["local_translation"])),
            max(abs(a - b) for a, b in zip(first_bone["local_rotation_xyzw"], last_bone["local_rotation_xyzw"])),
        )
    report = {
        "format": "rome2aoe2.blender-animation-validation",
        "version": 1,
        "animation": animation["animation"],
        "scene_fps": args.scene_fps,
        "source_sample_rate": animation["sample_rate"],
        "source_sample_count": animation["sample_count"],
        "endpoint_inclusive": animation["endpoint_inclusive"],
        "action": action.name,
        "action_frame_range": [start, end],
        "inserted_sample_positions": positions,
        "inserted_sample_count": len(positions),
        "fcurve_count": curve_count,
        "keyframe_point_count": keyframe_points,
        "expected_keyframe_point_count": animation["sample_count"] * animation["bone_count"] * 7,
        "linear_interpolation": True,
        "endpoint_max_local_component_delta": endpoint_delta,
        "equipment": equipment,
        "equipment_follow_max_matrix_error": equipment_follow_error,
        "pose_world_max_matrix_error": pose_matrix_error,
        "crest": crest,
        "sampled_scene_validation": sampled_validation,
        "manual_corrections": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
