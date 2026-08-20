"""Accepted Hastati scene setup for the frozen Rome II runtime renderer.

This is the production-owned subset of the formerly experimental Asset Editor
integration driver.  Material preparation and lighting remain in
``render_hastati_runtime_parity``; this module only opens the approved assembled
blend, identifies its material records, and establishes the fixed raw-AOV scene.
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


ROOT = Path(__file__).resolve().parents[2]
BLEND = ROOT / "build/community_tool_investigation/complete-hastati-native-textured/complete-hastati-native-textured.blend"
TEXROOT = ROOT / "build/local-integration/rome2/cross-unit-calibration/units/hastati"
RES = 1600
TARGETS = {
    "skin": ("roman_1_head", "roman_1_eyes_teeth"),
    "cuirass": ("italian_square_muscled_cuirass_",),
    "helmet": ("roman_montefortino",),
    "tunic": ("E3_tunic", "E3_tunic_flipped"),
    "shield": ("roman_early_scutum_lod1",),
    "sandals-legs": ("roman_1_sandals", "roman_body1"),
    "gladius": ("roman_gladius_lod1",),
    "pilum": ("roman_pilum_light_lod1",),
    "crest": ("black_feather_03_lod1",),
}


def bounds(meshes):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in meshes:
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        points.extend(evaluated.matrix_world @ vertex.co for vertex in mesh.vertices)
        evaluated.to_mesh_clear()
    return (Vector([min(point[index] for point in points) for index in range(3)]),
            Vector([max(point[index] for point in points) for index in range(3)]))


def camera(meshes):
    low, high = bounds(meshes)
    center = (low + high) / 2
    span = max(high - low)
    azimuth = math.radians(112.5)
    elevation = math.radians(18)
    direction = Vector((math.cos(azimuth) * math.cos(elevation),
                        math.sin(azimuth) * math.cos(elevation), math.sin(elevation)))
    location = center + direction * span * 3
    bpy.ops.object.camera_add(location=location)
    result = bpy.context.object
    result.data.type = "ORTHO"
    result.data.ortho_scale = span * 1.12
    result.rotation_euler = (center - location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = result


def configure():
    bpy.ops.wm.open_mainfile(filepath=str(BLEND))
    scene = bpy.context.scene
    arms = [obj for obj in scene.objects if obj.type == "ARMATURE"]
    if len(arms) != 1 or len(arms[0].data.bones) != 50:
        raise RuntimeError("approved Hastati scene must contain one 50-bone armature")
    armature = arms[0]
    action = armature.animation_data.action
    reference_frame = (int(action.frame_range[0]) + int(round(action.frame_range[1]))) // 2
    scene.frame_set(reference_frame)
    for obj in list(scene.objects):
        if obj.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(obj, do_unlink=True)
    meshes = [obj for obj in scene.objects
              if obj.type == "MESH" and not obj.hide_render and "Icosphere" not in obj.name]
    camera(meshes)
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = RES
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "ZIP"
    scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Raw"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    return scene, armature, action, reference_frame, meshes


def material_records():
    document = json.loads((TEXROOT / "texture-manifest.json").read_text())
    return {material["material_name"]: material for material in document["materials"]}
