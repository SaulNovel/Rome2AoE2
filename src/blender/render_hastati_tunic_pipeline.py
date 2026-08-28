"""Render same-geometry raw and Rome-tinted E3_tunic emission stages."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src/blender"))
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import maps,tex,exact_tint
OUT=ROOT/"build/local-integration/rome2/tunic-semantic-color/inputs";EFF=ROOT/"build/local-integration/rome2/runtime-resolution/effective/hastati/effective-unit.json"
def linear(h):
 def f(v):v=v/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
 return tuple(f(int(h[i:i+2],16)) for i in (0,2,4))
def build(root,mode,colors):
 mm=maps(root)
 for mat in bpy.data.materials:
  key=mat.name.split(".")[0];mat.use_nodes=True;n=mat.node_tree.nodes;l=mat.node_tree.links;n.clear();o=n.new("ShaderNodeOutputMaterial");e=n.new("ShaderNodeEmission");l.new(e.outputs["Emission"],o.inputs["Surface"])
  if key not in ("E3_tunic","E3_tunic_flipped"):e.inputs["Color"].default_value=(0,0,0,1);continue
  t=mm[key];di=tex(n,t["Diffuse"],"raw diffuse");base=di.outputs["Color"]
  if mode=="mask":base=tex(n,t["Mask"],"Rome faction RGB",True).outputs["Color"]
  elif mode=="tinted":
   mk=tex(n,t["Mask"],"Rome faction RGB",True);base=exact_tint(n,l,base,mk,colors)
  l.new(base,e.inputs["Color"])
def render(name,mode,colors):
 bpy.ops.wm.read_factory_settings(use_empty=True);cu.BASE=ROOT/"build/local-integration/rome2/cross-unit-calibration";root,_=cu.import_unit("hastati");cu.configure_camera(bpy.context.scene,45,30,8.5,12);build(root,mode,colors);s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=s.render.resolution_y=3200;s.render.resolution_percentage=100;s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.view_settings.view_transform="Raw" if mode=="mask" else "Standard";s.view_settings.look="None";s.view_settings.exposure=0;s.render.filepath=str(OUT/name);bpy.ops.render.render(write_still=True)
def main():
 OUT.mkdir(parents=True,exist_ok=True);m=json.loads(EFF.read_text());c=m["faction_colours"];colors=tuple(linear(c[x]) for x in ("C0","C1","C2"));render("tunic-raw-diffuse.png","raw",colors);render("tunic-rome-tinted.png","tinted",colors);render("tunic-mask-rgb.png","mask",colors)
 (OUT/"trace.json").write_text(json.dumps({"materials":["E3_tunic","E3_tunic_flipped"],"model":"variantmeshes/_variantmodels/man/tunics/e3_tunic.rigid_model_v2","diffuse":"greektunicvest_diffuse.dds","mask":"greektunicvest_mask.dds","selected_vmd_index":0,"channel_remap":"identity: R->C0, G->C1, B->C2","colors":{"C0":c["C0"],"C1":c["C1"],"C2":c["C2"],"source":c["source"]},"equation":"D0=lerp(D,D*C0,R); D1=lerp(D0,D0*C1,G); D2=lerp(D1,D1*C2,B)"},indent=2)+"\n")
if __name__=="__main__":main()
