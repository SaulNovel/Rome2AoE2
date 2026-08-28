"""Phase 4 A/B/C diagnostic renders for Praetorian visual fidelity (non-destructive).

A: raw authored albedo (diffuse+decal) via Emission
B: A + evidence-backed faction tint via Emission (lerp(base, base*tint, mask))
C: existing production materials under v2 lighting

Same camera, same pose (frame 0), 800x800 transparent. Writes PNG under
build/local-integration/rome2/visual-fidelity/renders/.
"""

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "local-integration" / "rome2" / "visual-fidelity" / "renders"
TEX = ROOT / "build" / "local-integration" / "rome2" / "textures"

BLEND_IN = ROOT / "build" / "local-integration" / "rome2" / "textured" / "sws_stand_textured.blend"
PROFILE = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v2.json"

# Task-specified reference colours (task description, NOT DB-verified).
REF_TINTS = {
    "primary": (0.55, 0.06, 0.10),    # red/burgundy shields + tunic
    "secondary": (0.85, 0.55, 0.10),  # orange/gold shield decoration
    "cloth": (0.45, 0.20, 0.45),      # purple cloth
    "skin_warm": (0.75, 0.55, 0.42),  # warm skin
}

# Painted/tinted surfaces (faction tint expected to affect these).
PAINTED_KEYWORDS = ("shield", "tunic", "cloak", "crest", "horsehair", "pants", "leg")
# Metallic surfaces (tint NOT expected to explain darkness here).
METAL_KEYWORDS = ("helmet", "lorica", "hamata", "chainmail", "gladius", "sword", "pilum", "boss", "rim")


def socket(node, name):
    item = node.inputs.get(name)
    if item is None:
        raise RuntimeError(f"{node.bl_idname} lacks input {name}")
    return item


def set_emission_material(mat, tint=None, use_mask=False):
    """Rebuild a material as pure Emission (raw albedo), optionally tinted via mask."""
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    links.new(emit.outputs["Emission"], out.inputs["Surface"])

    # Find the diffuse image node by name pattern (set by apply_rome2_materials).
    diffuse = next((n for n in nodes if n.bl_idname == "ShaderNodeTexImage" and "diffuse" in n.label.lower()), None)
    # Re-add diffuse from the existing image if present in bpy.data.images.
    img = None
    for image in bpy.data.images:
        if "diffuse" in image.name.lower() and image.source == "FILE":
            img = image
            break
    if img is None:
        emit.inputs["Color"].default_value = (0.5, 0.5, 0.5, 1.0)
        return

    tex = nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.extension = "REPEAT"
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    links.new(uv.outputs["UV"], tex.inputs["Vector"])

    color = tex.outputs["Color"]
    if tint is not None:
        # lerp(base, base*tint, mask) == base * lerp(white, tint, mask)
        # Use mask R channel as the faction mask (R-dominant per Phase 3).
        mask_img = None
        for image in bpy.data.images:
            if "mask" in image.name.lower() and image.source == "FILE":
                mask_img = image
                break
        if use_mask and mask_img is not None:
            mask_tex = nodes.new("ShaderNodeTexImage")
            mask_tex.image = mask_img
            mask_tex.extension = "REPEAT"
            links.new(uv.outputs["UV"], mask_tex.inputs["Vector"])
            sep = nodes.new("ShaderNodeSeparateColor")
            links.new(mask_tex.outputs["Color"], sep.inputs["Color"])
            # lerp(white, tint, mask_r)
            mix = nodes.new("ShaderNodeMixRGB")
            mix.blend_type = "MIX"
            mix.inputs[0].default_value = 1.0  # fac from mask
            links.new(sep.outputs["Red"], mix.inputs[0])
            mix.inputs[1].default_value = (1.0, 1.0, 1.0, 1.0)
            mix.inputs[2].default_value = (*tint, 1.0)
            mult = nodes.new("ShaderNodeMixRGB")
            mult.blend_type = "MULTIPLY"
            links.new(color, mult.inputs[1])
            links.new(mix.outputs["Color"], mult.inputs[2])
            color = mult.outputs["Color"]
        else:
            # No mask: multiply whole surface by tint (diagnostic fallback).
            mult = nodes.new("ShaderNodeMixRGB")
            mult.blend_type = "MULTIPLY"
            links.new(color, mult.inputs[1])
            mult.inputs[2].default_value = (*tint, 1.0)
            color = mult.outputs["Color"]

    links.new(color, emit.inputs["Color"])
    emit.inputs["Strength"].default_value = 1.0


