"""Bounded 2x2 material-vs-lighting diagnostic (C/D/E/F) for Praetorian metal.

C: recovered material + v2 sun/uniform-grey world
D: recovered material + neutral procedural outdoor environment
E: corrected specular/gloss material + v2 lighting
F: corrected specular/gloss material + neutral outdoor environment

Faction tint is identical across C/D/E/F (task-reference primary, NOT authentic).
Same pose (frame 0), camera, 800x800, Standard view transform, fixed exposure.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "local-integration" / "rome2" / "visual-fidelity" / "renders"
BLEND_IN = ROOT / "build" / "local-integration" / "rome2" / "textured" / "sws_stand_textured.blend"
PROFILE = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v2.json"

# Task-reference tint (NOT authentic Rome II value; kept identical across C/D/E/F).
TINT = (0.55, 0.06, 0.10)  # sRGB red/burgundy, task description only

# Per-surface metal treatment (NOT global Metallic).
METAL_SURFACES = ("lorica", "hamata", "helmet", "gladius", "sword", "pilum", "boss", "rim")


def harvest_images(mat):
    """Collect images already wired into this material's node tree.

    The recovered production script assigned each material its correct
    diffuse/specular/gloss/mask images; reuse them per-material so the
    corrected build does not cross-wire textures.
    """
    result = {}
    if not mat.node_tree:
        return result
    for node in mat.node_tree.nodes:
        if node.bl_idname != "ShaderNodeTexImage" or node.image is None:
            continue
        label = (node.label or node.name).lower()
        if "diffuse" in label:
            result.setdefault("diffuse", node.image)
        elif "specular" in label:
            result.setdefault("specular", node.image)
        elif "gloss" in label:
            result.setdefault("gloss", node.image)
        elif "mask" in label:
            result.setdefault("mask", node.image)
    return result


def make_image_node(nodes, links, image, uv, label):
    node = nodes.new("ShaderNodeTexImage")
    node.image = image
    node.label = label
    node.extension = "REPEAT"
    links.new(uv.outputs["UV"], node.inputs["Vector"])
    return node


def corrected_material(mat, corrected):
    """Build material for E/F (corrected) or reuse recovered baseline for C/D.

    corrected=True:
      - metals (chainmail/helmet/sword/boss): Metallic=1, BaseColor=specular RGB (conductor F0),
        Roughness from gloss red channel.
      - dielectrics (shield paint/cloth/skin): Metallic=0, BaseColor=diffuse,
        Specular IOR Level = mean(specular RGB).
    corrected=False leaves the recovered node tree untouched (C/D).

    No faction tint is applied (matches recovered production baseline), so tint
    is identical across C/D/E/F.
    """
    if not corrected:
        return
    # Harvest the material's own wired images BEFORE clearing the tree.
    images = harvest_images(mat)
    diffuse = images.get("diffuse")
    specular = images.get("specular")
    gloss = images.get("gloss")

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"

    is_metal = any(k in mat.name.lower() for k in METAL_SURFACES)

    if is_metal:
        # Conductor: Metallic=1, Base Color = specular RGB (F0 tint).
        bsdf.inputs["Metallic"].default_value = 1.0
        if specular:
            sp = make_image_node(nodes, links, specular, uv, "specular_rgb_F0")
            links.new(sp.outputs["Color"], bsdf.inputs["Base Color"])
        elif diffuse:
            di = make_image_node(nodes, links, diffuse, uv, "diffuse_F0_fallback")
            links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Metallic"].default_value = 0.0
        if diffuse:
            di = make_image_node(nodes, links, diffuse, uv, "diffuse")
            links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
        if specular:
            sp = make_image_node(nodes, links, specular, uv, "specular_rgb")
            # Specular IOR Level from mean of RGB channels (clamped 0..1).
            lum = nodes.new("ShaderNodeRGBToBW")
            links.new(sp.outputs["Color"], lum.inputs["Color"])
            clamp = nodes.new("ShaderNodeClamp")
            clamp.inputs["Min"].default_value = 0.0
            clamp.inputs["Max"].default_value = 1.0
            links.new(lum.outputs["Val"], clamp.inputs["Value"])
            links.new(clamp.outputs["Result"], bsdf.inputs["Specular IOR Level"])

    # Roughness from gloss red channel (packed scalar): roughness = 1 - gloss_red^2.
    if gloss:
        gl = make_image_node(nodes, links, gloss, uv, "gloss")
        sep = nodes.new("ShaderNodeSeparateColor")
        links.new(gl.outputs["Color"], sep.inputs["Color"])
        sq = nodes.new("ShaderNodeMath")
        sq.operation = "MULTIPLY"
        links.new(sep.outputs["Red"], sq.inputs[0])
        links.new(sep.outputs["Red"], sq.inputs[1])
        rough = nodes.new("ShaderNodeMath")
        rough.operation = "SUBTRACT"
        rough.inputs[0].default_value = 1.0
        links.new(sq.outputs[0], rough.inputs[1])
        links.new(rough.outputs[0], bsdf.inputs["Roughness"])
    else:
        bsdf.inputs["Roughness"].default_value = 0.7


def set_neutral_outdoor_world(scene):
    """Deterministic neutral procedural sky. Not a Rome II / AoE2 setup.

    Bright upper-sky hemisphere + weaker warm ground bounce; no visible
    background; fixed orientation (Z-up).
    """
    if scene.world is None:
        scene.world = bpy.data.worlds.new("cdef_sky")
    scene.world.use_nodes = True
    nt = scene.world.node_tree
    nodes = nt.nodes
    nodes.clear()
    links = nt.links
    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    sky = nodes.new("ShaderNodeTexSky")
    sky.sky_type = "PREETHAM"
    sky.sun_elevation = math.radians(60.0)
    sky.sun_rotation = math.radians(45.0)
    sky.air_density = 1.0
    links.new(sky.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 1.0
    links.new(bg.outputs["Background"], out.inputs["Surface"])
    return scene.world


def set_uniform_grey_world(scene, rgb, strength=1.0):
    if scene.world is None:
        scene.world = bpy.data.worlds.new("cdef_grey")
    scene.world.use_nodes = True
    nt = scene.world.node_tree
    nodes = nt.nodes
    bg = nodes.get("Background")
    if bg is None:
        bg = nodes.new("ShaderNodeBackground")
    bg.inputs["Color"].default_value = (*rgb, 1.0)
    bg.inputs["Strength"].default_value = strength


def setup_v2_sun(scene, profile):
    clear_lights(scene)
    data = bpy.data.lights.new("cdef_key", "SUN")
    obj = bpy.data.objects.new("cdef_key", data)
    scene.collection.objects.link(obj)
    az = math.radians(profile["lighting"]["key_azimuth_degrees"])
    el = math.radians(profile["lighting"]["key_elevation_degrees"])
    obj.location = (10.0 * math.cos(el) * math.cos(az), 10.0 * math.cos(el) * math.sin(az), 10.0 * math.sin(el))
    obj.rotation_euler = (Vector((0.0, 0.0, 1.0)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    data.energy = profile["lighting"]["key_strength"]
    data.angle = math.radians(profile["lighting"]["key_angular_size_degrees"])
    return obj


def clear_lights(scene):
    for o in list(scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)


def configure_camera(scene, azimuth=45.0, elevation=30.0, ortho_scale=8.5, distance=12.0):
    cam = next((o for o in scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        cam = bpy.data.objects.new("cdef_cam", bpy.data.cameras.new("cdef_cam"))
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
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    scene.render.filepath = str(out_path.resolve())
    bpy.ops.render.render(write_still=True)
    return out_path


def run():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    cases = [
        ("C", False, "v2"),
        ("D", False, "sky"),
        ("E", True, "v2"),
        ("F", True, "sky"),
    ]
    for label, corrected, lighting in cases:
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
        scene = bpy.context.scene
        scene.frame_set(0)
        configure_camera(scene)
        if lighting == "v2":
            set_uniform_grey_world(scene, (0.35, 0.35, 0.35), profile["lighting"]["ambient_strength"])
            setup_v2_sun(scene, profile)
        else:
            set_neutral_outdoor_world(scene)
            clear_lights(scene)
        for mat in bpy.data.materials:
            if mat.use_nodes:
                corrected_material(mat, corrected)
        path = OUT / f"{label}_render.png"
        render(scene, path)
        results[label] = str(path)
        print(f"rendered {label}: {path}")

    report = {
        "format": "rome2aoe2.visual-fidelity.cdef", "version": 1,
        "cases": results,
        "tint": {"rgb": list(TINT), "color_space": "sRGB",
                 "source": "task-reference red/burgundy, NOT authentic Rome II record",
                 "authentic": False},
        "notes": {
            "C": "recovered material + v2 sun/uniform-grey world",
            "D": "recovered material + neutral procedural outdoor sky",
            "E": "corrected specular/gloss material (metal F0, gloss-to-roughness) + v2 lighting",
            "F": "corrected specular/gloss material + neutral procedural outdoor sky",
            "tint_constant": "no faction tint applied in any case (matches recovered production baseline)",
        },
    }
    (OUT.parent / "cdef-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()
