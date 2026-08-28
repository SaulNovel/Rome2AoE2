"""Decode proprietary stock AoE2 references into ignored build output and measure style.

The inputs are read directly from the local AoE2 DE installation.  Nothing is
copied into the repository or committed.
"""
from __future__ import annotations

import json, math, statistics, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "build/python-deps/pillow"), str(ROOT / "src")]
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from aoe2.sld import parse_sld
from aoe2.analyze_sld import decode_frame

OUT = ROOT / "build/local-integration/rome2/aoe-style-calibration"
GRAPHICS = Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\drs\graphics")
HASTATI = ROOT / "build/local-integration/rome2/runtime-resolution/renders/hastati-runtime-resolved-representative.png"
REFS = {
    "militia": {"unit_id": 74, "graphic_id": 1102, "stem": "u_inf_militia_idleA", "frames_per_facet": 30},
    "man-at-arms": {"unit_id": 75, "graphic_id": 1115, "stem": "u_inf_manatarms_idleA", "frames_per_facet": 30},
    "legionary": {"unit_id": 1793, "graphic_id": 7605, "stem": "u_inf_legionary_idleA", "frames_per_facet": 45},
}
# Facet 2 is the native facing closest to the fixed Rome camera's readable 3/4 view.
FACET = 2

def rgba_metrics(image: Image.Image, shadow: Image.Image | None = None, pc: Image.Image | None = None) -> dict:
    im=image.convert("RGBA"); a=im.getchannel("A"); box=a.getbbox(); pix=[]
    if box:
        for r,g,b,alpha in im.crop(box).getdata():
            if alpha > 8:
                y=.2126*r+.7152*g+.0722*b
                mx=max(r,g,b); mn=min(r,g,b); sat=0 if mx==0 else (mx-mn)/mx*255
                pix.append((y,sat,alpha))
    ys=sorted(v[0] for v in pix); sats=[v[1] for v in pix]
    def q(p): return round(ys[min(len(ys)-1, int((len(ys)-1)*p))],3) if ys else None
    gray=im.convert("L"); edges=gray.filter(ImageFilter.FIND_EDGES)
    ep=[v for v,a0 in zip(edges.getdata(),a.getdata()) if a0>8]
    local=[]
    blur=gray.filter(ImageFilter.GaussianBlur(1.2))
    for v,b0,a0 in zip(gray.getdata(),blur.getdata(),a.getdata()):
        if a0>8: local.append(abs(v-b0))
    shadow_alpha=list((shadow.getchannel("A") if shadow and shadow.mode=="RGBA" else shadow.convert("L")).getdata()) if shadow else []
    pc_alpha=list(pc.convert("L").getdata()) if pc else []
    body_count=len(pix)
    return {
        "bbox": list(box) if box else None,
        "bbox_width": box[2]-box[0] if box else 0,
        "bbox_height": box[3]-box[1] if box else 0,
        "opaque_pixel_count": body_count,
        "silhouette_density": round(body_count/((box[2]-box[0])*(box[3]-box[1])),5) if box and body_count else 0,
        "luminance": {f"p{int(p*100):02d}": q(p) for p in (.05,.10,.25,.50,.75,.90,.95)},
        "mean_saturation": round(statistics.fmean(sats),3) if sats else 0,
        "local_luminance_contrast": round(statistics.fmean(local),3) if local else 0,
        "edge_contrast": round(statistics.fmean(ep),3) if ep else 0,
        "edge_acutance_p90": round(sorted(ep)[int(.9*(len(ep)-1))],3) if ep else 0,
        "highlight_clipping_percent": round(100*sum(y>=250 for y in ys)/len(ys),4) if ys else 0,
        "dark_pixel_percent": round(100*sum(y<=40 for y in ys)/len(ys),3) if ys else 0,
        "shadow_opacity_mean": round(statistics.fmean(v for v in shadow_alpha if v>0),3) if any(shadow_alpha) else 0,
        "shadow_area_relative_to_body": round(sum(v>8 for v in shadow_alpha)/body_count,4) if body_count and shadow_alpha else 0,
        "player_colour_coverage": round(sum(v>8 for v in pc_alpha)/body_count,4) if body_count and pc_alpha else 0,
        "body_to_shadow_contrast": round((statistics.median(ys) if ys else 0)-(64*(1-statistics.fmean(v for v in shadow_alpha if v>0)/255) if any(shadow_alpha) else 64),3),
    }

