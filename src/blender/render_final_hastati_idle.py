"""Render the final Hastati idle through the accepted Rome II runtime backend.

This deliberately imports the frozen local integration driver instead of
recreating its material, lighting, environment, or display equations.
"""

import argparse
import gc
import json
import math
import os
import sys
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "build/community_tool_investigation/asset-editor-runtime-integration"
sys.path.insert(0, str(INTEGRATION))
sys.path.insert(0, str(ROOT / "src/blender"))
sys.path.insert(0, str(ROOT / "src/rome2"))
import render_integration as accepted
import render_hastati_runtime_parity as runtime
from downsample_rgba import downsample_rgba

RAW = (
    "basis_normal", "basis_tangent", "basis_bitangent", "diffuse_raw",
    "specular_raw", "gloss_raw", "normal_sample", "normal_alpha", "mask_raw",
    "dirt_raw", "dirt_alpha", "dirt_mask_raw", "dirt_mask_alpha", "family",
)
DIRECTION_ANGLES = [45.0, 22.5, 0.0, 337.5, 315.0, 292.5, 270.0, 247.5,
                    225.0, 202.5, 180.0, 157.5, 135.0, 112.5, 90.0, 67.5]


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--directions", default="all")
    parser.add_argument("--frames", default="all")
    parser.add_argument("--master-size", type=int, default=800)
    parser.add_argument("--orthographic-scale", type=float,
                        help="Fixed absolute camera scale; defaults to the accepted span*1.20 framing")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def parse_selection(value, complete):
    if value == "all":
        return list(complete)
    return [int(item) for item in value.split(",")]


def set_camera(scene, center, span, azimuth_degrees, orthographic_scale=None):
    azimuth = math.radians(azimuth_degrees)
    elevation = math.radians(18.0)
    direction = Vector((math.cos(azimuth) * math.cos(elevation),
                        math.sin(azimuth) * math.cos(elevation), math.sin(elevation)))
    camera = scene.camera
    camera.location = center + direction * span * 3.0
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = orthographic_scale if orthographic_scale is not None else span * 1.20
    camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()


def reduce_image(source_path, destination, size):
    source = bpy.data.images.load(str(source_path.resolve()), check_existing=False)
    pixels = list(source.pixels)
    reduced = downsample_rgba(pixels, source.size[0], source.size[1], size, size, "bicubic")
    output = bpy.data.images.new(f"FinalHastati{size}", size, size, alpha=True)
    output.alpha_mode = "STRAIGHT"
    output.pixels.foreach_set(reduced)
    output.file_format = "PNG"
    output.filepath_raw = str(destination.resolve())
    output.save()
    bpy.data.images.remove(output)
    bpy.data.images.remove(source)


