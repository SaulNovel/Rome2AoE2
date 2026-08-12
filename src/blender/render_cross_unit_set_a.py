"""Render Set A material-class diagnostics and common L06/L10/L11 proofs."""
import json, math, sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
ANIM=ROOT/"build"/"local-integration"/"rome2"/"animation-v5"/"full"/"sws_stand.animation.json"
sys.path.insert(0,str(ROOT/"src"/"blender"))
from import_animation_clip import create_action, AXIS_INV, rows_matrix  # noqa:E402
from render_lighting_sweep import CANDIDATES, clear_lights, set_world, add_sun, add_area  # noqa:E402
from render_rome2_v4_candidate import configure_camera  # noqa:E402

UNITS=("hastati","principes","triarii","velites","hoplites","celtic-warriors","eastern-spearmen")
LABELS={"hastati":"Hastati","principes":"Principes","triarii":"Triarii","velites":"Velites","hoplites":"Hoplites","celtic-warriors":"Celtic Warriors","eastern-spearmen":"Eastern Spearmen"}
COLORS={"skin":(1,.16,.28,1),"bronze":(1,.65,.02,1),"iron/steel":(.03,.28,1,1),"wood":(1,.32,.02,1),"cloth":(.05,.65,.12,1),"leather":(.32,.09,.025,1),"hair/fur":(.65,.1,.75,1),"other":(.25,.25,.25,1),"unknown":(1,0,1,1)}
CLASS={
 "roman_body1":"skin","roman_1_head":"skin","roman_1_sandals":"leather","roman_1_eyes_teeth":"other","barbarian_base_game":"skin","generic_eyes_tongue":"other",
 "linothorax_basic_01":"cloth","greaves_variations1":"bronze","Hellenic_Thracian_1":"bronze","hellenic_shield_hoplon_lod1":"unknown","hellenic_tunic_cut":"cloth",
 "eastern_beard_01a":"hair/fur","eastern_cap":"cloth","eastern_wooden_tower_shield_1_l":"wood","eastern_trousers_cut_01":"cloth","eastern_basic_tunic_01":"cloth",
 "E3_tunic":"cloth","E3_tunic_flipped":"cloth","celtic_checker_trousers":"cloth","celtic_cloak_a":"cloth","pin1_a":"bronze",
 "barbarian_beard_02f_brown":"hair/fur","barbarain_hair_06d_brown":"hair/fur","wolf_pelt_3_no_helmet":"hair/fur","black_feather_03_lod1":"hair/fur","phyrgian_crest_1_white_lod1":"hair/fur","tall_ridge_crest_1_white_lod1":"hair/fur","white_feather_01_lod1":"hair/fur",
 "lorica_hamata_A":"iron/steel","roman_belt_01":"leather","italian_square_muscled_cuirass_":"bronze","roman_montefortino":"bronze","hellenic_konos":"bronze","roman_italio_corinthian_1":"bronze","roman_montefortino_b_1":"bronze","Hellenic_elite_greave":"bronze","Celt_montefortino":"bronze",
 "briton_torc_c_bronze":"unknown","celt_sword_bladea_lod1":"iron/steel","celt_sword_hilta_lod1":"leather",
 "roman_early_scutum_lod1":"unknown","roman_cavalry_shield_Lod1":"unknown","celtic_oval_shield_a_lod1":"unknown",
 "roman_gladius_lod1":"unknown","roman_pilum_light_lod1":"unknown","Hellenic_javelin_Leaf_tip_01_lo":"unknown","hellenic_spear_01_lod1":"unknown",
}
MIXED={"roman_early_scutum_lod1":"painted wood body + metal boss/rim in one material","roman_cavalry_shield_Lod1":"painted wood/body + fittings in one material","celtic_oval_shield_a_lod1":"painted wood/body + fittings in one material","roman_gladius_lod1":"steel blade + non-metal grip/scabbard in one material","roman_pilum_light_lod1":"iron head + wooden shaft in one material","Hellenic_javelin_Leaf_tip_01_lo":"metal head + wooden shaft in one material","hellenic_spear_01_lod1":"metal head + wooden shaft in one material"}

