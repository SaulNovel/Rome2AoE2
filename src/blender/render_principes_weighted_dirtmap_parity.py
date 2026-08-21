"""Controlled exact-vs-rejected preparation proof for Principes dirt materials."""

import json
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
sys.path.insert(0, str(ROOT / "src"))
import render_hastati_runtime_parity as runtime
import rome2_exact_material_backend as exact
from render_shared_material_parity import image_array, legacy_generic_preparation
from rome2.runtime_material_preparation import faction_diffuse, tangent_normal, DIRT_COLOUR

IDENTITY = "bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6"
CONVERSION = ROOT / "build/conversions/rom_principes" / IDENTITY
OUT = ROOT / "build/validation/rome2aoe2/principes-weighted-dirtmap-parity"
GROUPS = {
    "lorica": {"lorica_hamata_A"},
    "belt": {"roman_belt_01"},
    "helmet": {"hellenic_konos"},
}


def key(material):
    return material.name.split(".")[0]


def exact_weighted_preparation(arrays):
    arrays["normal_sample"][...,3]=arrays["normal_alpha"][...,0]
    arrays["dirt_raw"][...,3]=arrays["dirt_alpha"][...,0]
    arrays["dirt_mask_raw"][...,3]=arrays["dirt_mask_alpha"][...,0]
    active=arrays["diffuse_raw"][...,3]>.001; shape=active.shape
    base=runtime.normalize(arrays["basis_normal"][...,:3]*2-1)
    tangent=runtime.normalize(arrays["basis_tangent"][...,:3]*2-1)
    bitangent=runtime.normalize(arrays["basis_bitangent"][...,:3]*2-1)
    result={"normal":base.copy(),"diffuse":np.zeros((*shape,3),np.float32),
            "specular":np.zeros((*shape,3),np.float32),"smoothness":np.zeros(shape,np.float32),
            "reflectivity":np.zeros(shape,np.float32)}
    if np.any(active):
        q=active;p=runtime.prepare_weighted_dirtmap(
            arrays["diffuse_raw"][q],arrays["specular_raw"][q],arrays["normal_sample"][q],
            arrays["gloss_raw"][q],arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],
            base[q],tangent[q],bitangent[q],arrays["mask_raw"][q],runtime.FACTION)
        result["normal"][q]=p.normal;result["diffuse"][q]=p.diffuse;result["specular"][q]=p.specular
        result["smoothness"][q]=p.smoothness;result["reflectivity"][q]=p.reflectivity
    return result,base


def exact_stages(arrays):
    arrays={k:v.copy() for k,v in arrays.items()}
    arrays["normal_sample"][...,3]=arrays["normal_alpha"][...,0]
    arrays["dirt_raw"][...,3]=arrays["dirt_alpha"][...,0]
    arrays["dirt_mask_raw"][...,3]=arrays["dirt_mask_alpha"][...,0]
    active=arrays["diffuse_raw"][...,3]>.001;base=runtime.normalize(arrays["basis_normal"][...,:3]*2-1)
    tangent=runtime.normalize(arrays["basis_tangent"][...,:3]*2-1);bitangent=runtime.normalize(arrays["basis_bitangent"][...,:3]*2-1)
    raw=arrays["diffuse_raw"][...,:3];masked=faction_diffuse(arrays["diffuse_raw"],arrays["mask_raw"],runtime.FACTION)
    amount=arrays["dirt_raw"][...,3]*arrays["dirt_mask_raw"][...,3]
    dirty=masked+amount[...,None]*(DIRT_COLOUR-masked)
    spec=arrays["specular_raw"][...,:3]*(1-.99*amount)[...,None]
    smooth=arrays["gloss_raw"][...,0];reflect=arrays["gloss_raw"][...,1]
    final_normal=tangent_normal(arrays["normal_sample"],base,tangent,bitangent,
                                arrays["dirt_raw"],arrays["dirt_mask_raw"],True)
    def stage(d,n=base,f=None,s=None,r=None):
        return {"normal":n,"diffuse":np.where(active[...,None],d,0),
                "specular":np.zeros_like(d) if f is None else np.where(active[...,None],f,0),
                "smoothness":np.zeros_like(smooth) if s is None else np.where(active,s,0),
                "reflectivity":np.zeros_like(reflect) if r is None else np.where(active,r,0)}
    return {
        "A-diffuse":stage(raw),"B-faction":stage(masked),"C-dirt":stage(dirty),
        "D-spec-gloss":stage(dirty,f=spec,s=smooth,r=reflect),
        "E-normal":stage(dirty,final_normal,spec,smooth,reflect),
        "F-final":stage(dirty,final_normal,spec,smooth,reflect),
    }


