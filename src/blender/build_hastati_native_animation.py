"""Build a production Hastati scene from an Asset Editor-native glTF Action.

This is the authoritative production animation route. It deliberately reuses
the Action created by Blender's standard glTF importer. Optional walk-style
locomotion centering is isolated on an outer object; death preserves all native
motion. No joint curve is decoded or reconstructed.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix


ATTACHMENTS = ("weapon_02", "weapon_03", "weapon_05", "crest_centre")


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--animated-gltf", type=Path, required=True)
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--action-name", default="AE_NATIVE__sws_walk_162_cm")
    parser.add_argument("--motion-policy", choices=("center-horizontal", "preserve-native"),
                        default="center-horizontal")
    parser.add_argument("--hide-equipment-prefix", action="append", default=[])
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def rows(matrix):
    return [[float(matrix[r][c]) for c in range(4)] for r in range(4)]


def maximum_delta(left, right):
    return max(abs(left[r][c] - right[r][c]) for r in range(4) for c in range(4))


def action_curves(action):
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    result = []
    for layer in action.layers:
        for strip in layer.strips:
            for bag in strip.channelbags:
                result.extend(bag.fcurves)
    return result


def action_fingerprint(action):
    payload = []
    for curve in action_curves(action):
        points = []
        for point in curve.keyframe_points:
            points.append((float(point.co[0]), float(point.co[1]), point.interpolation))
        payload.append((curve.data_path, curve.array_index, points))
    payload.sort(key=lambda item: (item[0], item[1]))
    encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest(), len(payload), sum(len(item[2]) for item in payload)


def attachment_snapshot():
    result = {}
    for key in ATTACHMENTS:
        wrapper = bpy.data.objects.get(f"attachment__{key}") or bpy.data.objects.get(f"attachment_{key}")
        if wrapper is None:
            continue
        child_of = [constraint for constraint in wrapper.constraints if constraint.type == "CHILD_OF"]
        result[key] = {
            "wrapper": wrapper.name,
            "wrapper_local": rows(wrapper.matrix_basis),
            "carrier": child_of[0].subtarget if len(child_of) == 1 else None,
            "children": {child.name: rows(child.matrix_basis) for child in wrapper.children},
        }
    return result


def find_single_armature(objects):
    arms = [obj for obj in objects if obj.type == "ARMATURE"]
    if len(arms) != 1:
        raise RuntimeError(f"expected one imported armature, found {len(arms)}")
    return arms[0]


def main():
    args = arguments()
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    production_arms = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(production_arms) != 1:
        raise RuntimeError(f"expected one production armature, found {len(production_arms)}")
    armature = production_arms[0]
    attachments_before = attachment_snapshot()

    existing = set(bpy.context.scene.objects)
    bpy.ops.import_scene.gltf(filepath=str(args.animated_gltf.resolve()))
    imported = set(bpy.context.scene.objects) - existing
    native_armature = find_single_armature(imported)
    if native_armature.animation_data is None or native_armature.animation_data.action is None:
        raise RuntimeError("standard glTF import did not create an active native Action")
    native_action = native_armature.animation_data.action
    native_slot = native_armature.animation_data.action_slot
    fingerprint_before, curve_count, point_count = action_fingerprint(native_action)

    production_bones = {bone.name for bone in armature.data.bones}
    native_bones = {bone.name for bone in native_armature.data.bones}
    common = sorted(production_bones & native_bones)
    missing_in_production = sorted(native_bones - production_bones)
    production_only = sorted(production_bones - native_bones)
    if missing_in_production:
        raise RuntimeError(f"native animated bones absent from production skeleton: {missing_in_production}")
    rest_delta = max(maximum_delta(armature.data.bones[name].matrix_local,
                                   native_armature.data.bones[name].matrix_local)
                     for name in common)
    if rest_delta > 1e-5:
        raise RuntimeError(f"native and production rest skeletons differ: {rest_delta}")

    if armature.animation_data is None:
        armature.animation_data_create()
    armature.animation_data.action = native_action
    armature.animation_data.action_slot = native_slot
    native_action.name = args.action_name

    # Imported geometry is only an Action/rest-skeleton carrier.  Production
    # geometry, materials, pivots, and rigid attachment objects remain intact.
    for obj in list(imported):
        bpy.data.objects.remove(obj, do_unlink=True)

    facet = bpy.data.objects.new("Rome2AoE2_FacetRoot", None)
    bpy.context.scene.collection.objects.link(facet)
    arm_world = armature.matrix_world.copy()
    center = None
    if args.motion_policy == "center-horizontal":
        center = bpy.data.objects.new("Rome2AoE2_LocomotionCenter", None)
        bpy.context.scene.collection.objects.link(center)
        center.parent = facet
        armature.parent = center
    else:
        armature.parent = facet
    armature.matrix_world = arm_world

    start, end = native_action.frame_range
    curves = action_curves(native_action)
    sample_frames = sorted({float(point.co[0]) for curve in curves for point in curve.keyframe_points})
    source_positions = []
    for frame in sample_frames:
        whole = int(frame)
        bpy.context.scene.frame_set(whole, subframe=frame - whole)
        bpy.context.view_layer.update()
        hips = armature.pose.bones.get("bn_hips")
        if hips is None:
            raise RuntimeError("native skeleton has no bn_hips")
        location = (armature.matrix_world @ hips.matrix).translation.copy()
        source_positions.append((frame, location.x, location.y, location.z))
    reference = source_positions[0]
    if center is not None:
        center.animation_data_clear()
        center.location = (0.0, 0.0, 0.0)
        for frame, x, y, _z in source_positions:
            center.location = (reference[1] - x, reference[2] - y, 0.0)
            center.keyframe_insert(data_path="location", frame=frame, group="External locomotion centering")
        for curve in action_curves(center.animation_data.action):
            for point in curve.keyframe_points:
                point.interpolation = "LINEAR"
        center.location = (0.0, 0.0, 0.0)

    hidden_equipment = []
    for obj in bpy.context.scene.objects:
        if any(obj.name.startswith(prefix) for prefix in args.hide_equipment_prefix):
            obj.hide_render = True
            obj.hide_viewport = True
            hidden_equipment.append(obj.name)

    scene = bpy.context.scene
    scene.frame_start = int(start)
    scene.frame_end = int(round(end))
    scene.frame_set(int(start))
    bpy.context.view_layer.update()
    fingerprint_after, _, _ = action_fingerprint(native_action)
    attachments_after = attachment_snapshot()

    attachment_delta = 0.0
    for key in attachments_before:
        attachment_delta = max(attachment_delta, maximum_delta(
            Matrix(attachments_before[key]["wrapper_local"]),
            Matrix(attachments_after[key]["wrapper_local"])))
        for name, before in attachments_before[key]["children"].items():
            attachment_delta = max(attachment_delta, maximum_delta(
                Matrix(before), Matrix(attachments_after[key]["children"][name])))

    report = {
        "format": "rome2aoe2.hastati-native-production-animation",
        "version": 1,
        "authoritative_route": "Asset Editor RmvToGltfExporter -> Blender glTF importer -> imported Action unchanged",
        "source": str(args.animated_gltf),
        "action": native_action.name,
        "action_identity_preserved": True,
        "joint_action_sha256_before": fingerprint_before,
        "joint_action_sha256_after": fingerprint_after,
        "joint_action_byte_equivalent": fingerprint_before == fingerprint_after,
        "joint_curve_count": curve_count,
        "joint_keyframe_point_count": point_count,
        "rest_skeleton_max_matrix_delta": rest_delta,
        "native_bone_count": len(native_bones),
        "production_bone_count": len(production_bones),
        "production_only_bones": production_only,
        "sample_count": len(sample_frames),
        "action_frame_range": [float(start), float(end)],
        "motion_policy": args.motion_policy,
        "centering": {
            "object": center.name if center is not None else None,
            "parent": facet.name,
            "reference_bone": "bn_hips",
            "horizontal_axes": ["local X", "local Y"],
            "vertical_channel_modified": False,
            "joint_channels_modified": False,
            "samples": [{"frame": f, "source_hips": [x, y, z],
                         "container": ([reference[1] - x, reference[2] - y, 0.0]
                                       if center is not None else [0.0, 0.0, 0.0])}
                        for f, x, y, z in source_positions],
        },
        "hierarchy": ([facet.name, center.name, armature.name]
                      if center is not None else [facet.name, armature.name]),
        "hidden_equipment": sorted(hidden_equipment),
        "attachment_local_max_delta": attachment_delta,
        "attachments": attachments_after,
    }
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
