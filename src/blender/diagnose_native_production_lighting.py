"""Controlled exact-backend lighting-space diagnostic for a native unit scene."""
import argparse, json, math, os, shutil, sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "src/blender"), str(ROOT / "src/rome2")]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production
from aoe2.facet_mapping import soldier_yaw_degrees


def arguments():
    p = argparse.ArgumentParser()
    p.add_argument("--input-blend", type=Path, required=True)
    p.add_argument("--static-input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--resolution", type=int, default=320)
    p.add_argument("--category", choices=("idle", "attack"), required=True)
    p.add_argument("--sample-fraction", type=float, default=.5)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def component_mask(scene, texture_root, component):
    objects = [o for o in scene.objects if o.type == "MESH"]
    hidden = {o: o.hide_render for o in objects}
    for obj in objects:
        obj.hide_render = obj.get("manifest_component") != component
    result = runtime.render_aov(scene, runtime.OUT, "diffuse_raw", texture_root)[..., 3] > .001
    for obj, value in hidden.items():
        obj.hide_render = value
    return result


def region_stats(image_path, mask):
    image = bpy.data.images.load(str(image_path.resolve()), check_existing=False)
    data = np.empty(len(image.pixels), np.float32); image.pixels.foreach_get(data)
    rgba = data.reshape((image.size[1], image.size[0], 4))[::-1]
    bpy.data.images.remove(image)
    lum = rgba[..., :3] @ np.array((.2126, .7152, .0722), np.float32)
    active = mask & (rgba[..., 3] > .001)
    if not np.any(active):
        return {"pixels": 0, "mean": None, "dark_percentage": None, "p95": None}
    values = lum[active]
    return {"pixels": int(len(values)), "mean": float(values.mean()),
            "dark_percentage": float(100 * np.count_nonzero(values < .08) / len(values)),
            "p95": float(np.percentile(values, 95))}

def load_rgba(image_path):
    image=bpy.data.images.load(str(image_path.resolve()),check_existing=False)
    data=np.empty(len(image.pixels),np.float32);image.pixels.foreach_get(data)
    rgba=data.reshape((image.size[1],image.size[0],4))[::-1].copy();bpy.data.images.remove(image);return rgba

def basis_stats(arrays,mask):
    norm=lambda v:v/np.maximum(np.linalg.norm(v,axis=-1,keepdims=True),1e-12)
    n=norm(arrays["basis_normal"][...,:3]*2-1);t=norm(arrays["basis_tangent"][...,:3]*2-1);b=norm(arrays["basis_bitangent"][...,:3]*2-1);active=mask&(arrays["diffuse_raw"][...,3]>.001)
    handed=np.sum(np.cross(n,t)*b,axis=-1);return {"pixels":int(np.count_nonzero(active)),"normal_length_max_error":float(np.max(np.abs(np.linalg.norm(n[active],axis=-1)-1))),"tangent_length_max_error":float(np.max(np.abs(np.linalg.norm(t[active],axis=-1)-1))),"bitangent_length_max_error":float(np.max(np.abs(np.linalg.norm(b[active],axis=-1)-1))),"normal_tangent_abs_dot_p95":float(np.percentile(np.abs(np.sum(n*t,axis=-1)[active]),95)),"normal_bitangent_abs_dot_p95":float(np.percentile(np.abs(np.sum(n*b,axis=-1)[active]),95)),"tangent_bitangent_abs_dot_p95":float(np.percentile(np.abs(np.sum(t*b,axis=-1)[active]),95)),"handedness_median":float(np.median(handed[active])),"negative_handedness_fraction":float(np.count_nonzero(handed[active]<0)/np.count_nonzero(active))}


