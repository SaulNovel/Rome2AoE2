"""Headless, profile-driven AoE2 DE infantry render calibration."""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aoe2_render_profile import (camera_location, deterministic_json, direction_angles,
                                 load_profile, output_filename, sample_blender_frame,
                                 stable_canvas)


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--animation", required=True)
    parser.add_argument("--source-sample", type=int, default=0)
    parser.add_argument("--source-sample-rate", type=float, default=15.0)
    parser.add_argument("--scene-fps", type=int, default=60)
    parser.add_argument("--timeline-start", type=float, default=1.0)
    parser.add_argument("--direction", default="0", help="direction index or 'all'")
    parser.add_argument("--camera-azimuth", type=float)
    parser.add_argument("--camera-elevation", type=float)
    parser.add_argument("--orthographic-scale", type=float)
    parser.add_argument("--render-engine", choices=("CYCLES", "BLENDER_EEVEE"))
    parser.add_argument("--skip-shadow", action="store_true")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def point_camera(camera, target):
    camera.rotation_euler = (Vector(target) - camera.location).to_track_quat("-Z", "Y").to_euler()


def make_camera(profile, azimuth):
    data = bpy.data.cameras.new("AoE2CalibrationCamera")
    data.type = "ORTHO"
    data.ortho_scale = profile["camera"]["orthographic_scale"]
    camera = bpy.data.objects.new("AoE2CalibrationCamera", data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = camera_location(azimuth, profile["camera"]["elevation_degrees"],
                                      profile["camera"]["distance"], profile["target"]["origin"])
    point_camera(camera, profile["target"]["origin"])
    return camera


def make_lighting(profile):
    lighting = profile["lighting"]
    sun_data = bpy.data.lights.new("AoE2CalibrationKey", "SUN")
    sun_data.energy = lighting["key_strength"]
    sun_data.angle = math.radians(lighting["key_angular_size_degrees"])
    sun = bpy.data.objects.new("AoE2CalibrationKey", sun_data)
    bpy.context.scene.collection.objects.link(sun)
    point = camera_location(lighting["key_azimuth_degrees"], lighting["key_elevation_degrees"], 10.0)
    sun.rotation_euler = (Vector((0, 0, 0)) - Vector(point)).to_track_quat("-Z", "Y").to_euler()
    if bpy.context.scene.world is None:
        bpy.context.scene.world = bpy.data.worlds.new("AoE2CalibrationWorld")
    bpy.context.scene.world.color = (lighting["ambient_strength"],) * 3


def make_shadow_catcher(profile):
    bpy.ops.mesh.primitive_plane_add(size=20.0, location=profile["target"]["origin"])
    plane = bpy.context.object
    plane.name = "AoE2CalibrationShadowCatcher"
    plane.is_shadow_catcher = True
    return plane


def configure_scene(profile, args):
    scene = bpy.context.scene
    render = profile["render"]
    scene.render.engine = render["engine"]
    scene.render.resolution_x = render["width"]
    scene.render.resolution_y = render["height"]
    scene.render.resolution_percentage = render["resolution_percentage"]
    scene.render.film_transparent = render["film_transparent"]
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    if render["engine"] == "CYCLES":
        scene.cycles.samples = render["anti_aliasing_samples"]
        scene.cycles.use_denoising = False
    scene.view_settings.view_transform = render["view_transform"]
    scene.view_settings.look = render["look"]
    scene.view_settings.exposure = render["exposure"]
    scene.view_settings.gamma = render["gamma"]
    scene.render.fps = args.scene_fps
    frame = sample_blender_frame(args.source_sample, args.source_sample_rate,
                                 args.scene_fps, args.timeline_start)
    scene.frame_set(round(frame))
    return frame


def rendered_bounds(path, threshold=1.0 / 255.0):
    image = bpy.data.images.load(str(path.resolve()), check_existing=False)
    width, height = image.size
    pixels = list(image.pixels)
    points = []
    for index in range(width * height):
        if pixels[index * 4 + 3] > threshold:
            points.append((index % width, height - 1 - index // width))
    if not points:
        bpy.data.images.remove(image)
        return None
    xs, ys = zip(*points)
    result = [min(xs), min(ys), max(xs) + 1, max(ys) + 1]
    bpy.data.images.remove(image)
    return result


def project(scene, camera, point, width, height):
    from bpy_extras.object_utils import world_to_camera_view
    coordinate = world_to_camera_view(scene, camera, Vector(point))
    return [coordinate.x * width, (1.0 - coordinate.y) * height]


def main():
    args = arguments()
    profile = load_profile(args.profile)
    if args.camera_azimuth is not None:
        profile["camera"]["azimuth_degrees"] = args.camera_azimuth
    if args.camera_elevation is not None:
        profile["camera"]["elevation_degrees"] = args.camera_elevation
    if args.orthographic_scale is not None:
        profile["camera"]["orthographic_scale"] = args.orthographic_scale
    if args.render_engine is not None:
        profile["render"]["engine"] = args.render_engine
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    source_frame = configure_scene(profile, args)
    make_lighting(profile)
    shadow = None if args.skip_shadow else make_shadow_catcher(profile)
    angles = direction_angles(profile)
    indices = range(len(angles)) if args.direction == "all" else [int(args.direction)]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    reports = []
    for index in indices:
        if index < 0 or index >= len(angles):
            raise RuntimeError(f"direction index {index} is out of range")
        camera = make_camera(profile, angles[index])
        bpy.context.scene.camera = camera
        output = args.output_dir / output_filename(args.animation, args.source_sample, index)
        if shadow is not None:
            shadow.hide_render = True
        bpy.context.scene.render.filepath = str(output.resolve())
        bpy.ops.render.render(write_still=True)
        bounds = rendered_bounds(output)
        shadow_output = None
        shadow_bounds = None
        if shadow is not None:
            shadow.hide_render = False
            camera_visibility = {}
            for obj in bpy.context.scene.objects:
                if obj.type == "MESH" and obj != shadow:
                    camera_visibility[obj.name] = obj.visible_camera
                    obj.visible_camera = False
            shadow_output = args.output_dir / output_filename(args.animation, args.source_sample, index, "shadow")
            bpy.context.scene.render.filepath = str(shadow_output.resolve())
            bpy.ops.render.render(write_still=True)
            shadow_bounds = rendered_bounds(shadow_output, threshold=0.02)
            for name, visible in camera_visibility.items():
                bpy.data.objects[name].visible_camera = visible
        width, height = profile["render"]["width"], profile["render"]["height"]
        feet = project(bpy.context.scene, camera, profile["target"]["origin"], width, height)
        reports.append({
            "direction_index": index,
            "direction_name": profile["directions"]["order"][index],
            "azimuth_degrees": angles[index],
            "camera_matrix": [[float(v) for v in row] for row in camera.matrix_world],
            "feet_pixels": feet,
            "visible_pixel_bounds": bounds,
            "unit_pixel_height": None if bounds is None else bounds[3] - bounds[1],
            "output": output.name,
            "shadow_output": None if shadow_output is None else shadow_output.name,
            "shadow_bounds": shadow_bounds,
        })
        bpy.data.objects.remove(camera, do_unlink=True)
    document = {
        "format": "rome2aoe2.render-calibration",
        "version": 1,
        "profile": profile["name"],
        "blender_version": bpy.app.version_string,
        "animation": Path(args.animation).name,
        "source_sample": args.source_sample,
        "source_sample_rate": args.source_sample_rate,
        "scene_fps": args.scene_fps,
        "blender_frame": source_frame,
        "canvas": stable_canvas(profile),
        "camera": profile["camera"],
        "lighting": profile["lighting"],
        "render": profile["render"],
        "shadow_pass": "disabled" if shadow is None else "separate",
        "directions": reports,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(deterministic_json(document), encoding="utf-8")


if __name__ == "__main__":
    main()
