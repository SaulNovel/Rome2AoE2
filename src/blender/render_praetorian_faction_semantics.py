"""Apply exact Rome RGB tint equation to the existing Praetorian material proof."""
import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/"build"/"local-integration"/"rome2"/"material-reconstruction"/"renders";sys.path.insert(0,str(ROOT/"src"/"blender"))
from render_material_reconstruction_v1 import TEST,exact_tint
from render_cross_unit_set_a import configure_camera,setup_render,lighting
BLEND=ROOT/"build"/"local-integration"/"rome2"/"textured"/"sws_stand_textured.blend"
def main():
 for key,colors in TEST.items():
  bpy.ops.wm.open_mainfile(filepath=str(BLEND));bpy.context.scene.frame_set(0);configure_camera(bpy.context.scene,45,30,8.5,12)
  for mat in bpy.data.materials:
   if not mat.node_tree:continue
   n=mat.node_tree.nodes;l=mat.node_tree.links;b=next((x for x in n if x.bl_idname=="ShaderNodeBsdfPrincipled"),None);di=next((x for x in n if x.bl_idname=="ShaderNodeTexImage" and x.image and "diffuse" in ((x.label or '')+' '+x.image.name).lower()),None);mk=next((x for x in n if x.bl_idname=="ShaderNodeTexImage" and x.image and "mask" in ((x.label or '')+' '+x.image.name).lower() and "skin" not in ((x.label or '')+' '+x.image.name).lower() and "test_mask" not in x.image.name.lower()),None)
   if b and di and mk and b.inputs.get("Base Color"):
    for link in list(b.inputs["Base Color"].links):l.remove(link)
    l.new(exact_tint(n,l,di.outputs["Color"],mk,colors),b.inputs["Base Color"])
  lighting("L11");setup_render(OUT/f"praetorian-faction-{key}.png")
if __name__=="__main__":main()