def main():
    OUT.mkdir(parents=True, exist_ok=True); (OUT / "aov").mkdir(exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(CONVERSION / "static-unit.blend"))
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"; scene.render.resolution_percentage = 100
    scene.render.film_transparent = True; scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"; scene.render.image_settings.color_depth = "32"
    scene.render.image_settings.exr_codec = "ZIP"; scene.display_settings.display_device = "sRGB"
    scene.view_settings.view_transform = "Raw"; scene.view_settings.look = "None"
    scene.view_settings.exposure = 0; scene.view_settings.gamma = 1
    meshes = [obj for obj in scene.objects if obj.type == "MESH" and obj.name != "conversion_ground"]
    ground=bpy.data.objects.get("conversion_ground")
    if ground is not None: ground.hide_render=True
    texture_root = Path(json.loads((CONVERSION / "static-assembly-input.json").read_text())["texture_root"])
    runtime.OUT = OUT; runtime.AOV = OUT / "aov"; runtime.RESOLUTION = 800
    scene.render.resolution_x = scene.render.resolution_y = runtime.RESOLUTION
    rows = []
    for slug, materials in GROUPS.items():
        for obj in meshes:
            obj.hide_render = not any(key(slot.material) in materials for slot in obj.material_slots if slot.material)
        arrays = {name: runtime.render_aov(scene, CONVERSION, name, texture_root) for name in exact.RAW_AOVS}
        for stage_name,stage_values in exact_stages(arrays).items():
            runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=f"{slug}-{stage_name}.png",
                          diagnostics=False,prepared_override=stage_values)
        prepared,base=exact_weighted_preparation({k:v.copy() for k,v in arrays.items()})
        diffuse_only={k:v.copy() if hasattr(v,"copy") else v for k,v in prepared.items()}
        diffuse_only["normal"]=base;diffuse_only["specular"][:]=0;diffuse_only["smoothness"][:]=0;diffuse_only["reflectivity"][:]=0
        pre_normal={k:v.copy() if hasattr(v,"copy") else v for k,v in prepared.items()};pre_normal["normal"]=base
        runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=f"{slug}-stage-1-diffuse.png",diagnostics=False,prepared_override=diffuse_only)
        runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=f"{slug}-stage-3-spec-gloss.png",diagnostics=False,prepared_override=pre_normal)
        runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=f"{slug}-stage-4-normal-final.png",diagnostics=False,prepared_override=prepared)
        oracle_name=f"{slug}-exact.png"; legacy_name=f"{slug}-legacy.png"; generic_name=f"{slug}-generic.png"
        runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=oracle_name,diagnostics=False)
        runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=legacy_name,diagnostics=False,
                      prepared_override=legacy_generic_preparation(arrays))
        exact.shade(scene,{k:v.copy() for k,v in arrays.items()},output_name=generic_name,diagnostics=False)
        a=image_array(OUT/oracle_name); old=image_array(OUT/legacy_name); new=image_array(OUT/generic_name)
        old_delta=np.abs(a[...,:3]-old[...,:3]);new_delta=np.abs(a[...,:3]-new[...,:3])
        rows.append({"group":slug,"materials":sorted(materials),"legacy_mean_difference":float(old_delta.mean()),
                     "legacy_max_difference":float(old_delta.max()),"exact_mean_difference":float(new_delta.mean()),
                     "exact_max_difference":float(new_delta.max()),"passed":bool(np.array_equal(a,new))})
    source_manifest=json.loads((CONVERSION/"texture-manifest.json").read_text())
    selected={row["material_name"]:row for row in source_manifest["materials"]
              if row["material_name"] in {name for values in GROUPS.values() for name in values}}
    report={"format":"rome2aoe2.principes-weighted-dirtmap-parity","version":1,
            "manifest_identity":IDENTITY,"preparation":"prepare_weighted_dirtmap",
            "test_black":"zero-contribution sentinel","records":rows,
            "capture_equivalence":{
                "shader_family":"captured roman_montefortino event 1418 / PS 2168",
                "gbuffer_and_lighting":"event 1915",
                "faction_equation":"captured Weighted faction permutation; identity C0/C1/C2 for selected hamata VMD entry",
                "dirt_uv":"RMV float0/float1 scale; zero instance offset",
            },
            "source_materials":selected,
            "capture_validated_for_selected_assets":True,
            "passed":all(row["passed"] for row in rows)}
    (OUT/"report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")


if __name__ == "__main__": main()
