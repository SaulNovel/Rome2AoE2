"""Render the 8-phase native/centered/complete Hastati walk gate."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PHASES = tuple(index / 8 for index in range(8))


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-gltf", type=Path, required=True)
    parser.add_argument("--production-blend", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def armature():
    arms = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(arms) != 1:
        raise RuntimeError(f"expected one armature, found {len(arms)}")
    return arms[0]


def set_frame(scene, frame):
    whole = int(frame)
    scene.frame_set(whole, subframe=frame - whole)
    bpy.context.view_layer.update()


def pose_snapshot(arm):
    return {bone.name: [[float(bone.matrix_basis[r][c]) for c in range(4)] for r in range(4)]
            for bone in arm.pose.bones}


def matrix_delta(left, right):
    return max(abs(left[r][c] - right[r][c]) for r in range(4) for c in range(4))


def configure_render(output):
    scene = bpy.context.scene
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.camera_add(location=(6.0, -0.66, 1.0))
    camera = bpy.context.object
    camera.name = "NativeWalkGateCamera"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.75
    camera.rotation_euler = (Vector((0.0, -0.66, 1.0)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "MATERIAL"
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.show_specular_highlight = False
    scene.render.resolution_x = 520
    scene.render.resolution_y = 620
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Native walk gate world")
    scene.world.color = (0.025, 0.025, 0.025)
    output.mkdir(parents=True, exist_ok=True)
    return scene


def render_phases(scene, action, output, label):
    start, end = action.frame_range
    frames = [start + phase * (end - start) for phase in PHASES]
    images = []
    for index, frame in enumerate(frames):
        set_frame(scene, frame)
        path = output / f"{index:02d}-{label}.png"
        scene.render.filepath = str(path.resolve())
        bpy.ops.render.render(write_still=True)
        images.append(str(path))
    return frames, images


def set_body_visibility(native):
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        keep = "Icosphere" not in obj.name and (native or obj.name.startswith("skin__"))
        obj.hide_render = not keep
        obj.hide_viewport = not keep


def attachment_relative(arm, wrapper):
    constraints = [item for item in wrapper.constraints if item.type == "CHILD_OF"]
    if len(constraints) != 1 or not constraints[0].subtarget:
        return None
    carrier = arm.pose.bones[constraints[0].subtarget]
    carrier_world = arm.matrix_world @ carrier.matrix
    return carrier_world.inverted_safe() @ wrapper.matrix_world


def main():
    args = arguments()
    root = args.output_root
    report = {"format": "rome2aoe2.native-walk-production-gate", "version": 1,
              "phases": list(PHASES), "rows": {}}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(args.native_gltf.resolve()))
    raw_arm = armature()
    raw_action = raw_arm.animation_data.action
    raw_scene = configure_render(root / "row-A-native-body")
    set_body_visibility(True)
    raw_frames, raw_images = render_phases(raw_scene, raw_action, root / "row-A-native-body", "native-body")
    raw_poses = []
    for frame in raw_frames:
        set_frame(raw_scene, frame)
        raw_poses.append(pose_snapshot(raw_arm))
    report["rows"]["A"] = {"label": "Asset Editor-native / raw Blender body",
                              "frames": raw_frames, "images": raw_images}

    bpy.ops.wm.open_mainfile(filepath=str(args.production_blend.resolve()))
    prod_arm = armature()
    prod_action = prod_arm.animation_data.action
    prod_scene = configure_render(root / "row-B-centered-body")
    if prod_action is None or prod_action.name != "AE_NATIVE__sws_walk_162_cm":
        raise RuntimeError("production scene is not bound to the authoritative native Action")
    prod_frames = [prod_action.frame_range[0] + phase *
                   (prod_action.frame_range[1] - prod_action.frame_range[0]) for phase in PHASES]
    local_delta = 0.0
    for index, frame in enumerate(prod_frames):
        set_frame(prod_scene, frame)
        current = pose_snapshot(prod_arm)
        if set(current) != set(raw_poses[index]):
            raise RuntimeError("raw and production pose bone sets differ")
        for name in current:
            local_delta = max(local_delta, matrix_delta(current[name], raw_poses[index][name]))

    set_body_visibility(False)
    _, body_images = render_phases(prod_scene, prod_action, root / "row-B-centered-body", "centered-body")
    report["rows"]["B"] = {"label": "Production body + outer locomotion centering",
                              "frames": prod_frames, "images": body_images}

    for obj in prod_scene.objects:
        if obj.type == "MESH":
            keep = "Icosphere" not in obj.name
            obj.hide_render = not keep
            obj.hide_viewport = not keep
    complete_dir = root / "row-C-complete-production"
    complete_dir.mkdir(parents=True, exist_ok=True)
    _, complete_images = render_phases(prod_scene, prod_action, complete_dir, "complete-production")
    report["rows"]["C"] = {"label": "Complete production Hastati + outer centering",
                              "frames": prod_frames, "images": complete_images}

    attachment_drift = {}
    for key in ("weapon_02", "weapon_03", "weapon_05", "crest_centre"):
        wrapper = bpy.data.objects.get(f"attachment__{key}")
        if wrapper is None:
            continue
        reference = None
        maximum = 0.0
        for frame in prod_frames:
            set_frame(prod_scene, frame)
            relative = attachment_relative(prod_arm, wrapper)
            if reference is None:
                reference = relative.copy()
            maximum = max(maximum, matrix_delta(reference, relative))
        attachment_drift[key] = maximum

    report.update({
        "native_action": prod_action.name,
        "maximum_local_joint_transform_delta_A_vs_B": local_delta,
        "local_joint_transform_equivalent": local_delta <= 1e-6,
        "attachment_carrier_relative_max_delta_over_phases": attachment_drift,
        "centering_object": "Rome2AoE2_LocomotionCenter",
        "facet_root": "Rome2AoE2_FacetRoot",
        "camera": {"view": "fixed side", "location": [6.0, -0.66, 1.0],
                   "target": [0.0, -0.66, 1.0], "orthographic_scale": 2.75},
    })
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
