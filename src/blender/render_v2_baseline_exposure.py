"""Baseline render: recovered materials + real v2 profile settings (exposure +0.65).

Used as the 'current baseline under actual v2 profile' comparison in the v4
contact sheet. The recovered production materials are already in the blend;
only camera/lighting/exposure from aoe2_de_infantry_v2.json are applied.
"""

import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "local-integration" / "rome2" / "visual-fidelity" / "v4"
BLEND_IN = ROOT / "build" / "local-integration" / "rome2" / "textured" / "sws_stand_textured.blend"
PROFILE = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v2.json"


def run():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    cam_s = profile["camera"]
    light_s = profile["lighting"]
    render_s = profile["render"]

    bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
    scene = bpy.context.scene
    scene.frame_set(0)

    # Camera
    cam = next((o for o in scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        cam = bpy.data.objects.new("bl_cam", bpy.data.cameras.new("bl_cam"))
        scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = cam_s["orthographic_scale"]
    az = math.radians(cam_s["azimuth_degrees"])
    el = math.radians(cam_s["elevation_degrees"])
    target = Vector((0.0, 0.0, 0.0))
    cam.location = target + Vector((cam_s["distance"] * math.cos(el) * math.cos(az),
                                    cam_s["distance"] * math.cos(el) * math.sin(az),
                                    cam_s["distance"] * math.sin(el)))
    cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

    # Lights: replace with v2 sun.
    for o in list(scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    data = bpy.data.lights.new("bl_key", "SUN")
    obj = bpy.data.objects.new("bl_key", data)
    scene.collection.objects.link(obj)
    az = math.radians(light_s["key_azimuth_degrees"])
    el = math.radians(light_s["key_elevation_degrees"])
    obj.location = (10.0 * math.cos(el) * math.cos(az), 10.0 * math.cos(el) * math.sin(az), 10.0 * math.sin(el))
    obj.rotation_euler = (Vector((0.0, 0.0, 1.0)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    data.energy = light_s["key_strength"]
    data.angle = math.radians(light_s["key_angular_size_degrees"])

    # World: uniform grey per v2 ambient.
    if scene.world is None:
        scene.world = bpy.data.worlds.new("bl_grey")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg is None:
        bg = scene.world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (0.35, 0.35, 0.35, 1.0)
    bg.inputs["Strength"].default_value = light_s["ambient_strength"]

    # Render settings from real v2 profile (exposure 0.65).
    scene.render.engine = render_s["engine"]
    scene.cycles.samples = render_s["anti_aliasing_samples"]
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = render_s["exposure"]
    scene.view_settings.gamma = 1.0

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "baseline_v2.png"
    scene.render.filepath = str(path.resolve())
    bpy.ops.render.render(write_still=True)
    print(f"rendered baseline: {path}")


if __name__ == "__main__":
    run()