"""Controlled presentation and attachment diagnostics for a static conversion."""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
import assemble_manifest_static as assembly  # noqa: E402


def args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def component_objects(component):
    return [obj for obj in bpy.context.scene.objects
            if obj.type == "MESH" and obj.get("manifest_component") == component]


def visible_bounds(objects):
    points = [obj.matrix_world @ Vector(corner) for obj in objects for corner in obj.bound_box]
    low = Vector(tuple(min(p[i] for p in points) for i in range(3)))
    high = Vector(tuple(max(p[i] for p in points) for i in range(3)))
    return low, high


def camera_for(objects, azimuth, elevation, multiplier):
    low, high = visible_bounds(objects); center = (low + high) * .5
    camera = bpy.context.scene.camera
    camera.data.ortho_scale = max(high - low) * multiplier
    target = Vector((center.x, center.y, center.z))
    a, e = math.radians(azimuth), math.radians(elevation)
    camera.location = target + Vector((12 * math.cos(e) * math.cos(a),
                                       12 * math.cos(e) * math.sin(a), 12 * math.sin(e)))
    camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
    return {"azimuth": azimuth, "elevation": elevation,
            "ortho_scale": camera.data.ortho_scale, "target": list(target)}


def isolate(component):
    selected = component_objects(component)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            obj.hide_render = obj not in selected
    return selected


def invariants(objects):
    normals = np.asarray([tuple(poly.normal) for obj in objects for poly in obj.data.polygons], np.float64)
    uvs = sum(len(layer.data) for obj in objects for layer in obj.data.uv_layers)
    return {"objects": [obj.name for obj in objects], "polygons": int(len(normals)),
            "normal_min": normals.min(axis=0).tolist(), "normal_max": normals.max(axis=0).tolist(),
            "normal_nan": int(np.isnan(normals).sum()), "normal_inf": int(np.isinf(normals).sum()),
            "uv_values": uvs, "active_uv": [obj.data.uv_layers.active.name for obj in objects]}


def render_pair(document, out, component):
    objects = isolate(component)
    root = bpy.data.objects.get("manifest_unit_direction_root")
    if root: root.rotation_euler[2] = 0.0
    current = camera_for(objects, -55.0, 24.0, 1.28)
    assembly.exact_render(bpy.context.scene, document, out, f"review-{component}-current.png", 900)
    # Keep the same source-facing surface toward the camera. The root rotation
    # changes only the object's relation to the frozen captured illumination.
    if root: root.rotation_euler[2] = math.radians(-167.5)
    bpy.context.view_layer.update()
    approved = camera_for(objects, 112.5, 18.0, 1.12)
    assembly.exact_render(bpy.context.scene, document, out, f"review-{component}-infantry-static-review-v1.png", 900)
    return {"material_and_backend_identical": True, "current_camera": current,
            "validated_camera": approved, "mesh_invariants": invariants(objects)}


def close_equipment(document, out):
    objects = [obj for key in ("body", "armour", "helmet", "crest", "shield", "melee_weapon")
               for obj in component_objects(key)]
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH": obj.hide_render = obj not in objects
    root = bpy.data.objects.get("manifest_unit_direction_root")
    if root: root.rotation_euler[2] = math.radians(-167.5)
    bpy.context.view_layer.update()
    camera_for(objects, 112.5, 18.0, .82)
    return assembly.exact_render(bpy.context.scene, document, out,
                                 "static-equipment-grip-close.png", 1400)


def grip_before_after(document, out):
    objects = component_objects("body") + component_objects("melee_weapon")
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH": obj.hide_render = obj not in objects
    root = bpy.data.objects.get("manifest_unit_direction_root")
    if root: root.rotation_euler[2] = math.radians(-167.5)
    bpy.context.view_layer.update()
    camera_for(objects, 112.5, 18.0, .72)
    weapon = component_objects("melee_weapon")[0]
    solved = weapon.matrix_basis.copy()
    assembly_report = json.loads((out / "static-assembly-report.json").read_text())
    source_rows = next(iter(assembly_report["attachments"]["melee_weapon"]["source_local_transforms"].values()))
    source = assembly.Matrix(source_rows)
    assembly.exact_render(bpy.context.scene, document, out, "gladius-grip-after.png", 1100)
    weapon.matrix_basis = source
    bpy.context.view_layer.update()
    assembly.exact_render(bpy.context.scene, document, out, "gladius-grip-before.png", 1100)
    weapon.matrix_basis = solved
    return {"before": "gladius-grip-before.png", "after": "gladius-grip-after.png",
            "controlled_change": "generic geometry/anatomy grip solution applied after source RMV pivot",
            "source_local_translation": list(source.translation),
            "solved_local_translation": list(solved.translation), "rotation_changed": True}


