"""Render side-view, body-only native and production walk controls."""

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PHASES = tuple(index / 8 for index in range(8))
FOOT_BONES = ("bn_leftfoot", "bn_rightfoot", "bn_lefttoebase", "bn_righttoebase")


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-root", type=Path, required=True)
    parser.add_argument("--production-raw", type=Path, required=True)
    parser.add_argument("--production-centered", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def configure_scene(output):
    scene = bpy.context.scene
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    bpy.ops.object.camera_add(location=(6.0, -1.5, 0.9))
    camera = bpy.context.object
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 4.0
    camera.rotation_euler = (Vector((0.0, -1.5, 0.9)) - camera.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = camera
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "SINGLE"
    scene.display.shading.single_color = (0.62, 0.28, 0.17)
    scene.display.shading.show_shadows = True
    scene.display.shading.show_cavity = True
    scene.display.shading.show_specular_highlight = False
    scene.render.resolution_x = 600
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Walk control world")
    scene.world.color = (0.025, 0.025, 0.025)
    output.mkdir(parents=True, exist_ok=True)
    return scene


def armature_and_action():
    arms = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if len(arms) != 1:
        raise RuntimeError(f"expected one armature, found {len(arms)}")
    action = arms[0].animation_data.action
    if action is None:
        raise RuntimeError("animated scene has no active Action")
    return arms[0], action


def body_only(native):
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    if native:
        keep = meshes
    else:
        keep = [obj for obj in meshes if obj.name.startswith("skin__") and "Icosphere" not in obj.name]
    for obj in meshes:
        obj.hide_render = obj not in keep
        obj.hide_viewport = obj not in keep
    return keep


def matrix_rows(matrix):
    return [[float(matrix[row][column]) for column in range(4)] for row in range(4)]


def render_scene(source, output, label, native, save_imported=None, imported_body=False):
    if native:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=str(source.resolve()))
    else:
        bpy.ops.wm.open_mainfile(filepath=str(source.resolve()))
    if save_imported is not None:
        bpy.ops.wm.save_as_mainfile(filepath=str(save_imported.resolve()))
    scene = configure_scene(output)
    body_only(native or imported_body)
    armature, action = armature_and_action()
    start, end = action.frame_range
    frames = [start + phase * (end - start) for phase in PHASES]
    records = []
    for index, (phase, frame) in enumerate(zip(PHASES, frames)):
        whole = int(round(frame))
        scene.frame_set(whole, subframe=frame - whole)
        bpy.context.view_layer.update()
        pose = {}
        for name in ("bn_hips", *FOOT_BONES):
            bone = armature.pose.bones.get(name)
            if bone is not None:
                world = armature.matrix_world @ bone.matrix
                pose[name] = {"world_translation": list(world.translation), "world_matrix": matrix_rows(world)}
        path = output / f"{label}-phase-{index:02d}.png"
        scene.render.filepath = str(path.resolve())
        bpy.ops.render.render(write_still=True)
        records.append({"phase": phase, "frame": frame, "image": str(path), "pose": pose})
    return {"source": str(source), "action": action.name, "fps": scene.render.fps,
            "frame_range": list(action.frame_range), "records": records}


def main():
    args = arguments()
    report = {"format": "rome2aoe2.native-walk-controls", "version": 1,
              "phases": list(PHASES), "camera": {"view": "side", "orthographic_scale": 4.0,
              "location": [6.0, -1.5, 0.9], "target": [0.0, -1.5, 0.9]}, "stages": {}}
    for speed in (124, 162, 197, 251, 302):
        key = f"native_{speed}"
        report["stages"][key] = render_scene(
            args.native_root / f"sws_walk_{speed}_cm.gltf",
            args.output_root / key, key, True,
            save_imported=(args.output_root / "sws_walk_162_cm.raw-import.blend"
                           if speed == 162 else None))
    report["stages"]["raw_blender_reopen_162"] = render_scene(
        args.output_root / "sws_walk_162_cm.raw-import.blend",
        args.output_root / "raw_blender_reopen_162", "raw-blender-reopen-162",
        False, imported_body=True)
    report["stages"]["production_unmodified_root"] = render_scene(
        args.production_raw, args.output_root / "production_unmodified_root",
        "production-unmodified-root", False)
    report["stages"]["production_root_removed"] = render_scene(
        args.production_centered, args.output_root / "production_root_removed",
        "production-root-removed", False)
    path = args.output_root / "native-walk-controls.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
