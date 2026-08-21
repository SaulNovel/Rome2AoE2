"""Render controlled shared-asset A/B proofs against the Hastati oracle."""

import json
import shutil
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
import hastati_runtime_scene as accepted
import render_hastati_runtime_parity as oracle
import rome2_exact_material_backend as generic

OUT = ROOT / "build/validation/rome2aoe2/shared-material-parity"
GROUPS = {
    "skin": {"roman_body1", "roman_1_head", "roman_1_sandals", "roman_1_eyes_teeth"},
    "scutum": {"roman_early_scutum_lod1"},
    "gladius": {"roman_gladius_lod1"},
    "pilum": {"roman_pilum_light_lod1"},
}


def material_key(material):
    return material.name[:-9] if material.name.endswith("_Material") else material.name.split(".")[0]


def set_group(meshes, selected):
    for obj in meshes:
        keys = {material_key(slot.material) for slot in obj.material_slots if slot.material}
        obj.hide_render = not bool(keys & selected)


def image_array(path):
    image = bpy.data.images.load(str(path), check_existing=False)
    values = np.empty(len(image.pixels), np.float32)
    image.pixels.foreach_get(values)
    result = values.reshape((image.size[1], image.size[0], 4))[::-1].copy()
    bpy.data.images.remove(image)
    return result


def normalize(value):
    return value / np.maximum(np.linalg.norm(value, axis=-1, keepdims=True), 1e-12)


def legacy_generic_preparation(arrays):
    """Reproduce the rejected Principled graph's material-buffer semantics.

    Lighting/display are deliberately excluded and supplied by the oracle so
    this harness changes only material preparation.
    """
    family = arrays["family"]
    active = arrays["diffuse_raw"][..., 3] > .001
    skin = (family[..., 0] > .5) & (family[..., 1] < .5)
    decal = (family[..., 1] > .5) & (family[..., 0] < .5)
    dirt = (family[..., 2] > .5) & (family[..., 0] < .5) & (family[..., 1] < .5)
    normal = normalize(arrays["basis_normal"][..., :3] * 2 - 1)  # graph strength was zero
    diffuse = arrays["diffuse_raw"][..., :3].copy()
    mask = arrays["mask_raw"][..., :3]
    colours = np.asarray(oracle.FACTION, np.float32)
    for channel in range(3):
        q = np.where(skin, 0.0, mask[..., channel])[..., None]
        mapped = colours[[0, 2, 1]][channel] if np.any(decal) else colours[channel]
        diffuse += q * (diffuse * mapped - diffuse)
    spec_rgb = arrays["specular_raw"][..., :3]
    luma = np.sum(spec_rgb * np.array((.2126, .7152, .0722), np.float32), axis=-1)
    specular = np.repeat(luma[..., None], 3, axis=-1)
    gloss = arrays["gloss_raw"]
    smoothness = gloss[..., 0] ** 2
    reflectivity = gloss[..., 1].copy()
    # The rejected skin graph replaced captured RT2 with a small R-driven
    # Principled subsurface scalar and otherwise used the BSDF defaults.
    specular[skin] = .5
    reflectivity[skin] = arrays["specular_raw"][..., 0][skin] * .12
    specular[~active] = 0; diffuse[~active] = 0; smoothness[~active] = 0; reflectivity[~active] = 0
    return {"normal": normal, "diffuse": diffuse, "specular": specular,
            "smoothness": smoothness, "reflectivity": reflectivity}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    oracle.OUT = OUT
    oracle.AOV = OUT / "aov"
    oracle.RESOLUTION = 800
    oracle.OUT.mkdir(parents=True, exist_ok=True)
    oracle.AOV.mkdir(parents=True, exist_ok=True)
    scene, _, _, frame, meshes = accepted.configure()
    source_records = accepted.material_records()
    for material in bpy.data.materials:
        if material.name.endswith("_Material") and material.name[:-9] in source_records:
            material.name = material.name[:-9]
    scene.frame_set(frame)
    scene.render.resolution_x = scene.render.resolution_y = oracle.RESOLUTION
    records = []
    for slug, selected in GROUPS.items():
        set_group(meshes, selected)
        arrays = {name: oracle.render_aov(scene, accepted.TEXROOT, name) for name in generic.RAW_AOVS}
        oracle_name = f"{slug}-oracle.png"
        legacy_name = f"{slug}-legacy.png"
        generic_name = f"{slug}-generic.png"
        oracle.shade(scene, {key: value.copy() for key, value in arrays.items()},
                     output_name=oracle_name, diagnostics=False)
        oracle.shade(scene, {key: value.copy() for key, value in arrays.items()},
                     output_name=legacy_name, diagnostics=False,
                     prepared_override=legacy_generic_preparation(arrays))
        generic.shade(scene, {key: value.copy() for key, value in arrays.items()},
                      output_name=generic_name, diagnostics=False)
        a = image_array(OUT / oracle_name); legacy = image_array(OUT / legacy_name)
        b = image_array(OUT / generic_name); delta = np.abs(a[..., :3] - b[..., :3])
        legacy_delta = np.abs(a[..., :3] - legacy[..., :3])
        records.append({"asset_group": slug, "materials": sorted(selected),
                        "oracle": oracle_name, "legacy_generic": legacy_name, "generic": generic_name,
                        "legacy_mean_absolute_rgb_difference": float(legacy_delta.mean()),
                        "legacy_maximum_absolute_rgb_difference": float(legacy_delta.max()),
                        "mean_absolute_rgb_difference": float(delta.mean()),
                        "maximum_absolute_rgb_difference": float(delta.max()),
                        "passed": bool(np.array_equal(a, b))})
    report = {"format": "rome2aoe2.shared-material-parity", "version": 1,
              "oracle": "render_final_hastati_idle -> render_hastati_runtime_parity",
              "rejected_generic": "apply_rome2_materials_recovered semantics under common oracle lighting",
              "generic": "rome2_exact_material_backend", "records": records,
              "passed": all(row["passed"] for row in records)}
    (OUT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    if not report["passed"]:
        raise RuntimeError("shared material parity failed")


if __name__ == "__main__":
    main()
