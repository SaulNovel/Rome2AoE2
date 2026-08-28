"""Bounded Rome-II-daylight bronze study over the frozen P5 material state."""
import json, math, sys
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src/blender"))
import render_hastati_aoe_art_direction as ad
import render_hastati_stock_punch as punch
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
from render_lighting_sweep import clear_lights,add_sun

BASE=ROOT/"build/local-integration/rome2/hastati-rome2-daylight-bronze"
MASTER=BASE/"masters"; FACINGS=BASE/"facing-diagnostic"
MASKS=BASE/"facing-bronze-masks"
MASTER.mkdir(parents=True,exist_ok=True);FACINGS.mkdir(parents=True,exist_ok=True);MASKS.mkdir(parents=True,exist_ok=True)

# BR0 is the exact P5 render-side source. BR1-BR6 deliberately form a small,
# monotonic daylight/material family; finishing remains a separate AoE stage.
DEFS={
 "BR0":{"name":"Frozen P5 source","lighting":"A9","factor":(.54,.40,.25),"roughness":.58,"warm":.014},
 "BR1":{"name":"Rome preview daylight control","lighting":"R2DAY","factor":(.54,.40,.25),"roughness":.58,"warm":0},
 "BR2":{"name":"Daylight rich base","lighting":"R2DAY","factor":(.48,.34,.20),"roughness":.58,"warm":0},
 "BR3":{"name":"Daylight warm midtone","lighting":"R2DAY","factor":(.46,.32,.19),"roughness":.56,"warm":.010},
 "BR4":{"name":"Daylight controlled specular","lighting":"R2DAY","factor":(.44,.30,.17),"roughness":.50,"warm":.012},
 "BR5":{"name":"Daylight AoE-readable","lighting":"R2DAY_PUNCH","factor":(.44,.30,.17),"roughness":.52,"warm":.014},
 "BR6":{"name":"Bounded strongest bronze","lighting":"R2DAY_PUNCH","factor":(.41,.27,.15),"roughness":.46,"warm":.016}
}

def daylight(punchy=False):
 s=bpy.context.scene;clear_lights(s)
 # Official preview evidence: warm sun at azimuth 215.4/elevation 30.6 and a
 # bright directional ambient cube. Blender approximation: directional sun,
 # cool upper hemisphere, restrained warm ground hemisphere.
 add_sun(s,{"strength":4.20 if punchy else 3.20,"azimuth":125.0,"elevation":30.6,"angular_size":1.0,"color":(1.0,.91,.88)})
 w=s.world or bpy.data.worlds.new("Rome II daylight world");s.world=w;w.use_nodes=True
 n=w.node_tree.nodes;l=w.node_tree.links;n.clear();o=n.new("ShaderNodeOutputWorld");bg=n.new("ShaderNodeBackground")
 tc=n.new("ShaderNodeTexCoord");sep=n.new("ShaderNodeSeparateXYZ");l.new(tc.outputs["Normal"],sep.inputs["Vector"])
 ramp=n.new("ShaderNodeValToRGB");ramp.color_ramp.elements[0].position=.18;ramp.color_ramp.elements[0].color=(.18,.13,.08,1)
 ramp.color_ramp.elements[1].position=.70;ramp.color_ramp.elements[1].color=(.34,.49,.72,1)
 l.new(sep.outputs["Z"],ramp.inputs["Fac"]);l.new(ramp.outputs["Color"],bg.inputs["Color"]);bg.inputs["Strength"].default_value=.72 if punchy else .82;l.new(bg.outputs["Background"],o.inputs["Surface"])

def tune_bronze(d):
 punch.tune({"cloth":True,"skin":True,"shield":True,"leather":True})
 for mat in bpy.data.materials:
  if mat.name.split('.')[0] not in ad.BRONZE:continue
  b=ad.bsdf(mat);ad.multiply_base(mat,d["factor"]);b.inputs["Metallic"].default_value=1
  sock=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(sock.links)];sock.default_value=d["roughness"]
  if d["warm"]:ad.emission_fill(mat,d["warm"],True)

def setup(cid,azimuth,resolution,path):
 d=DEFS[cid];bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit("hastati")
 cu.configure_camera(bpy.context.scene,azimuth,30,8.5,12);reconstruct(root,ad.COLORS,True)
 punch.rig(punch.LIGHTS["A9"]) if d["lighting"]=="A9" else daylight(d["lighting"]=="R2DAY_PUNCH")
 tune_bronze(d);s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=s.render.resolution_y=resolution;s.render.resolution_percentage=100
 s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.render.image_settings.color_depth="8"
 s.display_settings.display_device="sRGB";s.view_settings.view_transform="Standard";s.view_settings.look="None";s.view_settings.exposure=.65;s.view_settings.gamma=1;s.render.filepath=str(path.resolve());bpy.ops.render.render(write_still=True)

def bronze_mask(path):
 for mat in bpy.data.materials:
  key=mat.name.split('.')[0];mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear();o=n.new("ShaderNodeOutputMaterial");e=n.new("ShaderNodeEmission")
  e.inputs["Color"].default_value=(1,1,1,1) if key in ad.BRONZE else (0,0,0,1);e.inputs["Strength"].default_value=1;l.new(e.outputs["Emission"],o.inputs["Surface"])
 s=bpy.context.scene;s.view_settings.exposure=0;s.render.filepath=str(path.resolve());bpy.ops.render.render(write_still=True)

def main():
 m=json.loads(ad.EFFECTIVE.read_text());ad.COLORS=tuple(ad.linear(m["faction_colours"][x]) for x in ("C0","C1","C2"))
 for i in range(16):
  setup("BR5",45+22.5*i,800,FACINGS/f"facet_{i:02d}.png");bronze_mask(MASKS/f"facet_{i:02d}.png")
 for cid in DEFS:setup(cid,45,3200,MASTER/f"{cid}.png")
 report={"format":"rome2aoe2.rome2-daylight-bronze-render","version":1,"definitions":DEFS,"fixed":{"composition":"runtime-resolved Hastati representative","pose_frame":1,"camera_elevation":30,"ortho_scale":8.5,"master_resolution":3200,"scale_stage":"R133 downstream"},"evidence":{"official_preview_environment":"assembly_kit/editor_working_data/Weather/variant_editor_day.environment","official_preview_constants":{"sun_azimuth":215.4,"sun_elevation":30.6,"sun_colour_scale":1.8,"ambient_cube":True,"ambient_scale":2.5,"hdr_white_points":[3,25]},"official_shader":"assembly_kit/max_exporter/max_shader/ca_shader.fx","proven_shader_behaviour":["directional diffuse and specular","hemisphere ambient diffuse","environment cubemap specular","RGB specular colour","smoothness/reflectivity material inputs"],"inference":"Procedural Blender hemisphere and energy mapping approximate, but do not reproduce, the official preview or battlefield renderer."}}
 (BASE/"rome2-daylight-render-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
