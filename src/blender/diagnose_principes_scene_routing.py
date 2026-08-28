"""Audit full-scene material/AOV routing without changing material equations."""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/blender"))
import render_hastati_runtime_parity as runtime  # noqa: E402
import rome2_exact_material_backend as exact  # noqa: E402

IDENTITY = "bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6"
CONVERSION = ROOT / "build/conversions/rom_principes" / IDENTITY
OUT = ROOT / "build/validation/rome2aoe2/principes-scene-routing"
COMPONENT_ORDER = ("body", "armour", "helmet", "crest", "shield", "melee_weapon", "missile_weapon")
SHARED = ("body", "shield", "melee_weapon", "missile_weapon")


def component(obj):
    return obj.name.split("__", 1)[0] if "__" in obj.name else None


def meshes():
    return [obj for obj in bpy.data.objects if obj.type == "MESH" and component(obj) in COMPONENT_ORDER]


def visibility(enabled):
    enabled = set(enabled)
    for obj in meshes():
        obj.hide_render = component(obj) not in enabled


def arrays(label, enabled, resolution=320):
    visibility(enabled)
    runtime.OUT = OUT / label
    runtime.AOV = runtime.OUT / "aov"
    runtime.RESOLUTION = resolution
    scene = bpy.context.scene
    scene.render.resolution_x = scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "OPEN_EXR"
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.image_settings.color_depth = "32"
    scene.view_settings.view_transform = "Raw"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = 0
    scene.view_settings.gamma = 1
    runtime.OUT.mkdir(parents=True, exist_ok=True)
    runtime.AOV.mkdir(parents=True, exist_ok=True)
    return {name: runtime.render_aov(bpy.context.scene, CONVERSION, name, CONVERSION.parent.parent.parent / "cache/rome2aoe2/assets-v1")
            for name in exact.RAW_AOVS}


def active(a):
    return a["diffuse_raw"][..., 3] > .001


def interior(mask):
    result=mask.copy()
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            result &= np.roll(np.roll(mask,dy,axis=0),dx,axis=1)
    result[[0,-1],:]=False;result[:,[0,-1]]=False
    return result


def compare(reference, candidate, overlap=None):
    overlap = active(reference) & active(candidate) if overlap is None else overlap
    rows = {}
    for name in exact.RAW_AOVS:
        delta = np.abs(reference[name][overlap] - candidate[name][overlap])
        rows[name] = {"overlap_pixels": int(np.count_nonzero(overlap)),
                      "mean_abs": float(delta.mean()) if delta.size else 0.0,
                      "max_abs": float(delta.max()) if delta.size else 0.0}
    return rows


def component_id_array(enabled, resolution):
    visibility(enabled)
    codes = {name: (index + 1) / 16.0 for index, name in enumerate(COMPONENT_ORDER)}
    for obj in meshes():
        value = codes[component(obj)]
        for slot in obj.material_slots:
            material = slot.material
            if material is None: continue
            material.use_nodes=True;nodes=material.node_tree.nodes;nodes.clear()
            output=nodes.new("ShaderNodeOutputMaterial");emission=nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value=(value,0,0,1)
            material.node_tree.links.new(emission.outputs[0],output.inputs["Surface"])
    scene=bpy.context.scene;scene.render.resolution_x=scene.render.resolution_y=resolution
    scene.render.resolution_percentage=100;scene.render.image_settings.file_format="OPEN_EXR"
    scene.render.image_settings.color_mode="RGBA";scene.view_settings.view_transform="Raw"
    path=OUT/"component-id-working.exr";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    image=bpy.data.images.load(str(path),check_existing=False);data=np.empty(len(image.pixels),np.float32)
    image.pixels.foreach_get(data);data=data.reshape((resolution,resolution,4))[::-1].copy();bpy.data.images.remove(image)
    return data,codes


def aov_stats(a):
    result = {}
    for name, value in a.items():
        result[name] = {"min": float(np.nanmin(value)), "max": float(np.nanmax(value)),
                        "nan": int(np.isnan(value).sum()), "inf": int(np.isinf(value).sum())}
    for name in ("basis_normal", "basis_tangent", "basis_bitangent"):
        vectors = a[name][..., :3] * 2 - 1
        lengths = np.linalg.norm(vectors[active(a)], axis=-1)
        result[name]["zero_vectors"] = int(np.count_nonzero(lengths < 1e-5))
        result[name]["length_min_active"] = float(lengths.min())
        result[name]["length_max_active"] = float(lengths.max())
    return result


