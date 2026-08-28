"""Apply deterministic Rome II spec/gloss materials from a texture manifest."""

import argparse
import json
import math
import sys
from pathlib import Path

try:
    import bpy
    from mathutils import Vector
except ImportError:  # Unit-testable manifest helpers do not require Blender.
    bpy = None
    Vector = None


FORMAT = "rome2aoe2.texture-manifest"
VERSION = 1
SUPPORTED_MATERIAL_TYPES = {
    "Weighted",
    "DefaultMaterial",
    "DecalDirtmap",
    "WeightedDirtmap",
    "WeightedSkinDirtmap",
}
DECAL_RECT = [0.052, 0.346, 0.468, 1.124]
ALPHA_THRESHOLD = 0.5


def deterministic_json(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def load_manifest(path):
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("format") != FORMAT or document.get("version") != VERSION:
        raise ValueError("unsupported texture manifest format/version")
    if not isinstance(document.get("materials"), list):
        raise ValueError("texture manifest requires materials")
    return document


def gloss_to_roughness(value):
    value = max(0.0, min(1.0, value))
    return 1.0 - value * value


def directx_normal(rgb):
    x = rgb[0] * 2.0 - 1.0
    y = (1.0 - rgb[1]) * 2.0 - 1.0
    z = math.sqrt(max(0.0, 1.0 - x * x - y * y))
    length = math.sqrt(x * x + y * y + z * z) or 1.0
    return [x / length, y / length, z / length]


def transform_decal_uv(uv, rect=DECAL_RECT):
    width, height = rect[2] - rect[0], rect[3] - rect[1]
    if abs(width) < 1.0e-12 or abs(height) < 1.0e-12:
        raise ValueError("invalid decal rectangle")
    return [(uv[0] - rect[0]) / width, (uv[1] - rect[1]) / height]


def material_index(document):
    result = {}
    for material in document["materials"]:
        name = material.get("material_name")
        if not name or name in result:
            raise ValueError(f"duplicate or empty material name: {name!r}")
        result[name] = material
    return result


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-blend", type=Path, required=True)
    parser.add_argument("--texture-manifest", type=Path, required=True)
    parser.add_argument("--texture-root", type=Path, required=True)
    parser.add_argument("--output-blend", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--render-profile", type=Path)
    parser.add_argument("--validation-frame", type=float, action="append", default=[])
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1 :])


def socket(node, name):
    item = node.inputs.get(name)
    if item is None:
        raise RuntimeError(f"Blender {bpy.app.version_string}: {node.bl_idname} lacks input {name}")
    return item


def texture_by_semantic(material):
    return {texture["semantic"]: texture for texture in material["textures"]}


def load_image(texture, root, material_name):
    if texture is None:
        return None
    if texture.get("status") != "resolved":
        return None
    path = root.joinpath(*texture["extracted_path"].split("/"))
    if not path.is_file():
        raise RuntimeError(f"{material_name}: extracted image is missing: {texture['extracted_path']}")
    image = bpy.data.images.load(str(path.resolve()), check_existing=True)
    image.name = f"rome2::{texture['resolved_path']}"
    image.colorspace_settings.name = texture["color_space"]
    return image


def image_node(nodes, texture, root, material_name, label):
    image = load_image(texture, root, material_name)
    if image is None:
        return None
    node = nodes.new("ShaderNodeTexImage")
    node.name = f"rome2_{label}"
    node.label = f"Rome II {label} ({texture['color_space']})"
    node.image = image
    node.extension = "REPEAT"
    return node


def uv_node(nodes):
    node = nodes.new("ShaderNodeUVMap")
    node.name = "rome2_uv0"
    node.label = "Rome II UV0"
    node.uv_map = "UVMap"
    return node


def alpha_default(texture):
    if texture and texture.get("status") == "shader_default":
        return float(texture.get("default_rgba", [0, 0, 0, 0])[3])
    return 1.0


def is_zero_contribution_sentinel(texture):
    """Recognise CA's engine-provided black placeholder by source identity.

    Some extracted caches contain a physical copy of ``test_black.dds``.  Its
    presence must not turn an absent dirt binding into full dirt coverage.
    """
    if not texture:
        return False
    source = texture.get("resolved_path") or texture.get("source_path") or ""
    return Path(source).name.casefold() == "test_black.dds"


