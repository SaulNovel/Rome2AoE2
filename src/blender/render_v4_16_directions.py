"""Render the V4 candidate (env_3, chainmail C) in 16 directions.

Feet anchored at canvas center (400,400) in the 800x800 render so the
downsample keeps the feet point invariant at the SLD hotspot.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "local-integration" / "rome2" / "visual-fidelity" / "v4" / "directions"
BLEND_IN = ROOT / "build" / "local-integration" / "rome2" / "textured" / "sws_stand_textured.blend"
PROFILE = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v4_material_fidelity_candidate.json"
EXPOSURE = 0.65

# Reuse the v4 candidate material builder.
sys.path.insert(0, str(ROOT / "src" / "blender"))
from render_rome2_v4_candidate import build_material, set_environment, setup_sun  # noqa: E402


def configure_camera(scene, azimuth, elevation=30.0, ortho_scale=8.5, distance=12.0):
    cam = next((o for o in scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        cam = bpy.data.objects.new("v4d_cam", bpy.data.cameras.new("v4d_cam"))
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = ortho_scale
    az = math.radians(azimuth)
    el = math.radians(elevation)
    target = Vector((0.0, 0.0, 0.0))
    cam.location = target + Vector((distance * math.cos(el) * math.cos(az),
                                    distance * math.cos(el) * math.sin(az),
                                    distance * math.sin(el)))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()


def render(scene, out_path):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 48
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = EXPOSURE
    scene.view_settings.gamma = 1.0
    scene.render.filepath = str(out_path.resolve())
    bpy.ops.render.render(write_still=True)


def run():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    start = float(profile["camera"]["azimuth_degrees"])
    count = profile["directions"]["count"]
    sign = -1.0 if profile["directions"].get("clockwise", True) else 1.0
    angles = [((start + sign * i * 360.0 / count) % 360.0) for i in range(count)]

    bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
    scene = bpy.context.scene
    scene.frame_set(0)
    set_environment(scene, 3)
    setup_sun(scene, profile)
    for mat in bpy.data.materials:
        if mat.use_nodes:
            build_material(mat, "C")

    for i, az in enumerate(angles):
        configure_camera(scene, az)
        path = OUT / f"direction-{i:02d}.png"
        render(scene, path)
        print(f"rendered {path}")

    report = {"format": "rome2aoe2.visual-fidelity.v4-16dir", "version": 1,
              "exposure": EXPOSURE, "environment": 3, "chainmail": "C",
              "angles": angles, "outputs": [str(OUT / f"direction-{i:02d}.png") for i in range(count)]}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    run()