def emission(name, colour):
    material = bpy.data.materials.new(name); material.use_nodes = True
    node = material.node_tree.nodes.get("Principled BSDF")
    node.inputs["Base Color"].default_value = (*colour, 1)
    node.inputs["Emission Color"].default_value = (*colour, 1)
    node.inputs["Emission Strength"].default_value = .35
    node.inputs["Roughness"].default_value = .75
    return material


def marker(location, radius, material):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=radius, location=location)
    bpy.context.object.data.materials.append(material)


def segment(start, end, radius, material):
    delta = end - start
    bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=radius, depth=delta.length,
                                       location=(start + end) * .5)
    obj = bpy.context.object; obj.rotation_euler = delta.to_track_quat("Z", "Y").to_euler()
    obj.data.materials.append(material)


def grip_geometry_debug(out):
    report = json.loads((out / "static-assembly-report.json").read_text())
    grip = report["attachments"]["melee_weapon"]["grip_solver"]
    body = component_objects("body"); weapon = component_objects("melee_weapon")
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH": obj.hide_render = obj not in body + weapon
    grey, white = emission("debug_body", (.18, .2, .23)), emission("debug_weapon", (.85, .85, .88))
    for obj in body: obj.data.materials.clear(); obj.data.materials.append(grey)
    for obj in weapon: obj.data.materials.clear(); obj.data.materials.append(white)
    wrapper = weapon[0].parent
    point = lambda key: wrapper.matrix_world @ Vector(grip[key])
    grip_world = point("grip_point_local"); handle = point("handle_end_local"); blade = point("blade_end_local")
    red, green, blue, yellow = (emission("debug_hand", (1, .08, .05)), emission("debug_grip", (.1, 1, .2)),
                                emission("debug_blade", (.05, .35, 1)), emission("debug_handle", (1, .8, .05)))
    marker(grip_world, .025, green); marker(handle, .025, yellow); marker(blade, .025, blue)
    segment(handle, blade, .008, blue)
    # The closest weighted right-hand point supplies the anatomical marker.
    graph = bpy.context.evaluated_depsgraph_get(); candidates = []
    for source in body:
        group = source.vertex_groups.get("bn_righthand")
        if group is None: continue
        evaluated = source.evaluated_get(graph); mesh = evaluated.to_mesh()
        indices = {v.index for v in source.data.vertices
                   if any(g.group == group.index and g.weight > .01 for g in v.groups)}
        candidates.extend(evaluated.matrix_world @ mesh.vertices[i].co for i in indices)
        evaluated.to_mesh_clear()
    hand = min(candidates, key=lambda value: (value - grip_world).length); marker(hand, .025, red)
    origin = wrapper.matrix_world.translation
    for axis, material in zip((Vector((1,0,0)), Vector((0,1,0)), Vector((0,0,1))), (red, green, blue)):
        segment(origin, origin + wrapper.matrix_world.to_3x3() @ axis * .16, .006, material)
    scene = bpy.context.scene; scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = scene.render.resolution_y = 1400; scene.render.resolution_percentage = 100
    scene.render.film_transparent = True; scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str((out / "gladius-grip-geometry-debug.png").resolve())
    bpy.ops.render.render(write_still=True)
    return {"path": scene.render.filepath,
            "legend": {"red": "right-hand weighted surface / socket X", "green": "grip / socket Y",
                       "yellow": "handle end", "blue": "blade end and principal axis / socket Z"},
            "hand_to_grip_distance": (hand - grip_world).length}


def main():
    options = args(); options.output.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(options.blend.resolve()))
    document = json.loads(options.input.read_text(encoding="utf-8"))
    render_root = options.input.parent
    report = {"format": "rome2aoe2.static-review-diagnostics", "version": 1,
              "controlled_variable": "camera/presentation only",
              "backend": "rome2_exact_material_backend", "material_equations_changed": False,
              "shield": render_pair(document, render_root, "shield"),
              "helmet": render_pair(document, render_root, "helmet")}
    report["shield"].update({"material": "roman_early_scutum_lod1",
                              "faction_channel_order": ["primary", "tertiary", "secondary"]})
    report["helmet"].update({"material": "hellenic_konos", "crest_hidden": True})
    report["grip_before_after"] = grip_before_after(document, render_root)
    report["close_diagnostic"] = close_equipment(document, render_root)
    report["grip_geometry_debug"] = grip_geometry_debug(render_root)
    path = options.output / "static-review-diagnostics.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
