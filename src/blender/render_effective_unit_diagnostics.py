"""Render DB-resolved unit identities with fixed L11 and real faction colours.

Slot and decal choices remain deterministic representatives where the engine's
per-soldier seed is unknown; the accompanying effective manifests say so.
"""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src"/"blender"))
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
OUT=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"/"renders";OUT.mkdir(parents=True,exist_ok=True)
EFFECTIVE=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"/"effective"
def linear(hex_value):
 def f(v):v=v/255;return v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4
 return tuple(f(int(hex_value[i:i+2],16)) for i in (0,2,4))
def render(key,slug,base):
 m=json.loads((EFFECTIVE/key/"effective-unit.json").read_text());c=m["faction_colours"];colors=tuple(linear(c[x]) for x in ("C0","C1","C2"))
 bpy.ops.wm.read_factory_settings(use_empty=True);cu.BASE=base;root,_=cu.import_unit(slug);cu.configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,colors,True);cu.lighting("L11");cu.setup_render(OUT/f"{key}-runtime-resolved-representative.png",64)
def main():
 cross=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";runtime=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"
 render("hastati","hastati",cross);render("eastern-spearman","eastern-spearmen",cross);render("praetorian","praetorian",runtime)
 (OUT/"README.txt").write_text("DB-resolved VMD and faction colours under fixed L11. VMD slot and decal-array choices are representative only where effective-unit.json marks the per-soldier runtime seed unresolved.\n")
if __name__=="__main__":main()