def build_material(blender_material, spec, texture_root):
    material_type = spec["material_type"]
    if material_type not in SUPPORTED_MATERIAL_TYPES:
        raise RuntimeError(f"{blender_material.name}: unsupported selected material type {material_type}")
    blender_material.use_nodes = True
    nodes = blender_material.node_tree.nodes
    links = blender_material.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.name = "rome2_output"
    bsdf = nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.name = "rome2_principled"
    bsdf.label = "Rome II spec/gloss approximation"
    socket(bsdf, "Metallic").default_value = 0.0
    if bsdf.inputs.get("Subsurface Weight"):
        bsdf.inputs["Subsurface Weight"].default_value = 0.0
    links.new(bsdf.outputs["BSDF"], output.inputs["Surface"])
    uv = uv_node(nodes)
    textures = texture_by_semantic(spec)
    warnings = []

    diffuse = image_node(nodes, textures.get("Diffuse"), texture_root, blender_material.name, "diffuse")
    base_color_output = diffuse.outputs["Color"] if diffuse else None
    if diffuse:
        links.new(uv.outputs["UV"], diffuse.inputs["Vector"])

    specular = image_node(nodes, textures.get("Specular"), texture_root, blender_material.name, "specular_rgb")
    specular_output = specular.outputs["Color"] if specular else None
    if specular:
        links.new(uv.outputs["UV"], specular.inputs["Vector"])

    if "DecalDiffuse" in textures:
        decal = image_node(nodes, textures["DecalDiffuse"], texture_root, blender_material.name, "decal_diffuse")
        subtract = nodes.new("ShaderNodeVectorMath")
        subtract.operation = "SUBTRACT"
        subtract.inputs[1].default_value = (*DECAL_RECT[:2], 0.0)
        divide = nodes.new("ShaderNodeVectorMath")
        divide.operation = "DIVIDE"
        divide.inputs[1].default_value = (DECAL_RECT[2] - DECAL_RECT[0], DECAL_RECT[3] - DECAL_RECT[1], 1.0)
        links.new(uv.outputs["UV"], subtract.inputs[0])
        links.new(subtract.outputs["Vector"], divide.inputs[0])
        links.new(divide.outputs["Vector"], decal.inputs["Vector"])
        mask_value = alpha_default(textures.get("DecalMask"))
        blend = nodes.new("ShaderNodeMath")
        blend.operation = "MULTIPLY"
        blend.inputs[1].default_value = mask_value
        links.new(decal.outputs["Alpha"], blend.inputs[0])
        color_mix = nodes.new("ShaderNodeMixRGB")
        color_mix.blend_type = "MIX"
        links.new(blend.outputs[0], color_mix.inputs[0])
        if base_color_output:
            links.new(base_color_output, color_mix.inputs[1])
        links.new(decal.outputs["Color"], color_mix.inputs[2])
        base_color_output = color_mix.outputs["Color"]
        if specular_output:
            decal_half = nodes.new("ShaderNodeVectorMath")
            decal_half.operation = "SCALE"
            decal_half.inputs[3].default_value = 0.5
            links.new(decal.outputs["Color"], decal_half.inputs[0])
            spec_mix = nodes.new("ShaderNodeMixRGB")
            links.new(blend.outputs[0], spec_mix.inputs[0])
            links.new(specular_output, spec_mix.inputs[1])
            links.new(decal_half.outputs["Vector"], spec_mix.inputs[2])
            specular_output = spec_mix.outputs["Color"]
        warnings.append("selected decal normal is flat and was intentionally omitted")
        flat_decal_normal = image_node(nodes, textures.get("DecalNormal"), texture_root, blender_material.name, "decal_normal_flat_preserved")
        if flat_decal_normal:
            flat_decal_normal.label = "Flat selected decal normal (preserved, intentionally unconnected)"

    dirt = image_node(nodes, textures.get("DecalDirtmap"), texture_root, blender_material.name, "dirt_rg_alpha")
    dirt_mask = textures.get("DecalDirtmask")
    dirt_coverage_output = None
    if spec["shader_flags"].get("dirt") and dirt:
        scale_values = {int(pair[0]): float(pair[1]) for pair in spec["parameters"].get("float", [])}
        scale = (scale_values.get(0, 1.0), scale_values.get(1, 1.0), 1.0)
        multiply_uv = nodes.new("ShaderNodeVectorMath")
        multiply_uv.operation = "MULTIPLY"
        multiply_uv.inputs[1].default_value = scale
        links.new(uv.outputs["UV"], multiply_uv.inputs[0])
        links.new(multiply_uv.outputs["Vector"], dirt.inputs["Vector"])
        eligibility = alpha_default(dirt_mask)
        if is_zero_contribution_sentinel(dirt_mask):
            coverage = nodes.new("ShaderNodeValue")
            coverage.name = "rome2_zero_dirt_sentinel"
            coverage.outputs[0].default_value = 0.0
            coverage_output = coverage.outputs[0]
        elif dirt_mask and dirt_mask.get("status") == "resolved":
            mask_node = image_node(nodes, dirt_mask, texture_root, blender_material.name, "dirt_mask")
            links.new(uv.outputs["UV"], mask_node.inputs["Vector"])
            coverage = nodes.new("ShaderNodeMath")
            coverage.operation = "MULTIPLY"
            links.new(dirt.outputs["Alpha"], coverage.inputs[0])
            links.new(mask_node.outputs["Alpha"], coverage.inputs[1])
            coverage_output = coverage.outputs[0]
        else:
            coverage = nodes.new("ShaderNodeMath")
            coverage.operation = "MULTIPLY"
            coverage.inputs[1].default_value = eligibility
            links.new(dirt.outputs["Alpha"], coverage.inputs[0])
            coverage_output = coverage.outputs[0]
        dirt_coverage_output = coverage_output
        # Preserve the resolved dirt inputs, but do not approximate the
        # capture-replay dirt path in a Principled graph.  Rome's dirt result
        # depends on the captured tangent basis and per-instance controls;
        # applying only its near-black diffuse term caused false striping and
        # crushed values.  The exact runtime bridge consumes these nodes later.
        dirt_mix = nodes.new("ShaderNodeMixRGB")
        dirt_mix.name = "rome2_dirt_mix"
        dirt_mix.label = "Rome II dirt inputs preserved; exact runtime path required"
        dirt_mix.inputs[0].default_value = 0.0
        if base_color_output:
            links.new(base_color_output, dirt_mix.inputs[1])
        dirt_mix.inputs[2].default_value = (0.03, 0.025, 0.02, 1.0)
        base_color_output = dirt_mix.outputs["Color"]
        warnings.append("dirt inputs preserved; approximate dark blend disabled pending exact runtime-basis evaluation")

    if base_color_output:
        links.new(base_color_output, socket(bsdf, "Base Color"))

    if specular_output and bsdf.inputs.get("Specular IOR Level"):
        luminance = nodes.new("ShaderNodeRGBToBW")
        luminance.label = "Principled scalar approximation of Rome II RGB specular"
        links.new(specular_output, luminance.inputs["Color"])
        links.new(luminance.outputs["Val"], bsdf.inputs["Specular IOR Level"])

    gloss = image_node(nodes, textures.get("GlossMap"), texture_root, blender_material.name, "gloss")
    if gloss:
        links.new(uv.outputs["UV"], gloss.inputs["Vector"])
        separate = nodes.new("ShaderNodeSeparateColor")
        square = nodes.new("ShaderNodeMath")
        square.operation = "MULTIPLY"
        invert = nodes.new("ShaderNodeMath")
        invert.operation = "SUBTRACT"
        invert.inputs[0].default_value = 1.0
        links.new(gloss.outputs["Color"], separate.inputs["Color"])
        links.new(separate.outputs["Red"], square.inputs[0])
        links.new(separate.outputs["Red"], square.inputs[1])
        links.new(square.outputs[0], invert.inputs[1])
        links.new(invert.outputs[0], socket(bsdf, "Roughness"))

    normal = image_node(nodes, textures.get("Normal"), texture_root, blender_material.name, "normal_ag")
    if normal:
        normal_uv = uv
        normal_uv_name = "UVMap.001" if material_type == "WeightedSkinDirtmap" else "UVMap"
        if normal_uv_name != "UVMap":
            normal_uv = nodes.new("ShaderNodeUVMap")
            normal_uv.name = "rome2_skin_normal_uv1"
            normal_uv.label = "Rome II skin normal TEXCOORD_1"
            normal_uv.uv_map = normal_uv_name
        links.new(normal_uv.outputs["UV"], normal.inputs["Vector"])
        split = nodes.new("ShaderNodeSeparateColor")
        split.name = "rome2_normal_ag_channels"
        offset = 0.5 / 255.0
        x = nodes.new("ShaderNodeMath"); x.operation = "MULTIPLY_ADD"
        x.inputs[1].default_value = 2.0; x.inputs[2].default_value = 2.0 * offset - 1.0
        y = nodes.new("ShaderNodeMath"); y.operation = "MULTIPLY_ADD"
        # The exported glTF tangent sign already carries the Rome/Blender
        # handedness conversion.  Inverting G again mirrored the tangent Y
        # contribution and produced the characteristic striped skin failure.
        y.inputs[1].default_value = 2.0; y.inputs[2].default_value = 2.0 * offset - 1.0
        xx = nodes.new("ShaderNodeMath"); xx.operation = "MULTIPLY"
        yy = nodes.new("ShaderNodeMath"); yy.operation = "MULTIPLY"
        sum_xy = nodes.new("ShaderNodeMath"); sum_xy.operation = "ADD"
        remaining = nodes.new("ShaderNodeMath"); remaining.operation = "SUBTRACT"
        remaining.inputs[0].default_value = 1.0; remaining.use_clamp = True
        z = nodes.new("ShaderNodeMath"); z.operation = "SQRT"
        combine = nodes.new("ShaderNodeCombineColor")
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.space = "TANGENT"
        normal_map.uv_map = normal_uv_name
        # Blender's tangent basis is an approximation of the captured Rome II
        # basis. Bound its influence in the static preview to prevent packed
        # normal seams from crushing diffuse response.
        # The generic glTF bridge does not yet export the Rome draw-call
        # tangent basis used by the capture-replay backend.  Preserve and
        # validate the packed A/G texture, but do not feed an approximate
        # Blender basis into production colour proof renders: doing so creates
        # false striping that is absent from the approved runtime path.
        normal_map.inputs["Strength"].default_value = 0.0
        links.new(normal.outputs["Color"], split.inputs["Color"])
        links.new(normal.outputs["Alpha"], x.inputs[0])
        links.new(split.outputs["Green"], y.inputs[0])
        links.new(x.outputs[0], xx.inputs[0]); links.new(x.outputs[0], xx.inputs[1])
        links.new(y.outputs[0], yy.inputs[0]); links.new(y.outputs[0], yy.inputs[1])
        links.new(xx.outputs[0], sum_xy.inputs[0]); links.new(yy.outputs[0], sum_xy.inputs[1])
        links.new(sum_xy.outputs[0], remaining.inputs[1]); links.new(remaining.outputs[0], z.inputs[0])
        # Rome reconstructs tangent Z from the base A/G normal before applying
        # any dirt perturbation.  The simplified preview omits that perturbation
        # rather than replacing it with the former, structurally wrong RGB mix.
        for value, channel in ((x.outputs[0], "Red"), (y.outputs[0], "Green"), (z.outputs[0], "Blue")):
            encode = nodes.new("ShaderNodeMath"); encode.operation = "MULTIPLY_ADD"
            encode.inputs[1].default_value = 0.5; encode.inputs[2].default_value = 0.5
            links.new(value, encode.inputs[0]); links.new(encode.outputs[0], combine.inputs[channel])
        links.new(combine.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], socket(bsdf, "Normal"))

    mask = image_node(nodes, textures.get("Mask") or textures.get("SkinMask"), texture_root, blender_material.name, "preserved_mask")
    if mask:
        links.new(uv.outputs["UV"], mask.inputs["Vector"])
        split_mask = nodes.new("ShaderNodeSeparateColor")
        split_mask.name = "rome2_mask_channels"
        split_mask.label = "Preserved only: mask_r / mask_g / mask_b"
        links.new(mask.outputs["Color"], split_mask.inputs["Color"])
        if "SkinMask" in textures:
            if bsdf.inputs.get("Subsurface Weight"):
                skin_strength = nodes.new("ShaderNodeMath")
                skin_strength.name = "rome2_skin_mask_response"
                skin_strength.operation = "MULTIPLY"
                skin_strength.inputs[1].default_value = 0.12
                links.new(split_mask.outputs["Red"], skin_strength.inputs[0])
                links.new(skin_strength.outputs[0], bsdf.inputs["Subsurface Weight"])
            warnings.append("skin-mask R drives bounded generic skin response; mask remains Non-Color")
        else:
            warnings.append("faction mask RGB preserved but not applied")

    if spec["shader_flags"].get("alpha_test") and diffuse:
        cutout = nodes.new("ShaderNodeMath")
        cutout.operation = "GREATER_THAN"
        cutout.inputs[1].default_value = ALPHA_THRESHOLD
        links.new(diffuse.outputs["Alpha"], cutout.inputs[0])
        links.new(cutout.outputs[0], socket(bsdf, "Alpha"))
        if hasattr(blender_material, "surface_render_method"):
            blender_material.surface_render_method = "DITHERED"
        warnings.append(f"Rome alpha-test approximated as strict cutout at {ALPHA_THRESHOLD}")

    for node in nodes:
        node.select = False
    return warnings


