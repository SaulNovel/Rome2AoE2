"""Render every frame of the accepted Hastati stand action on a stable AoE2 canvas.

This is deliberately a render-only stage: it opens the assembled scene and never
changes rig, animation, attachment, mesh, or material transforms.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
from aoe2_render_profile import direction_angles
from downsample_rgba import downsample_rgba


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--directions", default="all", help="all or comma-separated indices")
    parser.add_argument("--engine", choices=("BLENDER_EEVEE", "CYCLES"), default="BLENDER_EEVEE")
    parser.add_argument("--internal-scale", type=int, choices=(1, 2, 4))
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def point_at(obj, target):
    obj.rotation_euler = (Vector(target) - obj.location).to_track_quat("-Z", "Y").to_euler()


def configure_camera(scene, profile, azimuth):
    data = bpy.data.cameras.new("AoE2AnimatedCamera")
    data.type = "ORTHO"
    data.ortho_scale = profile["camera"]["orthographic_scale"]
    camera = bpy.data.objects.new("AoE2AnimatedCamera", data)
    scene.collection.objects.link(camera)
    target = Vector(profile["target"]["origin"])
    distance = profile["camera"]["distance"]
    elevation = math.radians(profile["camera"]["elevation_degrees"])
    azimuth = math.radians(azimuth)
    camera.location = target + Vector((
        distance * math.cos(elevation) * math.cos(azimuth),
        distance * math.cos(elevation) * math.sin(azimuth),
        distance * math.sin(elevation),
    ))
    point_at(camera, target)
    scene.camera = camera
    return camera


def configure_lighting(scene, profile):
    for obj in list(scene.objects):
        if obj.type in {"LIGHT", "CAMERA"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    light = profile["lighting"]
    data = bpy.data.lights.new("AoE2AnimatedKey", "SUN")
    data.energy = light["key_strength"]
    data.angle = math.radians(light["key_angular_size_degrees"])
    sun = bpy.data.objects.new("AoE2AnimatedKey", data)
    scene.collection.objects.link(sun)
    azimuth = math.radians(light["key_azimuth_degrees"])
    elevation = math.radians(light["key_elevation_degrees"])
    sun.location = Vector((math.cos(elevation) * math.cos(azimuth),
                           math.cos(elevation) * math.sin(azimuth), math.sin(elevation))) * 10
    point_at(sun, (0, 0, 0))
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (1, 1, 1, 1)
    background.inputs["Strength"].default_value = light["ambient_strength"]


def save_reduced(source, destination, width, height):
    image = bpy.data.images.load(str(source.resolve()), check_existing=False)
    pixels = list(image.pixels)
    reduced = downsample_rgba(pixels, image.size[0], image.size[1], width, height, "bicubic")
    out = bpy.data.images.new("AoE2AnimatedReduced", width, height, alpha=True)
    out.alpha_mode = "STRAIGHT"
    out.pixels.foreach_set(reduced)
    out.file_format = "PNG"
    out.filepath_raw = str(destination.resolve())
    out.save()
    bpy.data.images.remove(out)
    bpy.data.images.remove(image)


def alpha_bounds(path):
    image = bpy.data.images.load(str(path.resolve()), check_existing=False)
    width, height = image.size
    alpha = list(image.pixels)[3::4]
    points = [(i % width, height - 1 - i // width) for i, value in enumerate(alpha) if value > 1 / 255]
    bpy.data.images.remove(image)
    if not points:
        return None
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def main():
    args = arguments()
    profile = json.loads(args.profile.read_text(encoding="utf-8-sig"))
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    scene = bpy.context.scene
    armature = next(obj for obj in scene.objects if obj.type == "ARMATURE")
    action = armature.animation_data.action
    frames = list(range(int(action.frame_range[0]), int(round(action.frame_range[1])) + 1))
    angles = direction_angles(profile)
    indices = list(range(len(angles))) if args.directions == "all" else [int(v) for v in args.directions.split(",")]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    configure_lighting(scene, profile)
    render = profile["render"]
    scale = args.internal_scale or render.get("internal_render_scale", 4)
    width, height = render["width"], render["height"]
    scene.render.engine = args.engine
    scene.render.resolution_x, scene.render.resolution_y = width * scale, height * scale
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.render.image_settings.compression = 15
    scene.view_settings.view_transform = render["view_transform"]
    scene.view_settings.look = render["look"]
    scene.view_settings.exposure = render["exposure"]
    scene.view_settings.gamma = render["gamma"]
    if args.engine == "CYCLES":
        scene.cycles.samples = render["anti_aliasing_samples"]
        scene.cycles.use_denoising = False
    records = []
    for direction in indices:
        camera = configure_camera(scene, profile, angles[direction])
        for ordinal, frame in enumerate(frames):
            scene.frame_set(frame)
            stem = f"idle-direction-{direction:02d}-frame-{ordinal:03d}"
            high = args.output_dir / f"{stem}-{scale}x.png"
            final = args.output_dir / f"{stem}.png"
            if not final.is_file():
                scene.render.filepath = str(high.resolve())
                bpy.ops.render.render(write_still=True)
                save_reduced(high, final, width, height)
                high.unlink()
            bounds = alpha_bounds(final)
            if bounds is None:
                raise RuntimeError(f"empty render: direction {direction}, frame {frame}")
            records.append({"direction": direction, "azimuth_degrees": angles[direction],
                            "output_frame": ordinal, "blender_frame": frame,
                            "bounds": bounds, "path": final.name})
            print(json.dumps({"direction": direction, "frame": ordinal, "bounds": bounds}))
        bpy.data.objects.remove(camera, do_unlink=True)
    document = {
        "format": "rome2aoe2.animated-sprite-render", "version": 1,
        "source_blend": str(args.input_blend), "action": action.name,
        "action_frame_range": list(action.frame_range), "scene_fps": scene.render.fps,
        "output_frames_per_direction": len(frames), "directions": indices,
        "direction_angles": [angles[index] for index in indices],
        "canvas": [width, height], "hotspot": profile["canvas"]["anchor_pixels"],
        "engine": args.engine, "records": records,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