def reset(): bpy.ops.wm.read_factory_settings(use_empty=True)
def import_unit(slug):
    root=BASE/"units"/slug; doc=json.loads((root/"assets.json").read_text()); animation=json.loads(ANIM.read_text())
    armatures=[]; rigid=[]; records=[]
    for e in doc["exports"]:
        before=set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=e["gltf"])
        added=[o for o in bpy.data.objects if o not in before]
        for o in added: o.name=f"{slug}__{Path(e['source_model']).stem}__{o.name}"
        newarms=[o for o in added if o.type=="ARMATURE"]
        if e["skinned"]:
            for arm in newarms: create_action(arm,animation,60,1.0); armatures.append(arm)
        else: rigid.append((e,[o for o in added if o.type=="MESH"]))
        records.append((e,added))
    if not armatures: raise RuntimeError(f"{slug}: no armature")
    primary=armatures[0]
    bone_map={"weapon_01":"bn_weapon_01","weapon_02":"bn_weapon_02","weapon_03":"bn_weapon_03","weapon_05":"bn_weapon_05"}
    for e,meshes in rigid:
        attach=next((o.get("attach_point") for o in e["origins"] if o.get("attach_point")),None)
        if attach in bone_map:
            wrapper=bpy.data.objects.new(f"{slug}_{attach}_attachment",None); bpy.context.scene.collection.objects.link(wrapper)
            c=wrapper.constraints.new("CHILD_OF"); c.target=primary;c.subtarget=bone_map[attach];c.inverse_matrix=Matrix.Identity(4);wrapper.matrix_basis=AXIS_INV
            for mesh in meshes: mesh.parent=wrapper;mesh.matrix_parent_inverse=Matrix.Identity(4);mesh.matrix_basis=Matrix.Identity(4)
        elif attach and attach.startswith("crest"):
            gltf=json.loads(Path(e["gltf"]).read_text()); # crest itself has no placement; helmet metadata owns it
            helmet=next((x for x in doc["exports"] if "helmet" in x["source_model"].lower()),None)
            hdoc=json.loads(Path(helmet["gltf"]).read_text()) if helmet else {}
            at=next((a for m in hdoc.get("materials",[]) for a in m.get("extras",{}).get("rome2aoe2",{}).get("attachments",[]) if a["name"]==attach),None)
            wrapper=bpy.data.objects.new(f"{slug}_{attach}_attachment",None);bpy.context.scene.collection.objects.link(wrapper)
            c=wrapper.constraints.new("CHILD_OF");c.target=primary;c.subtarget="bn_head";c.inverse_matrix=Matrix.Identity(4)
            attachment_local=Matrix((at["matrix"][0],at["matrix"][1],at["matrix"][2],(0,0,0,1))) if at else Matrix.Identity(4)
            wrapper.matrix_basis=attachment_local @ AXIS_INV
            for mesh in meshes: mesh.parent=wrapper;mesh.matrix_parent_inverse=Matrix.Identity(4);mesh.matrix_basis=Matrix.Identity(4)
    bpy.context.scene.frame_set(1); return root,records

def texture_map(root):
    doc=json.loads((root/"texture-manifest.json").read_text()); return {m["material_name"]:{t["semantic"]:root/"textures"/Path(t["extracted_path"]) for t in m["textures"] if t["status"]=="resolved"} for m in doc["materials"]}
def img_node(nodes,links,path,label,noncolor=False):
    n=nodes.new("ShaderNodeTexImage");n.image=bpy.data.images.load(str(path),check_existing=True);n.label=label
    if noncolor:n.image.colorspace_settings.name="Non-Color"
    return n
