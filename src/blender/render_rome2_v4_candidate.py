"""V4 material-fidelity candidate renders (bounded, non-destructive).

Chainmail A/B/C:
  A = dielectric approximation (recovered baseline)
  B = full conductor approximation
  C = mixed mask-blend (dielectric backing + conductor rings via mask R)

Environments (deterministic, fixed exposure +0.65, sun identical):
  1 = blue procedural sky (diagnostic F)
  2 = reduced-colour neutral sky
  3 = neutral upper sky + restrained warm ground bounce

No faction tint (authentic Rome II colour not extracted).
No global Metallic. No arbitrary saturation.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "build" / "local-integration" / "rome2" / "visual-fidelity" / "v4"
BLEND_IN = ROOT / "build" / "local-integration" / "rome2" / "textured" / "sws_stand_textured.blend"
PROFILE = ROOT / "config" / "render_profiles" / "aoe2_de_infantry_v4_material_fidelity_candidate.json"

EXPOSURE = 0.65  # real v2 value, fixed across all comparisons

# Explicit conductor candidates (model/material evidence from VMD + manifest).
CONDUCTORS = {
    "3c_niederbieber_helmet": "helmet metal (specular RGB strongly chromatic, delta 0.24)",
    "lorica_hamata_A": "chainmail rings (mixed mask-blend; not solid sheet)",
    "roman_gladius_lod1": "sword blade (specular near-grey, delta 0.042)",
    "roman_pilum_heavy_lod1": "pilum head (specular near-grey, delta 0.004)",
    "augustan_scutum_bossa_lod1": "shield boss/rim (specular near-grey, delta 0.005)",
}
# Dielectrics.
DIELECTRICS = {
    "augustan_scutum_lod1": "painted shield body",
    "celtic_basic_tunic_cut_01": "tunic",
    "roman_cloak_armour": "cloak",
    "3c_aurelian_pants": "trousers",
    "mhorsehair_01_lod1": "horsehair crest",
    "roman_1_head": "skin/head",
    "roman_body1": "skin/body",
    "roman_1_eyes_teeth": "eyes and teeth",
}


def harvest_images(mat):
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


def gloss_to_roughness(nodes, links, gloss, uv, bsdf):
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


def build_material(mat, chainmail_mode):
    """Build v4 candidate material. chainmail_mode: A/B/C."""
    images = harvest_images(mat)
    diffuse = images.get("diffuse")
    specular = images.get("specular")
    gloss = images.get("gloss")
    mask = images.get("mask")

    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    uv = nodes.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"

    name = mat.name
    is_chainmail = "lorica" in name.lower() or "hamata" in name.lower()
    is_conductor = name in CONDUCTORS and not is_chainmail

    if is_chainmail:
        # Chainmail: never a solid metal sheet.
        if chainmail_mode == "A":
            # Dielectric approximation (recovered baseline behaviour).
            bsdf.inputs["Metallic"].default_value = 0.0
            if diffuse:
                di = make_image_node(nodes, links, diffuse, uv, "diffuse")
                links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
            if specular:
                sp = make_image_node(nodes, links, specular, uv, "specular_rgb")
                lum = nodes.new("ShaderNodeRGBToBW")
                links.new(sp.outputs["Color"], lum.inputs["Color"])
                clamp = nodes.new("ShaderNodeClamp")
                clamp.inputs["Min"].default_value = 0.0
                clamp.inputs["Max"].default_value = 1.0
                links.new(lum.outputs["Val"], clamp.inputs["Value"])
                links.new(clamp.outputs["Result"], bsdf.inputs["Specular IOR Level"])
        elif chainmail_mode == "B":
            # Full conductor approximation (solid metal sheet).
            bsdf.inputs["Metallic"].default_value = 1.0
            if specular:
                sp = make_image_node(nodes, links, specular, uv, "specular_rgb_F0")
                links.new(sp.outputs["Color"], bsdf.inputs["Base Color"])
            elif diffuse:
                di = make_image_node(nodes, links, diffuse, uv, "diffuse_F0_fallback")
                links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
        else:
            # C: mixed mask-blend. Dielectric backing + conductor rings via mask R.
            bsdf.inputs["Metallic"].default_value = 0.0
            if diffuse:
                di = make_image_node(nodes, links, diffuse, uv, "diffuse")
                links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
            if specular:
                sp = make_image_node(nodes, links, specular, uv, "specular_rgb")
                lum = nodes.new("ShaderNodeRGBToBW")
                links.new(sp.outputs["Color"], lum.inputs["Color"])
                clamp = nodes.new("ShaderNodeClamp")
                clamp.inputs["Min"].default_value = 0.0
                clamp.inputs["Max"].default_value = 1.0
                links.new(lum.outputs["Val"], clamp.inputs["Value"])
                links.new(clamp.outputs["Result"], bsdf.inputs["Specular IOR Level"])
            # Mix metallic response by mask R (ring coverage).
            if mask:
                mk = make_image_node(nodes, links, mask, uv, "mask")
                sep = nodes.new("ShaderNodeSeparateColor")
                links.new(mk.outputs["Color"], sep.inputs["Color"])
                # metallic = mask_r (rings), base = lerp(diffuse, specular_F0, mask_r)
                metal = nodes.new("ShaderNodeMath")
                metal.operation = "MULTIPLY"
                metal.inputs[0].default_value = 1.0
                links.new(sep.outputs["Red"], metal.inputs[1])
                links.new(metal.outputs[0], bsdf.inputs["Metallic"])
                if specular:
                    sp2 = make_image_node(nodes, links, specular, uv, "specular_rgb_F0")
                    mix = nodes.new("ShaderNodeMixRGB")
                    mix.blend_type = "MIX"
                    links.new(sep.outputs["Red"], mix.inputs[0])
                    if diffuse:
                        links.new(di.outputs["Color"], mix.inputs[1])
                    links.new(sp2.outputs["Color"], mix.inputs[2])
                    links.new(mix.outputs["Color"], bsdf.inputs["Base Color"])
    elif is_conductor:
        bsdf.inputs["Metallic"].default_value = 1.0
        if specular:
            sp = make_image_node(nodes, links, specular, uv, "specular_rgb_F0")
            links.new(sp.outputs["Color"], bsdf.inputs["Base Color"])
        elif diffuse:
            di = make_image_node(nodes, links, diffuse, uv, "diffuse_F0_fallback")
            links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        # Dielectric.
        bsdf.inputs["Metallic"].default_value = 0.0
        if diffuse:
            di = make_image_node(nodes, links, diffuse, uv, "diffuse")
            links.new(di.outputs["Color"], bsdf.inputs["Base Color"])
        if specular:
            sp = make_image_node(nodes, links, specular, uv, "specular_rgb")
            lum = nodes.new("ShaderNodeRGBToBW")
            links.new(sp.outputs["Color"], lum.inputs["Color"])
            clamp = nodes.new("ShaderNodeClamp")
            clamp.inputs["Min"].default_value = 0.0
            clamp.inputs["Max"].default_value = 1.0
            links.new(lum.outputs["Val"], clamp.inputs["Value"])
            links.new(clamp.outputs["Result"], bsdf.inputs["Specular IOR Level"])

    if gloss:
        gloss_to_roughness(nodes, links, gloss, uv, bsdf)
    else:
        bsdf.inputs["Roughness"].default_value = 0.7


def set_environment(scene, env):
    """Deterministic procedural environments. Not Rome II / AoE2 setups."""
    if scene.world is None:
        scene.world = bpy.data.worlds.new("v4_world")
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

    if env == 2:
        # Reduced-colour neutral sky: desaturate the sky output.
        desat = nodes.new("ShaderNodeHueSaturation")
        desat.inputs["Saturation"].default_value = 0.15
        links.new(sky.outputs["Color"], desat.inputs["Color"])
        links.new(desat.outputs["Color"], bg.inputs["Color"])
    elif env == 3:
        # Neutral upper sky + restrained warm ground bounce.
        desat = nodes.new("ShaderNodeHueSaturation")
        desat.inputs["Saturation"].default_value = 0.15
        links.new(sky.outputs["Color"], desat.inputs["Color"])
        links.new(desat.outputs["Color"], bg.inputs["Color"])
        # Add warm ground hemisphere via a second background mixed by normal Z.
        bg2 = nodes.new("ShaderNodeBackground")
        bg2.inputs["Color"].default_value = (0.30, 0.22, 0.16, 1.0)  # restrained warm
        bg2.inputs["Strength"].default_value = 0.35
        mix = nodes.new("ShaderNodeMixShader")
        # Use a geometry normal to separate upper/lower hemisphere.
        geo = nodes.new("ShaderNodeNewGeometry")
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(geo.outputs["Normal"], sep.inputs["Vector"])
        # fac = 1 where normal Z > 0 (upper), 0 where Z < 0 (lower).
        math_node = nodes.new("ShaderNodeMath")
        math_node.operation = "GREATER_THAN"
        math_node.inputs[1].default_value = 0.0
        links.new(sep.outputs["Z"], math_node.inputs[0])
        links.new(bg.outputs["Background"], mix.inputs[1])
        links.new(bg2.outputs["Background"], mix.inputs[2])
        links.new(math_node.outputs[0], mix.inputs[0])
        links.new(mix.outputs["Shader"], out.inputs["Surface"])
        return scene.world

    links.new(bg.outputs["Background"], out.inputs["Surface"])
    return scene.world


def setup_sun(scene, profile):
    for o in list(scene.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    data = bpy.data.lights.new("v4_key", "SUN")
    obj = bpy.data.objects.new("v4_key", data)
    scene.collection.objects.link(obj)
    az = math.radians(profile["lighting"]["key_azimuth_degrees"])
    el = math.radians(profile["lighting"]["key_elevation_degrees"])
    obj.location = (10.0 * math.cos(el) * math.cos(az), 10.0 * math.cos(el) * math.sin(az), 10.0 * math.sin(el))
    obj.rotation_euler = (Vector((0.0, 0.0, 1.0)) - obj.location).to_track_quat("-Z", "Y").to_euler()
    data.energy = profile["lighting"]["key_strength"]
    data.angle = math.radians(profile["lighting"]["key_angular_size_degrees"])


def configure_camera(scene, azimuth=45.0, elevation=30.0, ortho_scale=8.5, distance=12.0):
    cam = next((o for o in scene.objects if o.type == "CAMERA"), None)
    if cam is None:
        cam = bpy.data.objects.new("v4_cam", bpy.data.cameras.new("v4_cam"))
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
    return out_path


def run():
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}

    # Chainmail A/B/C comparison (environment 3, fixed exposure).
    for mode in ("A", "B", "C"):
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
        scene = bpy.context.scene
        scene.frame_set(0)
        configure_camera(scene)
        set_environment(scene, 3)
        setup_sun(scene, profile)
        for mat in bpy.data.materials:
            if mat.use_nodes:
                build_material(mat, mode)
        path = OUT / f"chainmail_{mode}.png"
        render(scene, path)
        results[f"chainmail_{mode}"] = str(path)
        print(f"rendered chainmail_{mode}: {path}")

    # Environment 1/2/3 comparison with selected chainmail mode C.
    for env in (1, 2, 3):
        bpy.ops.wm.open_mainfile(filepath=str(BLEND_IN.resolve()))
        scene = bpy.context.scene
        scene.frame_set(0)
        configure_camera(scene)
        set_environment(scene, env)
        setup_sun(scene, profile)
        for mat in bpy.data.materials:
            if mat.use_nodes:
                build_material(mat, "C")
        path = OUT / f"env_{env}.png"
        render(scene, path)
        results[f"env_{env}"] = str(path)
        print(f"rendered env_{env}: {path}")

    report = {
        "format": "rome2aoe2.visual-fidelity.v4-candidate",
        "version": 1,
        "profile": str(PROFILE),
        "exposure": EXPOSURE,
        "chainmail_modes": {
            "A": "dielectric approximation",
            "B": "full conductor approximation",
            "C": "mixed mask-blend (dielectric backing + conductor rings via mask R)",
        },
        "environments": {
            "1": "blue procedural sky (diagnostic F)",
            "2": "reduced-colour neutral sky",
            "3": "neutral upper sky + restrained warm ground bounce",
        },
        "conductors": CONDUCTORS,
        "dielectrics": DIELECTRICS,
        "faction_tint": "none (authentic Rome II colour not extracted)",
        "renders": results,
    }
    (OUT / "v4-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    run()