"""Eight-way coherent Rome II environment-yaw experiment for frozen facet 03."""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src/blender"))
import render_hastati_runtime_parity as rp
import render_cross_unit_set_a as cu

YAWS=tuple(range(0,360,45))


def main():
    rp.OUT.mkdir(parents=True,exist_ok=True);rp.AOV.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True);root,_=cu.import_unit("hastati")
    cu.configure_camera(bpy.context.scene,rp.FACET_AZIMUTH,30,8.5,12)
    scene=bpy.context.scene;scene.render.engine="BLENDER_EEVEE"
    scene.render.resolution_x=scene.render.resolution_y=rp.RESOLUTION;scene.render.resolution_percentage=100;scene.render.film_transparent=True
    scene.render.image_settings.file_format="OPEN_EXR";scene.render.image_settings.color_mode="RGBA";scene.render.image_settings.color_depth="32";scene.render.image_settings.exr_codec="ZIP"
    scene.display_settings.display_device="sRGB";scene.view_settings.view_transform="Raw";scene.view_settings.look="None";scene.view_settings.exposure=0;scene.view_settings.gamma=1
    region=rp.render_aov(scene,root,"region")
    names=("basis_normal","basis_tangent","basis_bitangent","diffuse_raw","specular_raw","gloss_raw","normal_sample","normal_alpha","mask_raw","dirt_raw","dirt_alpha","dirt_mask_raw","dirt_mask_alpha","family")
    missing=[name for name in names if not (rp.AOV/f"{name}.npy").exists()]
    if missing: raise RuntimeError(f"Missing shared-production AOVs: {missing}; run render_hastati_runtime_parity.py first")
    arrays={name:np.load(rp.AOV/f"{name}.npy",mmap_mode="r") for name in names}
    active=arrays["diffuse_raw"][...,3]>.001;ys,xs=np.where(active);pad=4
    x0=max(0,int(xs.min())-pad);x1=min(rp.RESOLUTION,int(xs.max())+pad+1);y0=max(0,int(ys.min())-pad);y1=min(rp.RESOLUTION,int(ys.max())+pad+1)
    arrays={name:np.array(value[y0:y1,x0:x1],copy=True) for name,value in arrays.items()};region=np.array(region[y0:y1,x0:x1],copy=True)
    rows=[]
    for yaw in YAWS:
        print(f"Rendering coherent environment yaw {yaw:03d}")
        rows.append(rp.shade(scene,arrays,yaw,f"lighting-yaw-{yaw:03d}.png",False,region,(x0,y0)))
    report={"format":"rome2aoe2.hastati-lighting-yaw-sweep","version":1,"facet":3,"active_pixel_bounds":[x0,y0,x1,y1],"environment_rotation":{"axis":"Blender world Z","sun":"L=Renv@L0","ambient":"Nenv=N@Renv","cubemap":"reflected@Renv@transform"},"frozen":{"materials":True,"shader_equations":True,"intensities":True,"colours":True,"tone_display":True,"camera":True,"pose":True,"scale":True},"candidates":rows}
    (rp.OUT/"lighting-yaw-report.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__=="__main__":main()