def scene_signature():
    return {
        "actions": sorted((action.name, len(action.fcurves) if hasattr(action, "fcurves") else 0) for action in bpy.data.actions),
        "armatures": sorted((obj.name, len(obj.data.bones)) for obj in bpy.context.scene.objects if obj.type == "ARMATURE"),
        "geometry": sorted((obj.name, len(obj.data.vertices), len(obj.data.polygons)) for obj in bpy.context.scene.objects if obj.type == "MESH"),
        "matrices": sorted((obj.name, [round(value, 9) for row in obj.matrix_world for value in row]) for obj in bpy.context.scene.objects),
    }


def configure_camera(camera_settings, target_origin):
    scene = bpy.context.scene
    cameras = [obj for obj in scene.objects if obj.type == "CAMERA"]
    camera = cameras[0] if cameras else bpy.data.objects.new("rome2_material_camera", bpy.data.cameras.new("rome2_material_camera"))
    if not cameras:
        scene.collection.objects.link(camera)
    scene.camera = camera
    azimuth = math.radians(camera_settings["azimuth_degrees"])
    elevation = math.radians(camera_settings["elevation_degrees"])
    distance = camera_settings["distance"]
    target = Vector(target_origin)
    camera.location = target + Vector((distance * math.cos(elevation) * math.cos(azimuth), distance * math.cos(elevation) * math.sin(azimuth), distance * math.sin(elevation)))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = camera_settings["orthographic_scale"]


