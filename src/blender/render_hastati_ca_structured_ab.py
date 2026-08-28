"""Render one fixed high-resolution P5-vs-CA-structured material A/B."""
import json, sys
from pathlib import Path
import bpy

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
import render_cross_unit_set_a as cu
import render_hastati_stock_punch as punch
import render_hastati_aoe_art_direction as ad
import render_material_reconstruction_v1 as r1

BASE = ROOT / "build/local-integration/rome2/hastati-ca-structured-ab"
MASTERS = BASE / "masters"
MASKS = BASE / "masks"
EFFECTIVE = ROOT / "build/local-integration/rome2/runtime-resolution/effective/hastati/effective-unit.json"
BRONZE = ad.BRONZE
CLOTH = ad.CLOTH
FACET03_AZIMUTH = 112.5


def adjusted_faction_colour(colour):
    """CA ca_shader.fx get_adjusted_faction_colour, applied after linearization."""
    lum = max(0.0, min(1.0, colour[0] * .299 + colour[1] * .587 + colour[2] * .114))
    scale = 1.5 + (.5 - 1.5) * lum
    return tuple(channel * scale for channel in colour)


def image(nodes, path, label, noncolour=False):
    node = nodes.new("ShaderNodeTexImage")
    node.label = label
    node.image = bpy.data.images.load(str(path), check_existing=True)
    if noncolour:
        node.image.colorspace_settings.name = "Non-Color"
    return node


def rebuild_bronze(root):
    maps = r1.maps(root)
    for mat in bpy.data.materials:
        key = mat.name.split('.')[0]
        if key not in BRONZE or key not in maps:
            continue
        tex = maps[key]
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        out = nodes.new("ShaderNodeOutputMaterial")
        add = nodes.new("ShaderNodeAddShader")
        diffuse = nodes.new("ShaderNodeBsdfDiffuse")
        # Blender 5 names the former Glossy BSDF Anisotropic.
        glossy = nodes.new("ShaderNodeBsdfAnisotropic")
        glossy.label = "CA RGB specular lobe"
        links.new(diffuse.outputs[0], add.inputs[0])
        links.new(glossy.outputs[0], add.inputs[1])
        links.new(add.outputs[0], out.inputs["Surface"])

        di = image(nodes, tex["Diffuse"], "Authored bronze diffuse")
        sp = image(nodes, tex["Specular"], "CA RGB specular")
        gl = image(nodes, tex["GlossMap"], "Packed smoothness R / reflectivity G", True)
        split = nodes.new("ShaderNodeSeparateColor")
        links.new(gl.outputs["Color"], split.inputs["Color"])

        # CA keeps diffuse and RGB specular distinct. Gloss R controls lobe width;
        # packed G controls reflection amplitude independently.
        spec_amp = nodes.new("ShaderNodeMixRGB")
        spec_amp.blend_type = "MULTIPLY"
        spec_amp.inputs[0].default_value = 1.0
        links.new(sp.outputs["Color"], spec_amp.inputs[1])
        reflect_rgb = nodes.new("ShaderNodeCombineColor")
        for socket in ("Red", "Green", "Blue"):
            links.new(split.outputs["Green"], reflect_rgb.inputs[socket])
        links.new(reflect_rgb.outputs["Color"], spec_amp.inputs[2])

        rough = nodes.new("ShaderNodeMath")
        rough.operation = "SUBTRACT"
        rough.inputs[0].default_value = 1.0
        rough.use_clamp = True
        links.new(split.outputs["Red"], rough.inputs[1])
        links.new(di.outputs["Color"], diffuse.inputs["Color"])
        links.new(spec_amp.outputs["Color"], glossy.inputs["Color"])
        links.new(rough.outputs[0], diffuse.inputs["Roughness"])
        links.new(rough.outputs[0], glossy.inputs["Roughness"])

        if "Normal" in tex:
            no = image(nodes, tex["Normal"], "CA packed normal R*A, 1-G", True)
            normal = r1.packed_normal(nodes, links, no)
            links.new(normal, diffuse.inputs["Normal"])
            links.new(normal, glossy.inputs["Normal"])


def setup_scene(prototype):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root, _ = cu.import_unit("hastati")
    cu.configure_camera(bpy.context.scene, FACET03_AZIMUTH, 30, 8.5, 12)
    manifest = json.loads(EFFECTIVE.read_text())
    colours = tuple(ad.linear(manifest["faction_colours"][x]) for x in ("C0", "C1", "C2"))
    if prototype:
        colours = tuple(adjusted_faction_colour(c) for c in colours)
    r1.reconstruct(root, colours, True)
    # Match the preserved P5 material contribution on both sides. The
    # prototype then replaces only the bronze shader structure.
    punch.tune(punch.MATERIALS["B7"])
    if prototype:
        rebuild_bronze(root)
    # Fixed P5 A9 rig for both sides: this test changes shader structure, not lights.
    punch.rig(punch.LIGHTS["A9"])
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 3200
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "8"
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Khronos PBR Neutral" if prototype else "Standard"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = .65
    scene.view_settings.gamma = 1.0
    return root, scene


def render_master(name, prototype):
    root, scene = setup_scene(prototype)
    scene.render.filepath = str((MASTERS / f"{name}.png").resolve())
    bpy.ops.render.render(write_still=True)
    return root, scene


def render_mask(scene, name, selected):
    for mat in bpy.data.materials:
        key = mat.name.split('.')[0]
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        nodes.clear()
        out = nodes.new("ShaderNodeOutputMaterial")
        emission = nodes.new("ShaderNodeEmission")
        emission.inputs["Color"].default_value = (1, 1, 1, 1) if key in selected else (0, 0, 0, 1)
        emission.inputs["Strength"].default_value = 1
        links.new(emission.outputs[0], out.inputs["Surface"])
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.exposure = 0
    scene.render.filepath = str((MASKS / f"{name}.png").resolve())
    bpy.ops.render.render(write_still=True)


def main():
    MASTERS.mkdir(parents=True, exist_ok=True)
    MASKS.mkdir(parents=True, exist_ok=True)
    render_master("P5_CONTROL_F03", False)
    _, scene = render_master("CA_STRUCTURED_F03", True)
    render_mask(scene, "bronze_f03", BRONZE)
    _, scene = setup_scene(True)
    render_mask(scene, "cloth_f03", CLOTH)
    report = {
        "format": "rome2aoe2.hastati-ca-structured-ab", "version": 1,
        "fixed": {"composition": "runtime-resolved Hastati representative", "facet": 3,
                  "azimuth": FACET03_AZIMUTH, "camera": [FACET03_AZIMUTH, 30, 8.5, 12],
                  "pose_frame": 1, "resolution": 3200, "lighting": "P5 A9"},
        "control": {"material": "P5 B7", "view": "Standard", "exposure": .65},
        "prototype": {
            "bronze": "authored diffuse + RGB anisotropic specular",
            "smoothness": "GlossMap R; roughness=1-R",
            "reflectivity": "GlossMap G independently multiplies RGB specular",
            "faction": "official luminance-dependent adjusted faction colour",
            "view": "Khronos PBR Neutral", "exposure": .65,
        },
    }
    (BASE / "render-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
