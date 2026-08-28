"""Trace representative pre-fix artifact pixels through frozen exact stages."""
import json
import sys
from pathlib import Path

import bpy
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"src/blender"));sys.path.insert(0,str(ROOT/"src/rome2"))
import render_hastati_runtime_parity as runtime  # noqa: E402
from runtime_material_preparation import (prepare_decal_dirtmap,prepare_weighted,
    prepare_weighted_dirtmap,prepare_weighted_skin_dirtmap)  # noqa: E402

BASE=ROOT/"build/validation/rome2aoe2/principes-scene-routing"
AOV=BASE/"pre-fix-full/aov"
OUT=BASE/"pre-fix-trace"


def image(path):
    source=bpy.data.images.load(str(path),check_existing=False);data=np.empty(len(source.pixels),np.float32)
    source.pixels.foreach_get(data);result=data.reshape((source.size[1],source.size[0],4))[::-1].copy()
    bpy.data.images.remove(source);return result


def prepared(arrays):
    arrays={k:v.copy() for k,v in arrays.items()};arrays["normal_sample"][...,3]=arrays["normal_alpha"][...,0]
    arrays["dirt_raw"][...,3]=arrays["dirt_alpha"][...,0];arrays["dirt_mask_raw"][...,3]=arrays["dirt_mask_alpha"][...,0]
    active=arrays["diffuse_raw"][...,3]>.001;family=arrays["family"]
    base=runtime.normalize(arrays["basis_normal"][...,:3]*2-1);t=runtime.normalize(arrays["basis_tangent"][...,:3]*2-1);b=runtime.normalize(arrays["basis_bitangent"][...,:3]*2-1)
    skin=(family[...,0]>.5)&(family[...,1]<.5);decal=(family[...,1]>.5)&(family[...,0]<.5)
    dirt=(family[...,2]>.5)&(family[...,0]<.5)&(family[...,1]<.5);weighted=active&~skin&~decal&~dirt
    shape=active.shape;N=base.copy();D=np.zeros((*shape,3),np.float32);F=np.zeros_like(D);S=np.zeros(shape,np.float32);R=np.zeros(shape,np.float32)
    def assign(q,p):N[q]=p.normal;D[q]=p.diffuse;F[q]=p.specular;S[q]=p.smoothness;R[q]=p.reflectivity
    raw=(arrays["diffuse_raw"],arrays["specular_raw"],arrays["normal_sample"],arrays["gloss_raw"])
    if np.any(weighted):q=weighted;assign(q,prepare_weighted(*(x[q] for x in raw),base[q],t[q],b[q],arrays["mask_raw"][q],runtime.FACTION))
    if np.any(dirt):q=dirt;assign(q,prepare_weighted_dirtmap(*(x[q] for x in raw),arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],base[q],t[q],b[q],arrays["mask_raw"][q],runtime.FACTION))
    if np.any(skin):q=skin;assign(q,prepare_weighted_skin_dirtmap(arrays["diffuse_raw"][q],arrays["normal_sample"][q],arrays["gloss_raw"][q],arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],arrays["specular_raw"][q],base[q],t[q],b[q]))
    if np.any(decal):q=decal;assign(q,prepare_decal_dirtmap(*(x[q] for x in raw),arrays["mask_raw"][q],arrays["dirt_mask_raw"][q],arrays["dirt_raw"][q],base[q],t[q],b[q],runtime.SHIELD_FACTION))
    return {"normal":N,"diffuse":D,"specular":F,"smoothness":S,"reflectivity":R},skin,dirt


def record(label,y,x,arrays,p,hdr,display):
    return {"label":label,"pixel_xy":[int(x),int(y)],"family":arrays["family"][y,x].tolist(),
            "source_diffuse":arrays["diffuse_raw"][y,x,:3].tolist(),"faction_prepared_diffuse":p["diffuse"][y,x].tolist(),
            "normal_sample":arrays["normal_sample"][y,x].tolist(),"basis_normal":arrays["basis_normal"][y,x,:3].tolist(),
            "basis_tangent":arrays["basis_tangent"][y,x,:3].tolist(),"basis_bitangent":arrays["basis_bitangent"][y,x,:3].tolist(),
            "prepared_normal":p["normal"][y,x].tolist(),"specular":p["specular"][y,x].tolist(),
            "smoothness":float(p["smoothness"][y,x]),"reflectivity":float(p["reflectivity"][y,x]),
            "raw_captured_lighting":hdr[y,x,:3].tolist(),"display_rgb":display[y,x,:3].tolist()}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(ROOT/"build/conversions/rom_principes/bc5d577aadbce8e452d4419c6282e1e0d916900a9038516b321684ead85135c6/static-unit.blend1"))
    arrays={name:np.load(AOV/f"{name}.npy") for name in runtime.exact_materials.RAW_AOVS} if hasattr(runtime,"exact_materials") else {p.stem:np.load(p) for p in AOV.glob("*.npy")}
    runtime.OUT=OUT;runtime.AOV=OUT;runtime.RESOLUTION=arrays["diffuse_raw"].shape[0]
    runtime.shade(bpy.context.scene,{k:v.copy() for k,v in arrays.items()},output_name="pre-fix-reconstructed.png",diagnostics=True)
    display=image(OUT/"pre-fix-reconstructed.png");hdr=np.load(OUT/"hdr_linear.npy");p,skin,dirt=prepared(arrays)
    rgb=display[...,:3];active=arrays["diffuse_raw"][...,3]>.5
    cyan_score=rgb[...,1]+rgb[...,2]-2*rgb[...,0]
    cy,cx=np.unravel_index(np.argmax(np.where(active,cyan_score,-1)),active.shape)
    cyan=active&(cyan_score>.12)
    grey=skin&(rgb.min(axis=-1)>.25)&((rgb.max(axis=-1)-rgb.min(axis=-1))<.12)
    gy,gx=np.unravel_index(np.argmax(np.where(grey,rgb.mean(axis=-1),-1)),grey.shape)
    report={"cyan":record("cyan",cy,cx,arrays,p,hdr,display),"grey_white_skin":record("grey_white_skin",gy,gx,arrays,p,hdr,display),
            "cyan_counts":{"source_diffuse":int(np.count_nonzero((arrays['diffuse_raw'][...,1]>.25)&(arrays['diffuse_raw'][...,2]>.25)&(arrays['diffuse_raw'][...,0]<.18)&active)),
                           "prepared_diffuse":int(np.count_nonzero((p['diffuse'][...,1]>.25)&(p['diffuse'][...,2]>.25)&(p['diffuse'][...,0]<.18)&active)),
                           "display":int(np.count_nonzero(cyan))}}
    (OUT/"pixel-traces.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report))


if __name__=="__main__":main()
