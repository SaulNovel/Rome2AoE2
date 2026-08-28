"""Render fixed-L11 Hastati masters and an AA semantic material-ID image.

The ID render is an emission pass derived from resolved Blender material slots.
It is equivalent to a material matte pass: no final-RGB classification is used.
"""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src/blender"))
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
OUT=ROOT/"build/local-integration/rome2/material-aware-finishing/inputs";EFFECTIVE=ROOT/"build/local-integration/rome2/runtime-resolution/effective/hastati/effective-unit.json"
COLORS={"cloth":(1,0,0,1),"skin":(0,1,0,1),"bronze":(0,0,1,1),"iron/steel":(1,1,0,1),"shield body":(1,0,1,1),"shield metal":(0,1,1,1),"leather":(1,.25,0,1),"wood":(.25,1,0,1),"other":(.25,.25,.25,1)}
CLASS={"E3_tunic":"cloth","E3_tunic_flipped":"cloth","roman_1_head":"skin","roman_body1":"skin","italian_square_muscled_cuirass_":"bronze","roman_montefortino":"bronze","roman_1_sandals":"leather","roman_early_scutum_lod1":"shield body"}
MIXED={"roman_early_scutum_lod1":"painted body + metal boss/rim share one material; assigned to shield body, shield metal remains unresolved","roman_gladius_lod1":"blade + grip/scabbard share one material","roman_pilum_light_lod1":"head + shaft share one material"}
def linear(h):
 def f(v):v=v/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
 return tuple(f(int(h[i:i+2],16)) for i in (0,2,4))
def render(path,size,exposure=.65):
 s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=s.render.resolution_y=size;s.render.resolution_percentage=100;s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.view_settings.view_transform="Standard";s.view_settings.look="None";s.view_settings.exposure=exposure;s.render.filepath=str(path);bpy.ops.render.render(write_still=True)
def id_material(cls):
 name="MASK_"+cls;mat=bpy.data.materials.get(name) or bpy.data.materials.new(name);mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();out=n.new("ShaderNodeOutputMaterial");em=n.new("ShaderNodeEmission");em.inputs["Color"].default_value=COLORS[cls];em.inputs["Strength"].default_value=1;mat.node_tree.links.new(em.outputs["Emission"],out.inputs["Surface"]);return mat
def main():
 OUT.mkdir(parents=True,exist_ok=True);m=json.loads(EFFECTIVE.read_text());c=m["faction_colours"];colors=tuple(linear(c[x]) for x in ("C0","C1","C2"))
 bpy.ops.wm.read_factory_settings(use_empty=True);cu.BASE=ROOT/"build/local-integration/rome2/cross-unit-calibration";root,_=cu.import_unit("hastati");cu.configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,colors,True);cu.lighting("L11")
 for size in (800,1600,3200):render(OUT/f"hastati-master-{size}.png",size)
 rows=[];mats={k:id_material(k) for k in COLORS}
 for obj in (o for o in bpy.context.scene.objects if o.type=="MESH"):
  for slot in obj.material_slots:
   if not slot.material:continue
   original=slot.material.name.split(".")[0];cls=CLASS.get(original,"other");rows.append({"object":obj.name,"material":original,"semantic_class":cls,"mixed_limitation":MIXED.get(original)});slot.material=mats[cls]
 # Raw Standard emission values make the ID palette exact and separable.
 bpy.context.scene.world.color=(0,0,0);render(OUT/"hastati-material-id-3200.png",3200,0)
 report={"format":"rome2aoe2.hastati-finish-inputs","version":1,"source":"resolved Blender material slots","anti_aliasing":"single emission material-ID render at 3200; masks derived as fractional color mattes","colors":{k:list(v) for k,v in COLORS.items()},"assignments":rows,"unsupported_exact_masks":{"shield metal":MIXED["roman_early_scutum_lod1"],"iron/steel":"weapon metal shares materials with non-metal parts","wood":"weapon shafts/grips share materials with metal parts"},"masters":[800,1600,3200],"fixed":{"lighting":"L11","camera":"unchanged","materials":"reconstruction v1","composition":"deterministic representative"}}
 (OUT/"hastati-finish-inputs.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