def configure_camera(scene, azimuth=45.0, elevation=30.0, ortho_scale=8.5, distance=12.0):
    cam = next((o for o in scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        cam = bpy.data.objects.new("diag_cam", bpy.data.cameras.new("diag_cam"))
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


def clear_lights(scene):
    for o in list(scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)


def set_world_color(scene, rgb, strength=1.0):
    if scene.world is None:
        scene.world = bpy.data.worlds.new("diag_world")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg is None:
        bg = scene.world.node_tree.nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bg.inputs["Strength"].default_value = strength


def render_mode(scene, mode, out_path):
    scene.render.engine = "BLENDER_EEVEE" if mode in ("A", "B") else "CYCLES"
    if mode == "C":
        scene.cycles.samples = 48
        scene.cycles.use_denoising = False
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.filepath = str(out_path.resolve())
    bpy.ops.render.render(write_still=True)
    return out_path


def classify_surface(material_name):
    low = material_name.lower()
    if any(k in low for k in METAL_KEYWORDS):
        return "metallic"
    if any(k in low for k in PAINTED_KEYWORDS):
        return "painted"
    return "other"


def run():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
    scene = bpy.context.scene
    OUT.mkdir(parents=True, exist_ok=True)

    # Frame 0 (stand sample 0).
    scene.frame_set(0)

    # Snapshot original material node trees so we can restore for C.
    original_materials = {}
    for mat in bpy.data.materials:
        if mat.use_nodes:
            original_materials[mat.name] = mat.node_tree

    # ---- Mode A: raw albedo via Emission, no lights, black world ----
    clear_lights(scene)
    set_world_color(scene, (0.0, 0.0, 0.0), 0.0)
    for mat in bpy.data.materials:
        if mat.use_nodes:
            set_emission_material(mat, tint=None)
    configure_camera(scene)
    path_a = OUT / "A_raw_albedo.png"
    render_mode(scene, "A", path_a)

    # ---- Mode B: A + faction tint via mask ----
    for mat in bpy.data.materials:
        if mat.use_nodes:
            cls = classify_surface(mat.name)
            if cls == "painted":
                set_emission_material(mat, tint=REF_TINTS["primary"], use_mask=True)
            elif cls == "metallic":
                set_emission_material(mat, tint=None)  # metal: no tint
            else:
                set_emission_material(mat, tint=None)
    path_b = OUT / "B_raw_albedo_tinted.png"
    render_mode(scene, "B", path_b)

    # ---- Mode C: re-open original blend (production materials intact), v2 lighting ----
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
    scene = bpy.context.scene
    scene.frame_set(0)
    # v2 lighting from profile.
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    clear_lights(scene)
    light_data = bpy.data.lights.new("diag_key", "SUN")
    light = bpy.data.objects.new("diag_key", light_data)
    scene.collection.objects.link(light)
    az = math.radians(profile["lighting"]["key_azimuth_degrees"])
    el = math.radians(profile["lighting"]["key_elevation_degrees"])
    light.location = (10.0 * math.cos(el) * math.cos(az), 10.0 * math.cos(el) * math.sin(az), 10.0 * math.sin(el))
    light.rotation_euler = (Vector((0.0, 0.0, 1.0)) - light.location).to_track_quat("-Z", "Y").to_euler()
    light_data.energy = profile["lighting"]["key_strength"]
    light_data.angle = math.radians(profile["lighting"]["key_angular_size_degrees"])
    set_world_color(scene, (0.35, 0.35, 0.35), profile["lighting"]["ambient_strength"])
    configure_camera(scene)
    path_c = OUT / "C_production_v2.png"
    render_mode(scene, "C", path_c)

    report = {
        "format": "rome2aoe2.visual-fidelity.phase4-renders",
        "version": 1,
        "input_blend": str(BLEND_IN),
        "frame": 0,
        "camera": {"azimuth_degrees": 45.0, "elevation_degrees": 30.0, "ortho_scale": 8.5},
        "canvas": [800, 800],
        "renders": {
            "A": str(path_a),
            "B": str(path_b),
            "C": str(path_c),
        },
        "surface_classification": {
            "painted": sorted(m.name for m in bpy.data.materials if classify_surface(m.name) == "painted"),
            "metallic": sorted(m.name for m in bpy.data.materials if classify_surface(m.name) == "metallic"),
        },
        "tint_notes": {
            "painted": "faction tint applied via lerp(base, base*primary, mask_r) using task-reference red/burgundy",
            "metallic": "no tint applied - metal darkness must be diagnosed separately (lighting/material)",
            "glossmap_caveat": "RGB differences in GlossMap may be packed scalar channels, not chromatic reflectance; not treated as visible color",
        },
    }
    (OUT / "phase4-renders.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()
