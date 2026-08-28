"""Render actual Rome II RGB Mask texture coverage on calibration geometry."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";OUT=BASE/"tint-masks";OUT.mkdir(parents=True,exist_ok=True)
sys.path.insert(0,str(ROOT/"src"/"blender"));from render_cross_unit_set_a import import_unit,configure_camera,setup_render,CLASS  # noqa:E402
from render_rome2_v4_candidate import CONDUCTORS  # noqa:E402
SET=("hastati","principes","triarii","velites","hoplites","celtic-warriors","eastern-spearmen")
def black(mat):
 mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();o=n.new("ShaderNodeOutputMaterial");e=n.new("ShaderNodeEmission");e.inputs["Color"].default_value=(0,0,0,1);mat.node_tree.links.new(e.outputs["Emission"],o.inputs["Surface"])
def maskmat(mat,path):
 mat.use_nodes=True;n=mat.node_tree.nodes;n.clear();o=n.new("ShaderNodeOutputMaterial");e=n.new("ShaderNodeEmission");t=n.new("ShaderNodeTexImage");t.image=bpy.data.images.load(str(path),check_existing=True);t.image.colorspace_settings.name="Non-Color";mat.node_tree.links.new(t.outputs["Color"],e.inputs["Color"]);mat.node_tree.links.new(e.outputs["Emission"],o.inputs["Surface"])
def set_a(slug):
 root,_=import_unit(slug);configure_camera(bpy.context.scene,45,30,8.5,12);doc=json.loads((root/"texture-manifest.json").read_text());maps={m["material_name"]:next((root/"textures"/Path(t["extracted_path"]) for t in m["textures"] if t["semantic"]=="Mask" and t["status"]=="resolved"),None) for m in doc["materials"]}
 valid=set(maps)
 for obj in bpy.data.objects:
  if obj.type=="MESH" and not any(slot.material and slot.material.name.split(".")[0] in valid for slot in obj.material_slots):obj.hide_render=True
 for mat in bpy.data.materials:
  key=mat.name.split(".")[0];cls=CLASS.get(key,"unknown");path=maps.get(key)
  if path and cls not in ("skin","bronze","iron/steel","leather","hair/fur"):maskmat(mat,path)
  else:black(mat)
 setup_render(OUT/f"{slug}-mask-rgb.png")
def praetorian():
 blend=ROOT/"build"/"local-integration"/"rome2"/"textured"/"sws_stand_textured.blend";bpy.ops.wm.open_mainfile(filepath=str(blend));bpy.context.scene.frame_set(0);configure_camera(bpy.context.scene,45,30,8.5,12)
 for mat in bpy.data.materials:
  key=mat.name;excluded=key in CONDUCTORS or any(x in key.lower() for x in ("skin","head","body","eyes","teeth","horsehair"));candidate=None
  if mat.node_tree:
   candidate=next((n.image for n in mat.node_tree.nodes if n.bl_idname=="ShaderNodeTexImage" and n.image and "mask" in (n.label or n.name).lower() and "skin" not in (n.label or n.name).lower()),None)
  if candidate and not excluded:maskmat(mat,Path(bpy.path.abspath(candidate.filepath)))
  else:black(mat)
 setup_render(OUT/"praetorian-mask-rgb.png")
def main():
 for slug in SET:bpy.ops.wm.read_factory_settings(use_empty=True);set_a(slug)
 praetorian()
if __name__=="__main__":main()
