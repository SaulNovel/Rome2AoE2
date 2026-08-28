"""Bronze-only render families over the frozen P5-era cloth/general state."""
import json,sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src/blender"))
import render_hastati_aoe_art_direction as ad
import render_hastati_stock_punch as punch
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
OUT=ROOT/"build/local-integration/rome2/hastati-bronze-focus/masters";OUT.mkdir(parents=True,exist_ok=True)
DEFS={
 "A0":{"name":"Frozen P5 bronze control","factor":(.54,.40,.25),"roughness":.58,"warm":.014},
 "A1":{"name":"Slightly darker base","factor":(.49,.35,.21),"roughness":.58,"warm":.014},
 "A2":{"name":"Medium darker base","factor":(.43,.29,.17),"roughness":.58,"warm":.014},
 "A3":{"name":"Dark base mild warm highlight","factor":(.43,.29,.17),"roughness":.56,"warm":.021},
 "A4":{"name":"Dark base stronger separation","factor":(.43,.29,.17),"roughness":.50,"warm":.024},
 "B0":{"name":"Highlight control","factor":(.54,.40,.25),"roughness":.58,"warm":.014},
 "B1":{"name":"Slightly warmer highlight","factor":(.54,.40,.25),"roughness":.58,"warm":.020},
 "B2":{"name":"Warm stronger highlight","factor":(.54,.40,.25),"roughness":.54,"warm":.027},
 "B3":{"name":"Warm compressed broad highlight","factor":(.54,.40,.25),"roughness":.66,"warm":.030},
 "B4":{"name":"Bounded specular accent","factor":(.54,.40,.25),"roughness":.46,"warm":.022},
 "C0":{"name":"Specular control","factor":(.54,.40,.25),"roughness":.58,"warm":.014},
 "C1":{"name":"Increased bronze specular","factor":(.52,.38,.23),"roughness":.50,"warm":.020},
 "C2":{"name":"Strong specular restrained base","factor":(.49,.34,.20),"roughness":.44,"warm":.018},
 "C3":{"name":"Bronze micro-contrast source","factor":(.52,.37,.22),"roughness":.54,"warm":.020,"post":"micro"},
 "C4":{"name":"Specular plus local contrast source","factor":(.49,.34,.20),"roughness":.48,"warm":.023,"post":"local"},
 "C5":{"name":"Specular plus boundary source","factor":(.49,.34,.20),"roughness":.48,"warm":.023,"post":"boundary"},
 "D0":{"name":"Combined control","factor":(.54,.40,.25),"roughness":.58,"warm":.014},
 "D1":{"name":"Dark plus warm broad","factor":(.44,.30,.17),"roughness":.57,"warm":.027},
 "D2":{"name":"Dark warm specular","factor":(.43,.29,.16),"roughness":.50,"warm":.025},
 "D3":{"name":"Heroic bronze accent","factor":(.46,.31,.17),"roughness":.46,"warm":.029},
 "D4":{"name":"Balanced stock-punch bronze","factor":(.45,.31,.18),"roughness":.52,"warm":.026},
}
def render(cid,d):
 bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit("hastati");cu.configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,ad.COLORS,True);punch.rig(punch.LIGHTS["A9"]);punch.tune({"cloth":True,"skin":True,"shield":True,"leather":True})
 for mat in bpy.data.materials:
  if mat.name.split('.')[0] not in ad.BRONZE:continue
  b=ad.bsdf(mat);ad.multiply_base(mat,d["factor"]);b.inputs["Metallic"].default_value=1;s=b.inputs["Roughness"];[mat.node_tree.links.remove(x) for x in list(s.links)];s.default_value=d["roughness"];ad.emission_fill(mat,d["warm"],True)
 s=bpy.context.scene;s.render.engine="BLENDER_EEVEE";s.render.resolution_x=s.render.resolution_y=3200;s.render.resolution_percentage=100;s.render.film_transparent=True;s.render.image_settings.file_format="PNG";s.render.image_settings.color_mode="RGBA";s.render.image_settings.color_depth="8";s.display_settings.display_device="sRGB";s.view_settings.view_transform="Standard";s.view_settings.look="None";s.view_settings.exposure=.65;s.view_settings.gamma=1;s.render.filepath=str((OUT/f"{cid}.png").resolve());bpy.ops.render.render(write_still=True);print("rendered",cid,flush=True)
def main():
 m=json.loads(ad.EFFECTIVE.read_text());ad.COLORS=tuple(ad.linear(m["faction_colours"][x]) for x in ("C0","C1","C2"))
 for cid,d in DEFS.items():render(cid,d)
 (OUT.parent/"bronze-render-definitions.json").write_text(json.dumps({"format":"rome2aoe2.hastati-bronze-focus-render","version":1,"baseline":"P5-era A9+B7 with cloth/skin/shield/leather frozen","definitions":DEFS},indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