def main():
    a = arguments(); a.output.mkdir(parents=True, exist_ok=True)
    doc = json.loads(a.static_input.read_text()); shutil.copyfile(doc["texture_manifest"], a.output / "texture-manifest.json")
    bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()))
    scene = bpy.context.scene; production.camera(scene)
    root = bpy.data.objects["Rome2AoE2_FacetRoot"]
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    start, end = arm.animation_data.action.frame_range
    sample=start+(end-start)*a.sample_fraction
    scene.frame_set(int(sample),subframe=sample-int(sample));bpy.context.view_layer.update()
    runtime.RESOLUTION = a.resolution
    scene.render.resolution_x = scene.render.resolution_y = a.resolution
    scene.render.resolution_percentage = 100; scene.render.film_transparent = True
    scene.render.image_settings.file_format = "OPEN_EXR"; scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"; scene.render.image_settings.exr_codec = "ZIP"
    scene.display_settings.display_device = "sRGB"; scene.view_settings.view_transform = "Raw"
    texture_root = Path(doc["texture_root"])
    records = []
    policies = {"current":{"floor":None},"shield-readability-floor-2.10":{"floor":2.10},"shield-readability-floor-2.40":{"floor":2.40},"shield-readability-floor-2.70":{"floor":2.70}}
    for direction in range(16):
        yaw = soldier_yaw_degrees(direction); root.rotation_euler[2] = math.radians(yaw)
        bpy.context.view_layer.update()
        work = a.output / "aov" / f"direction-{direction:02d}"
        runtime.OUT = a.output; runtime.AOV = work; work.mkdir(parents=True, exist_ok=True)
        arrays = {name: runtime.render_aov(scene, a.output, name, texture_root) for name in exact.exact_materials.RAW_AOVS}
        semantic_roles = runtime.render_aov(scene, a.output, "semantic_role", texture_root)
        shield_mask = component_mask(scene, texture_root, "shield")
        family=arrays["family"];visible_decal=(family[...,1]>.5)&(family[...,0]<.5)
        # The isolated component silhouette includes shield pixels hidden behind
        # the composited unit. Restrict policy/metrics to visible material ownership.
        shield_mask &= visible_decal
        armour_mask = component_mask(scene, texture_root, "armour")
        # Visible ownership, not an isolated component silhouette.  The latter
        # includes weapon pixels hidden behind the shield and contaminated the
        # earlier screen-space metric when those shield pixels changed.
        weapon_mask = (semantic_roles[..., 1] > .5) & (semantic_roles[..., 0] < .5)
        equipment_mask=shield_mask
        body_mask=component_mask(scene,texture_root,"body");metric_masks={"shield":shield_mask,"weapon":weapon_mask,"armour":armour_mask,"body":body_mask}
        basis={name:basis_stats(arrays,mask) for name,mask in metric_masks.items()}
        direction_records=[]
        for name, policy in policies.items():
            output_name = f"{name}-direction-{direction:02d}.png"
            metrics = runtime.shade(scene, arrays, environment_yaw_degrees=0,
                                    illumination_yaw_offset_degrees=0,
                                    readability_fill=.60,equipment_readability=0,equipment_mask=equipment_mask,metric_masks=metric_masks,
                                    equipment_diffuse_irradiance_floor=policy["floor"],equipment_floor_transition=.15,
                                    output_name=output_name,diagnostics=False)
            path = a.output / output_name
            metrics["shield"] = region_stats(path, shield_mask)
            metrics["armour"] = region_stats(path, armour_mask)
            metrics["weapon"] = region_stats(path, weapon_mask)
            direction_records.append({"direction": direction, "root_yaw_degrees": yaw,
                            "policy": name, "output": str(path), "metrics": metrics,"basis":basis})
        current=load_rgba(Path(direction_records[0]["output"]));excluded=~equipment_mask
        for record in direction_records[1:]:
            candidate=load_rgba(Path(record["output"]));delta=np.abs(candidate[...,:3]-current[...,:3])
            record["excluded_equipment_pixel_control"]={"max_rgb_difference":float(delta[excluded].max()),"changed_channel_count":int(np.count_nonzero(delta[excluded]))}
        records.extend(direction_records)
    report = {
        "format": "rome2aoe2.native-production-lighting-diagnostic", "version": 1,
        "input_blend": str(a.input_blend), "category":a.category,"sample_fraction":a.sample_fraction,"resolution":[a.resolution,a.resolution],"output_scale":"x2/high_definition","x1_generated":False,"shadow_pass_modified": False,
        "coordinate_audit": {
            "normal_tangent_bitangent": "Blender world space after armature deformation and FacetRoot yaw; emitted by Geometry/NormalMap nodes",
            "captured_sun": "Rome-II vector converted once to Blender world space; environment yaw applied once; no unit-root transform",
            "environment_reflection": "world-space reflected view vector converted to Rome-II cube basis; environment yaw applied once",
            "view_vector": "world-fixed orthographic camera forward from camera.matrix_world quaternion",
            "unit_root": "object transform only; rotates geometry and therefore rasterized world-space basis",
            "camera": "fixed world transform",
            "captured_world_view_matrix": "not used by the CPU exact backend",
            "double_transform": False,
        },
        "policies": policies, "records": records,
    }
    (a.output / "lighting-diagnostic.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