def decode_stock() -> tuple[dict, list[tuple[str,Image.Image]]]:
    decoded=OUT/"decoded-stock"; decoded.mkdir(parents=True,exist_ok=True)
    results={}; images=[]
    for key,rec in REFS.items():
        result={**rec,"facet":FACET,"sample":0,"files":{},"metrics":{}}
        for zoom in ("x1","x2"):
            src=GRAPHICS/f"{rec['stem']}_{zoom}.sld"; raw=src.read_bytes(); doc=parse_sld(raw)
            expected=rec["frames_per_facet"]*16
            # Stock idle SLDs carry a final repeated loop-closure frame.
            if len(doc.frames) not in (expected,expected+1): raise ValueError(f"{src}: {len(doc.frames)} frames, expected {expected} or loop-closed {expected+1}")
            if raw != __import__('aoe2.sld',fromlist=['serialize_sld']).serialize_sld(doc): raise ValueError(f"{src}: nondeterministic serialization")
            index=FACET*rec["frames_per_facet"]
            main,shadow=decode_frame(doc,index)
            # Decode the PC layer separately by retaining its scalar alpha image.
            from aoe2.sld import LAYER_PLAYERCOLOR
            from aoe2.sld_blocks import decode_bc4_block
            frame=doc.frames[index]; pc=Image.new("L",main.size,0)
            layer=next((x for x in frame.layers if x.layer_type==LAYER_PLAYERCOLOR),None)
            if layer:
                main_layer=next(x for x in frame.layers if x.layer_type==1)
                width=main_layer.offset_x2-main_layer.offset_x1; columns=(width+3)//4; cursor=0; bi=0
                for skip,draw in layer.commands:
                    cursor+=skip
                    for _ in range(draw):
                        x=main_layer.offset_x1+(cursor%columns)*4; y=main_layer.offset_y1+(cursor//columns)*4
                        block=decode_bc4_block(layer.blocks[bi])
                        for yy in range(4):
                            for xx in range(4):
                                if x+xx<frame.canvas_width and y+yy<frame.canvas_height: pc.putpixel((x+xx,y+yy),block[yy][xx])
                        cursor+=1; bi+=1
            p=decoded/f"{key}-{zoom}-facet{FACET:02d}-frame00.png"; main.save(p)
            shadow.save(decoded/f"{key}-{zoom}-shadow.png"); pc.save(decoded/f"{key}-{zoom}-playercolor.png")
            result["files"][zoom]={"sld":str(src),"png":str(p)}
            result["metrics"][zoom]=rgba_metrics(main,shadow,pc)
            if zoom=="x1": images.append((key,main))
        results[key]=result
    return results,images

def hastati_x1() -> Image.Image:
    im=Image.open(HASTATI).convert("RGBA"); box=im.getchannel("A").getbbox()
    if not box: raise ValueError("empty Hastati render")
    crop=im.crop(box); scale=50/crop.height; crop=crop.resize((max(1,round(crop.width*scale)),50),Image.Resampling.LANCZOS)
    canvas=Image.new("RGBA",(200,200)); canvas.alpha_composite(crop,(100-crop.width//2,100-crop.height))
    return canvas

def sheet(images):
    font=ImageFont.load_default(); bg=(47,71,48,255); cell=(220,240)
    out=Image.new("RGBA",(cell[0]*len(images),cell[1]),bg); d=ImageDraw.Draw(out)
    for i,(name,im) in enumerate(images):
        out.alpha_composite(im,(i*cell[0]+10,20)); d.text((i*cell[0]+10,215),name,fill="white",font=font)
    out.save(OUT/"reference-comparison.png")

def main():
    OUT.mkdir(parents=True,exist_ok=True); refs,images=decode_stock(); h=hastati_x1(); h.save(OUT/"hastati-current-x1.png")
    from aoe2.generate_v4_ingame_proof import make_shadow
    hs=make_shadow(h);refs["hastati-current"]={"source":str(HASTATI),"metrics":{"x1":rgba_metrics(h,hs)}}; images.append(("Hastati current",h)); sheet(images)
    payload={"format":"rome2aoe2.aoe-style-reference-analysis","version":1,"proprietary_outputs_ignored":True,"selection":{"facet":FACET,"sample":0},"references":refs}
    (OUT/"aoe-reference-analysis.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(payload,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
