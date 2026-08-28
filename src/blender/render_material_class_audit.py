"""Reusable diagnostic-only material-class audit for an assembled Rome II unit.

Loads a production blend, records mesh/material coverage, replaces materials
in-memory with fixed class colors, and renders four views. It never saves the
blend and therefore cannot contaminate production materials.
"""
import json,math
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[2]
BLEND=ROOT/"build"/"local-integration"/"rome2"/"textured"/"sws_stand_textured.blend"
OUT=ROOT/"build"/"local-integration"/"rome2"/"material-class-audit"
COLORS={"skin":(1.0,.16,.28,1),"bronze":(1.0,.65,.02,1),"iron/steel":(.03,.28,1.0,1),
        "cloth":(.05,.65,.12,1),"leather":(.32,.09,.025,1),"other":(.65,.10,.75,1)}

EXPECTED={
 "roman_1_head":"skin","roman_body1":"skin","roman_1_eyes_teeth":"other",
 "3c_aurelian_pants":"mixed cloth/skin","3c_niederbieber_helmet":"bronze",
 "lorica_hamata_A":"iron/steel","celtic_basic_tunic_cut_01":"cloth","roman_cloak_armour":"cloth",
 "mhorsehair_01_lod1":"other","roman_gladius_lod1":"mixed iron/steel/leather",
 "roman_pilum_heavy_lod1":"mixed iron/steel/wood","augustan_scutum_lod1":"other",
 "augustan_scutum_bossa_lod1":"iron/steel"}

def current_class(name):
    if name in {"3c_niederbieber_helmet","lorica_hamata_A","roman_gladius_lod1","roman_pilum_heavy_lod1","augustan_scutum_bossa_lod1"}: return "conductor"
    return "dielectric"
def diagnostic_class(name):
    expected=EXPECTED.get(name,"other")
    if expected.startswith("mixed"): return "cloth" if name=="3c_aurelian_pants" else "iron/steel"
    return expected
def world_bounds(obj):
    points=[obj.matrix_world@Vector(corner) for corner in obj.bound_box]
    return {"min":[round(min(p[i] for p in points),4) for i in range(3)],"max":[round(max(p[i] for p in points),4) for i in range(3)]}
def make_material(cls):
    mat=bpy.data.materials.get("AUDIT_"+cls) or bpy.data.materials.new("AUDIT_"+cls); mat.diffuse_color=COLORS[cls]; mat.use_nodes=True
    nodes=mat.node_tree.nodes; nodes.clear(); out=nodes.new("ShaderNodeOutputMaterial"); bsdf=nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value=COLORS[cls]; bsdf.inputs["Roughness"].default_value=.75; bsdf.inputs["Metallic"].default_value=0
    mat.node_tree.links.new(bsdf.outputs["BSDF"],out.inputs["Surface"]); return mat
def camera(scene,azimuth):
    cam=next((o for o in scene.objects if o.type=="CAMERA"),None); scene.camera=cam; cam.data.type="ORTHO"; cam.data.ortho_scale=8.5
    az=math.radians(azimuth); el=math.radians(30); target=Vector((0,0,0)); cam.location=target+Vector((12*math.cos(el)*math.cos(az),12*math.cos(el)*math.sin(az),12*math.sin(el)))
    cam.rotation_euler=(target-cam.location).to_track_quat("-Z","Y").to_euler()
def run():
    OUT.mkdir(parents=True,exist_ok=True); bpy.ops.wm.open_mainfile(filepath=str(BLEND.resolve())); scene=bpy.context.scene; scene.frame_set(0)
    rows=[]; audit_mats={cls:make_material(cls) for cls in COLORS}
    for obj in sorted((o for o in scene.objects if o.type=="MESH" and not o.hide_render),key=lambda o:o.name):
        original=[slot.material.name if slot.material else None for slot in obj.material_slots]
        rows.append({"object":obj.name,"materials":original,"world_bounds":world_bounds(obj),
                     "classes":[{"material":name,"current_v4_class":current_class(name),"expected_class":EXPECTED.get(name,"other"),"diagnostic_class":diagnostic_class(name)} for name in original if name]})
        for slot in obj.material_slots:
            if slot.material: slot.material=audit_mats[diagnostic_class(slot.material.name)]
    # Neutral, shadowless diagnostic illumination; classification colors only.
    for obj in list(scene.objects):
        if obj.type=="LIGHT": bpy.data.objects.remove(obj,do_unlink=True)
    scene.world.use_nodes=True; bg=scene.world.node_tree.nodes.get("Background"); bg.inputs["Color"].default_value=(.12,.12,.12,1); bg.inputs["Strength"].default_value=.8
    scene.render.engine="BLENDER_EEVEE"; scene.render.resolution_x=800; scene.render.resolution_y=800; scene.render.resolution_percentage=100; scene.render.film_transparent=False
    scene.render.image_settings.file_format="PNG"; scene.render.image_settings.color_mode="RGBA"; scene.view_settings.view_transform="Standard"; scene.view_settings.look="None"; scene.view_settings.exposure=0; scene.view_settings.gamma=1
    renders=[]
    for az in (45,135,225,315):
        camera(scene,az); path=OUT/f"material-classes-{az:03d}.png"; scene.render.filepath=str(path.resolve()); bpy.ops.render.render(write_still=True); renders.append(str(path))
    report={"format":"rome2aoe2.material-class-audit","version":1,"source_blend":str(BLEND),"diagnostic_only":True,"blend_saved":False,
            "colors":{k:list(v) for k,v in COLORS.items()},"expected_material_classes":EXPECTED,"objects":rows,"renders":renders}
    (OUT/"material-class-audit.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__": run()