def beauty_materials(root):
    maps=texture_map(root)
    for mat in bpy.data.materials:
        key=mat.name.split(".")[0] if mat.name not in maps else mat.name; tex=maps.get(key,{})
        mat.use_nodes=True;nodes=mat.node_tree.nodes;links=mat.node_tree.links;nodes.clear();out=nodes.new("ShaderNodeOutputMaterial");bs=nodes.new("ShaderNodeBsdfPrincipled");links.new(bs.outputs["BSDF"],out.inputs["Surface"])
        cls=CLASS.get(key,"unknown"); bs.inputs["Metallic"].default_value=1.0 if cls in ("bronze","iron/steel") else 0.0
        if "Diffuse" in tex:
            di=img_node(nodes,links,tex["Diffuse"],"diffuse");links.new(di.outputs["Color"],bs.inputs["Base Color"]);links.new(di.outputs["Alpha"],bs.inputs["Alpha"])
        if cls in ("bronze","iron/steel") and "Specular" in tex:
            sp=img_node(nodes,links,tex["Specular"],"specular_F0");links.new(sp.outputs["Color"],bs.inputs["Base Color"])
        if "GlossMap" in tex:
            gl=img_node(nodes,links,tex["GlossMap"],"gloss",True);sep=nodes.new("ShaderNodeSeparateColor");links.new(gl.outputs["Color"],sep.inputs["Color"]);sq=nodes.new("ShaderNodeMath");sq.operation="MULTIPLY";links.new(sep.outputs["Red"],sq.inputs[0]);links.new(sep.outputs["Red"],sq.inputs[1]);sub=nodes.new("ShaderNodeMath");sub.operation="SUBTRACT";sub.inputs[0].default_value=1;links.new(sq.outputs[0],sub.inputs[1]);links.new(sub.outputs[0],bs.inputs["Roughness"])
        else: bs.inputs["Roughness"].default_value=.72 if cls not in ("bronze","iron/steel") else .45
        if cls=="bronze": bs.inputs["Base Color"].default_value=(.55,.22,.045,1)
        mat.diffuse_color=COLORS.get(cls,COLORS["unknown"])
def false_materials():
    for mat in bpy.data.materials:
        key=mat.name.split(".")[0];cls=CLASS.get(key,"unknown");mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();out=n.new("ShaderNodeOutputMaterial");em=n.new("ShaderNodeEmission");em.inputs["Color"].default_value=COLORS[cls];em.inputs["Strength"].default_value=1;mat.node_tree.links.new(em.outputs["Emission"],out.inputs["Surface"])
def setup_render(path,samples=32):
    s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=800;s.render.resolution_y=800;s.render.resolution_percentage=100;s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.view_settings.view_transform="Standard";s.view_settings.look="None";s.view_settings.exposure=.65;s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
def lighting(cid):
    s=bpy.context.scene;c=next(x for x in CANDIDATES if x["id"]==cid);clear_lights(s);set_world(s,c["world"]);add_sun(s,c["sun"])
    for a in c["areas"]:add_area(s,a)
def run():
    out=BASE/"renders-set-a";out.mkdir(parents=True,exist_ok=True);audit=[]
    for slug in UNITS:
        reset();root,records=import_unit(slug);configure_camera(bpy.context.scene,45,30,8.5,12);beauty_materials(root)
        audit.append({"unit":LABELS[slug],"materials":[{"material":m.name.split('.')[0],"class":CLASS.get(m.name.split('.')[0],"unknown"),"mixed_limitation":MIXED.get(m.name.split('.')[0])} for m in bpy.data.materials]})
        false_materials();setup_render(out/f"{slug}-material-classes.png")
        for cid in ("L06","L10","L11"):
            reset();root,_=import_unit(slug);configure_camera(bpy.context.scene,45,30,8.5,12);beauty_materials(root);lighting(cid);setup_render(out/f"{slug}-{cid}.png")
    (BASE/"material-classification-set-a.json").write_text(json.dumps({"format":"rome2aoe2.material-classification-set-a","version":1,"colors":COLORS,"mixed_regions":MIXED,"units":audit},indent=2,sort_keys=True)+"\n")
if __name__=="__main__":run()
