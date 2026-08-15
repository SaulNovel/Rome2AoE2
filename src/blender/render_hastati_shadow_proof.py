"""Render a separated fixed-studio cast-shadow proof for the Hastati."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
INTEGRATION = ROOT / "build/community_tool_investigation/asset-editor-runtime-integration"
sys.path.insert(0, str(INTEGRATION))
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "src/blender"))
sys.path.insert(0, str(ROOT / "src/rome2"))

import render_integration as accepted
import render_hastati_runtime_parity as runtime
from downsample_rgba import downsample_rgba
from render_final_hastati_idle import (
    DIRECTION_ANGLES, REFERENCE_CAMERA_AZIMUTH, create_unit_root,
    set_camera,
)
from aoe2.facet_mapping import soldier_yaw_degrees


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--frame", type=int, default=33)
    parser.add_argument("--master-size", type=int, default=800)
    parser.add_argument("--orthographic-scale", type=float, default=7.27480212108078)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def image_array(path: Path) -> np.ndarray:
    image = bpy.data.images.load(str(path), check_existing=False)
    values = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(values)
    result = values.reshape((image.size[1], image.size[0], 4))[::-1].copy()
    bpy.data.images.remove(image)
    return result


def save_rgba(path: Path, rgba: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    runtime.png_rgba(path, rgba.astype(np.float32))


def downsample(source: np.ndarray, size: int) -> np.ndarray:
    values = downsample_rgba(
        source.reshape(-1).tolist(), source.shape[1], source.shape[0],
        size, size, "bicubic",
    )
    return np.asarray(values, np.float32).reshape((size, size, 4))


def configure_shadow_scene(scene, meshes, master: int):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = True
    scene.render.resolution_x = scene.render.resolution_y = master
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Raw"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    world = bpy.data.worlds.new("Rome2AoE2_ShadowWorld") if scene.world is None else scene.world
    scene.world = world
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.35

    plane_material = bpy.data.materials.new("Rome2AoE2_ShadowReceiver")
    plane_material.diffuse_color = (1, 1, 1, 1)
    plane_material.use_nodes = True
    principled = plane_material.node_tree.nodes.get("Principled BSDF")
    principled.inputs["Base Color"].default_value = (1, 1, 1, 1)
    principled.inputs["Roughness"].default_value = 1.0
    bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, -0.01))
    plane = bpy.context.object
    plane.name = "Rome2AoE2_ShadowReceiver"
    plane.data.materials.append(plane_material)

    opaque = bpy.data.materials.new("Rome2AoE2_OpaqueShadowCaster")
    opaque.diffuse_color = (0.5, 0.5, 0.5, 1)
    for mesh in meshes:
        mesh.data.materials.clear()
        mesh.data.materials.append(opaque)
        mesh.visible_camera = False
        mesh.visible_shadow = True

    axis = np.array(((1, 0, 0), (0, 0, -1), (0, 1, 0)), np.float32)
    recovered_direction = axis @ (-runtime.SUN_DIRECTION_R2)
    recovered_direction /= np.linalg.norm(recovered_direction)
    horizontal = recovered_direction[:2] / np.linalg.norm(recovered_direction[:2])
    elevation = math.radians(60.0)
    light_direction = np.array((horizontal[0] * math.cos(elevation),
                                horizontal[1] * math.cos(elevation),
                                math.sin(elevation)), np.float32)
    light_data = bpy.data.lights.new("Rome2AoE2_FixedShadowKey", "AREA")
    light_data.energy = 900.0
    light_data.shape = "DISK"
    light_data.size = 3.0
    light = bpy.data.objects.new("Rome2AoE2_FixedShadowKey", light_data)
    light.location = Vector(light_direction.tolist()) * 12.0
    light.rotation_euler = (-light.location).to_track_quat("-Z", "Y").to_euler()
    scene.collection.objects.link(light)
    return plane, recovered_direction.tolist(), light_direction.tolist()


def main() -> int:
    args = arguments()
    if not args.output_root.is_absolute():
        args.output_root = (ROOT / args.output_root).resolve()
    args.output_root.mkdir(parents=True, exist_ok=True)
    scene, armature, _action, _reference_frame, meshes = accepted.configure()
    scene.frame_set(args.frame)
    low, high = accepted.bounds(meshes)
    center = Vector((0.0, 0.0, (low.z + high.z) / 2.0))
    span = max(high - low)
    root, rooted = create_unit_root(armature, meshes)
    set_camera(scene, center, span, REFERENCE_CAMERA_AZIMUTH, args.orthographic_scale)
    _plane, recovered_light_direction, light_direction = configure_shadow_scene(scene, meshes, args.master_size)
    scene.render.filepath = str(args.output_root / "raw.png")

    for mesh in meshes:
        mesh.visible_shadow = False
    bpy.ops.render.render(write_still=True)
    baseline = image_array(Path(scene.render.filepath))
    baseline_luminance = baseline[..., :3] @ np.array((0.2126, 0.7152, 0.0722), np.float32)
    for mesh in meshes:
        mesh.visible_shadow = True

    records = []
    for direction in range(16):
        yaw = soldier_yaw_degrees(direction)
        root.rotation_euler[2] = math.radians(yaw)
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        shaded = image_array(Path(scene.render.filepath))
        luminance = shaded[..., :3] @ np.array((0.2126, 0.7152, 0.0722), np.float32)
        relative = np.maximum(0, baseline_luminance - luminance) / np.maximum(baseline_luminance, 1e-5)
        alpha = np.clip(relative / 0.72, 0, 1) * 0.38
        alpha[alpha < 0.025] = 0
        rgba = np.zeros((*alpha.shape, 4), np.float32)
        rgba[..., 3] = alpha
        stem = f"idle-direction-{direction:02d}-frame-000.png"
        master_path = args.output_root / "master" / stem
        x1_path = args.output_root / "x1" / stem
        x2_path = args.output_root / "x2" / stem
        save_rgba(master_path, rgba)
        save_rgba(x2_path, downsample(rgba, 400))
        save_rgba(x1_path, downsample(rgba, 200))
        visible = np.argwhere(alpha >= 1 / 255)
        bounds = None if not len(visible) else [
            int(visible[:, 1].min()), int(visible[:, 0].min()),
            int(visible[:, 1].max()) + 1, int(visible[:, 0].max()) + 1,
        ]
        records.append({"facet": direction, "unit_yaw_degrees": yaw, "bounds_master": bounds,
                        "maximum_opacity": float(alpha.max())})
        print(json.dumps(records[-1]))
    report = {
        "format": "rome2aoe2.hastati-shadow-proof", "version": 1,
        "frame": args.frame, "facets": 16,
        "policy": "fixed camera/light/environment/ground; rotate complete unit root only",
        "camera": {"azimuth_degrees": REFERENCE_CAMERA_AZIMUTH, "elevation_degrees": 18.0,
                   "orthographic_scale": args.orthographic_scale,
                   "location": list(scene.camera.location), "target": list(center)},
        "unit_root": {"name": root.name, "pivot": [0, 0, 0], "top_level_members": rooted},
        "shadow": {"method": "separate physical receiver/caster pass",
                   "recovered_main_light_direction": recovered_light_direction,
                   "fixed_shadow_light_direction": light_direction,
                   "fixed_shadow_light_elevation_degrees": 60.0,
                   "shadow_light_azimuth_policy": "same fixed horizontal azimuth as recovered main sun",
                   "area_light_size": 3.0,
                   "maximum_authored_opacity": 0.38,
                   "main_colour_modified": False},
        "records": records,
    }
    args.output_root.mkdir(parents=True, exist_ok=True)
    (args.output_root / "shadow-render-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