def alpha_bounds(path):
    image = bpy.data.images.load(str(path.resolve()), check_existing=False)
    width, height = image.size
    alpha = list(image.pixels)[3::4]
    points = [(index % width, height - 1 - index // width)
              for index, value in enumerate(alpha) if value > 1 / 255]
    bpy.data.images.remove(image)
    if not points:
        return None
    xs, ys = zip(*points)
    return [min(xs), min(ys), max(xs) + 1, max(ys) + 1]


def main():
    args = arguments()
    scene, armature, action, reference_frame, meshes = accepted.configure()
    records = accepted.material_records()
    for material in bpy.data.materials:
        if material.name.endswith("_Material") and material.name[:-9] in records:
            material.name = material.name[:-9]
    scene.frame_set(reference_frame)
    low, high = accepted.bounds(meshes)
    # Freeze one animation-wide target and scale.  XY remains the unit origin so
    # rotating the camera cannot introduce direction-dependent lateral framing.
    center = Vector((0.0, 0.0, (low.z + high.z) / 2.0))
    span = max(high - low)
    master = args.master_size
    scene.render.resolution_x = scene.render.resolution_y = master
    runtime.RESOLUTION = master
    runtime.OUT = args.output_dir / "master"
    # AOVs are disposable, but each background Blender worker must own its
    # directory so parallel direction batches cannot truncate one another.
    runtime.AOV = args.output_dir / "aov-working" / str(os.getpid())
    runtime.OUT.mkdir(parents=True, exist_ok=True)
    runtime.AOV.mkdir(parents=True, exist_ok=True)
    x1_dir = args.output_dir / "x1"
    x2_dir = args.output_dir / "x2"
    x1_dir.mkdir(parents=True, exist_ok=True)
    x2_dir.mkdir(parents=True, exist_ok=True)
    frame_start = int(action.frame_range[0])
    frame_end = int(round(action.frame_range[1]))
    frames = parse_selection(args.frames, range(frame_start, frame_end + 1))
    directions = parse_selection(args.directions, range(16))
    output = []
    hotspots = {}
    for direction_index in directions:
        angle = DIRECTION_ANGLES[direction_index]
        set_camera(scene, center, span, angle, args.orthographic_scale)
        projected = world_to_camera_view(scene, scene.camera, Vector((0, 0, 0)))
        master_hotspot = [round(projected.x * master), round((1.0 - projected.y) * master)]
        x1_hotspot = [int(math.floor(value * 200 / master + 0.5)) for value in master_hotspot]
        hotspots[str(direction_index)] = {
            "master": master_hotspot,
            "x1": x1_hotspot,
            "x2": [value * 2 for value in x1_hotspot],
        }
        for ordinal, frame in enumerate(frames):
            scene.frame_set(frame)
            stem = f"idle-direction-{direction_index:02d}-frame-{ordinal:03d}"
            master_path = runtime.OUT / f"{stem}.png"
            x1_path = x1_dir / f"{stem}.png"
            x2_path = x2_dir / f"{stem}.png"
            if not (x1_path.is_file() and x2_path.is_file()):
                arrays = {name: runtime.render_aov(scene, accepted.TEXROOT, name) for name in RAW}
                runtime.shade(scene, arrays, output_name=master_path.name, diagnostics=False)
                reduce_image(master_path, x2_path, 400)
                reduce_image(master_path, x1_path, 200)
                del arrays
                gc.collect()
                for temporary in runtime.AOV.glob("*"):
                    temporary.unlink()
            x1_bounds = alpha_bounds(x1_path)
            x2_bounds = alpha_bounds(x2_path)
            if x1_bounds is None or x2_bounds is None:
                raise RuntimeError(f"empty output {direction_index}/{frame}")
            output.append({
                "direction": direction_index, "azimuth_degrees": angle,
                "output_frame": ordinal, "blender_frame": frame,
                "x1": str(x1_path), "x2": str(x2_path),
                "x1_bounds": x1_bounds, "x2_bounds": x2_bounds,
            })
            print(json.dumps({"direction": direction_index, "frame": frame,
                              "progress": f"{len(output)}/{len(directions) * len(frames)}"}))
    document = {
        "format": "rome2aoe2.final-hastati-idle-render", "version": 1,
        "renderer": "accepted Raw AOV rasterization -> runtime_material_preparation -> frozen Rome II runtime lighting/display backend",
        "accepted_driver": str(INTEGRATION / "render_integration.py"),
        "source_blend": str(accepted.BLEND), "action": action.name,
        "action_frame_range": list(action.frame_range), "fps": scene.render.fps,
        "directions": directions, "direction_angles": [DIRECTION_ANGLES[i] for i in directions],
        "frames_per_direction": len(frames), "master_canvas": [master, master],
        "x1_canvas": [200, 200], "x2_canvas": [400, 400], "hotspots": hotspots,
        "camera": {"projection": "orthographic", "elevation_degrees": 18.0,
                   "orthographic_scale": args.orthographic_scale if args.orthographic_scale is not None else span * 1.20,
                   "scale_source": "explicit" if args.orthographic_scale is not None else "accepted span*1.20 default",
                   "target": list(center)},
        "downsampling": {"x1": f"{master}->200 direct premultiplied-alpha bicubic", "x2": f"{master}->400 direct premultiplied-alpha bicubic",
                         "x2_upscaled_from_x1": False},
        "records": output,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