def mesh_record(obj):
    uv = obj.data.uv_layers
    uv_stats={}
    for layer in uv:
        values=np.asarray([tuple(item.uv) for item in layer.data],np.float32)
        uv_stats[layer.name]={"min":values.min(axis=0).tolist(),"max":values.max(axis=0).tolist(),
                              "nan":int(np.isnan(values).sum()),"inf":int(np.isinf(values).sum()),
                              "distinct":int(len(np.unique(values,axis=0)))}
    tangent_stats={"available":False}
    active_uv=uv.active.name if uv.active else None
    if active_uv:
        obj.data.calc_tangents(uvmap=active_uv)
        tangents=np.asarray([tuple(loop.tangent) for loop in obj.data.loops],np.float32)
        signs=np.asarray([loop.bitangent_sign for loop in obj.data.loops],np.float32)
        tangent_stats={"available":True,"min":tangents.min(axis=0).tolist(),"max":tangents.max(axis=0).tolist(),
                       "nan":int(np.isnan(tangents).sum()),"inf":int(np.isinf(tangents).sum()),
                       "zero":int(np.count_nonzero(np.linalg.norm(tangents,axis=1)<1e-6)),
                       "handedness":sorted(float(value) for value in np.unique(signs))}
        obj.data.free_tangents()
    camera=bpy.context.scene.camera
    world=np.asarray([tuple((camera.matrix_world.inverted()@(obj.matrix_world@vertex.co))) for vertex in obj.data.vertices],np.float32)
    return {"component": component(obj), "object": obj.name,
            "material_slots": [{"slot": index, "blender_material": slot.material.name,
                                "source_material": slot.material.name.split(".")[0]}
                               for index, slot in enumerate(obj.material_slots) if slot.material],
            "uv_layers": [layer.name for layer in uv],
            "active_uv": uv.active.name if uv.active else None,
            "render_uv": next((layer.name for layer in uv if layer.active_render), None),
            "uv_stats":uv_stats,"tangent_stats":tangent_stats,
            "camera_depth":{"min":float((-world[:,2]).min()),"max":float((-world[:,2]).max()),
                            "nan":int(np.isnan(world[:,2]).sum()),"inf":int(np.isinf(world[:,2]).sum())},
            "vertices": len(obj.data.vertices), "loops": len(obj.data.loops),
            "polygons": len(obj.data.polygons)}


def material_id_render(records):
    palette = [(0.90,0.12,0.12,1),(0.10,0.75,0.20,1),(0.10,0.30,0.95,1),(0.95,0.75,0.08,1),
               (0.85,0.10,0.85,1),(0.05,0.85,0.85,1),(0.95,0.45,0.08,1),(0.55,0.25,0.95,1),
               (0.35,0.85,0.55,1),(0.95,0.45,0.65,1),(0.55,0.55,0.55,1)]
    names = sorted({slot["source_material"] for row in records for slot in row["material_slots"]})
    legend = {}
    for index, name in enumerate(names):
        colour = palette[index % len(palette)]; legend[name] = colour[:3]
        for material in bpy.data.materials:
            if material.name.split(".")[0] != name: continue
            material.use_nodes=True; nodes=material.node_tree.nodes; nodes.clear()
            output=nodes.new("ShaderNodeOutputMaterial"); emission=nodes.new("ShaderNodeEmission")
            emission.inputs["Color"].default_value=colour
            material.node_tree.links.new(emission.outputs[0],output.inputs["Surface"])
    scene=bpy.context.scene;visibility(COMPONENT_ORDER);scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=scene.render.resolution_y=1000;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format="PNG";scene.render.image_settings.color_mode="RGBA"
    scene.render.film_transparent=True;scene.view_settings.view_transform="Raw";scene.view_settings.look="None"
    path=OUT/"material-id-debug.png";scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
    (OUT/"material-id-legend.json").write_text(json.dumps(legend,indent=2,sort_keys=True)+"\n")
    return str(path), legend


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(CONVERSION / "static-unit.blend"))
    root=bpy.data.objects.get("manifest_unit_direction_root")
    if root: root.rotation_euler[2]=np.deg2rad(45);bpy.context.view_layer.update()
    records=[mesh_record(obj) for obj in meshes()]
    material_ids={name:index+1 for index,name in enumerate(sorted(
        {slot["source_material"] for row in records for slot in row["material_slots"]}))}
    for row in records:
        for slot in row["material_slots"]:
            slot["runtime_prepared_material_key"]=slot["source_material"]
            slot["aov_material_id"]=material_ids[slot["source_material"]]
    full_ids,codes=component_id_array(COMPONENT_ORDER,320)
    full=arrays("full", COMPONENT_ORDER)
    isolated={}; comparisons={}
    for name in SHARED:
        candidate=arrays(f"isolated-{name}", (name,))
        mask=interior((np.abs(full_ids[...,0]-codes[name])<1e-4)&(candidate["diffuse_raw"][...,3]>.999))
        isolated[name]=candidate; comparisons[name]=compare(full,candidate,mask)
    bisection=[]; previous=None
    previous_ids=None
    for end in range(1,len(COMPONENT_ORDER)+1):
        enabled=COMPONENT_ORDER[:end]; current=arrays(f"bisect-{end}-{enabled[-1]}",enabled,240)
        if previous is not None:
            current_ids,_=component_id_array(enabled,240)
            same=interior((np.abs(previous_ids[...,0]-current_ids[...,0])<1e-4)&(previous_ids[...,0]>.001))
            bisection.append({"addition":enabled[-1],"stable_visible_pixels":int(np.count_nonzero(same)),
                              "previous_aov_change":compare(previous,current,same)})
            previous_ids=current_ids
        else:
            previous_ids,_=component_id_array(enabled,240)
        previous=current
    # Reopen to restore material data before producing the independent flat-ID render.
    bpy.ops.wm.open_mainfile(filepath=str(CONVERSION / "static-unit.blend"))
    if root:=bpy.data.objects.get("manifest_unit_direction_root"):
        root.rotation_euler[2]=np.deg2rad(45);bpy.context.view_layer.update()
    debug,legend=material_id_render(records)
    report={"format":"rome2aoe2.principes-scene-routing","version":1,
            "material_mapping":records,"material_id_debug":debug,"material_id_legend":legend,
            "full_aov_stats":aov_stats(full),"isolated_vs_assembled":comparisons,
            "assembly_bisection":bisection}
    (OUT/"routing-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({"report":str(OUT/"routing-report.json"),"debug":debug}))


if __name__ == "__main__":
    main()
