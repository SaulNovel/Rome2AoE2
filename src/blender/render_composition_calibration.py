"""Render bounded Hastati/Eastern diagnostics and three Praetorian compositions."""
import json,sys
from pathlib import Path
import bpy
from mathutils import Matrix
ROOT=Path(__file__).resolve().parents[2];CU=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";BASE=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration";OUT=BASE/"renders";OUT.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(ROOT/"src"/"blender"))
from render_cross_unit_set_a import import_unit,configure_camera,setup_render,lighting
from render_material_reconstruction_v1 import reconstruct,TEST
from import_animation_clip import create_action,AXIS_INV
ANIM=json.loads((ROOT/"build"/"local-integration"/"rome2"/"animation-v5"/"full"/"sws_stand.animation.json").read_text());ALT=json.loads((BASE/"praetorian-slot-assets.json").read_text())
P=[{"id":"P01","armour":"3c_roman_lorica_hamata_cape","helmet":"3c_niederbieber_helmet","shield":"roman_augustan_scutuma"},{"id":"P02","armour":"lorica_segmentata_a","helmet":"3c_niederbieber_helmet_gold","shield":"roman_augustan_scutumb"},{"id":"P03","armour":"3c_roman_lorica_hamata_cape","helmet":"3c_italic_h_helmet","shield":"roman_augustan_scutumc"}]
def render_unit(slug,name,colors=TEST["neutral"]):
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=import_unit(slug);configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,colors,True);lighting("L11");setup_render(OUT/name)
def delete_source(tokens):
 for o in list(bpy.data.objects):
  if o.type=="MESH" and any(t.lower() in o.name.lower() for t in tokens):bpy.data.objects.remove(o,do_unlink=True)
def add_alt(row,primary):
 before=set(bpy.data.objects);bpy.ops.import_scene.gltf(filepath=row["gltf"]);added=[o for o in bpy.data.objects if o not in before]
 if row["slot"]!="shield":
  for a in added:
   if a.type=="ARMATURE":create_action(a,ANIM,60,1.0)
 else:
  w=bpy.data.objects.new(row["name"]+"_attachment",None);bpy.context.scene.collection.objects.link(w);c=w.constraints.new("CHILD_OF");c.target=primary;c.subtarget="bn_weapon_03";c.inverse_matrix=Matrix.Identity(4);w.matrix_basis=AXIS_INV
  for o in added:
   if o.type=="MESH":o.parent=w;o.matrix_parent_inverse=Matrix.Identity(4);o.matrix_basis=Matrix.Identity(4)
def render_p(c):
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=import_unit("praetorian");primary=next(o for o in bpy.data.objects if o.type=="ARMATURE");delete_source(["3c_roman_lorica_hamata_cape","lorica_segmentata_a","3c_niederbieber_helmet","3c_italic_h_helmet","roman_augustan_scutum"])
 for slot in ("armour","helmet","shield"):add_alt(next(x for x in ALT["assets"] if x["slot"]==slot and x["name"]==c[slot]),primary)
 configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,TEST["neutral"],True);reconstruct(BASE,TEST["neutral"],True);lighting("L11");setup_render(OUT/f"{c['id']}.png")
def main():
 for key,col in (("H01",TEST["neutral"]),("H02",TEST["R"]),("H03",TEST["RGB"])):render_unit("hastati",f"{key}.png",col)
 for key,col in (("E01",TEST["neutral"]),("E02",TEST["R"]),("E03",TEST["G"]),("E04",TEST["B"]),("E05",TEST["RGB"])):render_unit("eastern-spearmen",f"{key}.png",col)
 for c in P:render_p(c)
 (BASE/"composition-candidates.json").write_text(json.dumps({"format":"rome2aoe2.composition-candidates","version":1,"fixed_light":"L11","hastati":[{"id":"H01","description":"source reconstruction neutral"},{"id":"H02","description":"source reconstruction R test tint"},{"id":"H03","description":"source reconstruction RGB test tint"}],"eastern":[{"id":"E01","description":"neutral"},{"id":"E02","description":"R only"},{"id":"E03","description":"G only"},{"id":"E04","description":"B only"},{"id":"E05","description":"RGB independent"}],"praetorian":P},indent=2)+"\n")
if __name__=="__main__":main()
