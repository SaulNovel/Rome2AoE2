"""Render the bounded L11-derived presentation candidates for Hastati."""
import json,sys
from pathlib import Path
import bpy

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/"src/blender"))
import render_cross_unit_set_a as cu
from render_material_reconstruction_v1 import reconstruct
from render_lighting_sweep import add_area, area

OUT=ROOT/"build/local-integration/rome2/aoe-style-calibration/lighting-highres"
EFFECTIVE=ROOT/"build/local-integration/rome2/runtime-resolution/effective/hastati/effective-unit.json"
DEFS={
 "D01":{"name":"L11 Control","areas":[]},
 "D02":{"name":"Camera Soft Fill","areas":[area("style_camera_fill",(6,6,5),420,6.0)]},
 "D03":{"name":"Upper Front Softbox","areas":[area("style_upper_softbox",(4.5,4.5,8),650,6.5)]},
 "D04":{"name":"Restrained Rim","areas":[area("style_rim",(-4,-4,6),240,3.5,(1.0,.84,.65))]},
 "D05":{"name":"Fill And Rim","areas":[area("style_camera_fill",(6,6,5),330,6.0),area("style_rim",(-4,-4,6),180,3.5,(1.0,.84,.65))]},
}
def linear(h):
 def f(x):x/=255;return x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4
 return tuple(f(int(h[i:i+2],16)) for i in (0,2,4))
def main():
 OUT.mkdir(parents=True,exist_ok=True); m=json.loads(EFFECTIVE.read_text());colors=tuple(linear(m["faction_colours"][x]) for x in ("C0","C1","C2"))
 for cid,d in DEFS.items():
  bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit("hastati");cu.configure_camera(bpy.context.scene,45,30,8.5,12);reconstruct(root,colors,True);cu.lighting("L11")
  for a in d["areas"]:add_area(bpy.context.scene,a)
  cu.setup_render(OUT/f"{cid}.png",64)
 (OUT.parent/"lighting-presentation-definitions.json").write_text(json.dumps(DEFS,indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