def configure_lighting(neutral, lighting=None):
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("rome2_material_world")
    for obj in list(scene.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)
    light_data = bpy.data.lights.new("rome2_material_key", "AREA" if neutral else "SUN")
    light = bpy.data.objects.new("rome2_material_key", light_data)
    scene.collection.objects.link(light)
    if neutral:
        light.location = (4.0, -5.0, 7.0)
    else:
        azimuth = math.radians(lighting["key_azimuth_degrees"])
        elevation = math.radians(lighting["key_elevation_degrees"])
        light.location = (10.0 * math.cos(elevation) * math.cos(azimuth), 10.0 * math.cos(elevation) * math.sin(azimuth), 10.0 * math.sin(elevation))
    light.rotation_euler = (Vector((0.0, 0.0, 1.0)) - light.location).to_track_quat("-Z", "Y").to_euler()
    light_data.energy = 900.0 if neutral else lighting["key_strength"]
    if neutral:
        light_data.shape = "DISK"
        light_data.size = 5.0
    else:
        light_data.angle = math.radians(lighting["key_angular_size_degrees"])
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0) if neutral else (0.35, 0.35, 0.35, 1.0)
    background.inputs["Strength"].default_value = 0.5 if neutral else lighting["ambient_strength"]


def render_proofs(render_dir, frames, profile_path):
    scene = bpy.context.scene
    render_dir.mkdir(parents=True, exist_ok=True)
    profile = json.loads(profile_path.read_text(encoding="utf-8")) if profile_path else None
    scene.render.resolution_x = profile["render"]["width"] if profile else 200
    scene.render.resolution_y = profile["render"]["height"] if profile else 200
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0
    scene.view_settings.gamma = 1.0
    outputs = []
    neutral_camera = {"azimuth_degrees": 45.0, "elevation_degrees": 30.0, "orthographic_scale": 4.5, "distance": 12.0}
    for mode in ("neutral", "aoe2-profile"):
        settings = neutral_camera if mode == "neutral" else profile["camera"]
        target = [0.0, 0.0, 0.0] if mode == "neutral" else profile["target"]["origin"]
        scene.render.engine = "BLENDER_EEVEE" if mode == "neutral" else profile["render"]["engine"]
        if mode != "neutral" and scene.render.engine == "CYCLES":
            scene.cycles.samples = profile["render"]["anti_aliasing_samples"]
            scene.cycles.use_denoising = False
        configure_camera(settings, target)
        configure_lighting(mode == "neutral", None if mode == "neutral" else profile["lighting"])
        for frame in frames:
            scene.frame_set(int(round(frame)), subframe=frame - round(frame))
            filename = f"{Path(bpy.data.filepath).stem}-frame-{frame:g}-{mode}.png"
            scene.render.filepath = str((render_dir / filename).resolve())
            bpy.ops.render.render(write_still=True)
            image = bpy.data.images.load(str((render_dir / filename).resolve()), check_existing=False)
            width, height = image.size
            pixels = list(image.pixels)
            points = [(index % width, height - 1 - index // width) for index in range(width * height) if pixels[index * 4 + 3] > 1.0 / 255.0]
            bounds = None if not points else [min(x for x, _ in points), min(y for _, y in points), max(x for x, _ in points) + 1, max(y for _, y in points) + 1]
            bpy.data.images.remove(image)
            outputs.append({
                "bounds": bounds,
                "frame": frame,
                "mode": mode,
                "output": filename,
                "pixel_height": None if bounds is None else bounds[3] - bounds[1],
            })
    return outputs


def run(args):
    bpy.ops.wm.open_mainfile(filepath=str(args.input_blend.resolve()))
    manifest = load_manifest(args.texture_manifest)
    indexed = material_index(manifest)
    before = scene_signature()
    warnings = {}
    for name, spec in indexed.items():
        material = bpy.data.materials.get(name)
        if material is None:
            raise RuntimeError(f"scene is missing material {name}")
        warnings[name] = build_material(material, spec, args.texture_root)
    after = scene_signature()
    if before != after:
        raise RuntimeError("material application changed geometry, transforms, armatures, or actions")
    frames = args.validation_frame or [float(bpy.context.scene.frame_start)]
    renders = render_proofs(args.render_dir, frames, args.render_profile) if args.render_dir else []
    args.output_blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(args.output_blend.resolve()))
    meshes = [obj for obj in bpy.context.scene.objects if obj.type == "MESH"]
    report = {
        "format": "rome2aoe2.blender-material-validation",
        "version": 1,
        "input": args.input_blend.name,
        "output": args.output_blend.name,
        "material_count": len(indexed),
        "material_slot_count": sum(len(obj.material_slots) for obj in meshes),
        "loaded_image_count": len([image for image in bpy.data.images if image.source == "FILE"]),
        "missing_image_count": manifest["summary"]["missing_authored_resource_count"],
        "shader_default_count": manifest["summary"]["shader_default_count"],
        "alpha_materials": sorted(name for name, spec in indexed.items() if spec["shader_flags"].get("alpha_test")),
        "mesh_count": len(meshes),
        "armature_count": len([obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]),
        "actions": sorted(action.name for action in bpy.data.actions),
        "equipment_visibility": {key: any(key in obj.name and not obj.hide_render for obj in meshes) for key in ("weapon_02", "weapon_03", "weapon_05")},
        "uv_errors": sorted(obj.name for obj in meshes if "UVMap" not in obj.data.uv_layers),
        "node_warnings": warnings,
        "validation_frames": frames,
        "proof_renders": renders,
        "validation": [
            {
                "frame": frame,
                "visible_objects": sorted(obj.name for obj in meshes if not obj.hide_render),
                "material_slots": sum(len(obj.material_slots) for obj in meshes if not obj.hide_render),
                "finite_render_bounds": all(item["bounds"] is not None for item in renders if item["frame"] == frame),
                "equipment_visibility": {key: any(key in obj.name and not obj.hide_render for obj in meshes) for key in ("weapon_02", "weapon_03", "weapon_05")},
            }
            for frame in frames
        ],
        "scene_state_preserved": True,
        "manual_transform_corrections": False,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(deterministic_json(report), encoding="utf-8")
    return report


if __name__ == "__main__":
    try:
        print(deterministic_json(run(arguments())), end="")
    except Exception as error:
        print(f"apply_rome2_materials: {error}", file=sys.stderr)
        raise
