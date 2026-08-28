"""Read cached exact-backend AOVs and isolate scutum specular causality."""
import argparse,json,sys
from pathlib import Path
import bpy,numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"src/blender"),str(ROOT/"src/rome2")]
import assemble_manifest_static as exact
import render_hastati_runtime_parity as runtime
import render_manifest_native_production as production

def args():
 p=argparse.ArgumentParser();p.add_argument("--input-blend",type=Path,required=True);p.add_argument("--aov-root",type=Path,required=True);p.add_argument("--output",type=Path,required=True);return p.parse_args(sys.argv[sys.argv.index("--")+1:])

def main():
 a=args();a.output.mkdir(parents=True,exist_ok=True);bpy.ops.wm.open_mainfile(filepath=str(a.input_blend.resolve()));scene=bpy.context.scene;production.camera(scene);runtime.RESOLUTION=400;runtime.OUT=a.output;runtime.AOV=a.output/"aov";runtime.AOV.mkdir(exist_ok=True)
 report={"format":"rome2aoe2.scutum-material-semantics-audit","version":1,"directions":{}}
 for direction in range(16):
  source=a.aov_root/f"direction-{direction:02d}";arrays={name:np.load(source/f"{name}.npy") for name in exact.exact_materials.RAW_AOVS};family=arrays["family"];shield=(family[...,1]>.5)&(family[...,0]<.5)
  current=runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},readability_fill=.6,metric_masks={"shield":shield},output_name=f"direction-{direction:02d}-current.png",diagnostics=False)
  zero=runtime.shade(scene,{k:v.copy() for k,v in arrays.items()},readability_fill=.6,metric_masks={"shield":shield},zero_specular_mask=shield,output_name=f"direction-{direction:02d}-zero-specular-causal.png",diagnostics=False)
  report["directions"][str(direction)]={"current":current["component_contributions"]["shield"],"zero_specular":zero["component_contributions"]["shield"]}
 visible=[(v["current"]["final_display"]["mean"],int(k)) for k,v in report["directions"].items() if v["current"]["final_display"]["pixels"]>=100]
 report["visible_direction_controls"]={"darkest":min(visible)[1],"brightest":max(visible)[1],"minimum_visible_pixels":100}
 (a.output/"scutum-material-semantics-audit.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
