"""Build ignored native-SLD assets for the in-game visual calibration grid."""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
from PIL import Image, ImageDraw

from .analyze_sld import analyze
from .sld import serialize_sld
from .sld_authoring import DirectXTexBC1Encoder, alpha_bounds, author_identical_facets, author_direction_frames

DIRECTIONS = {0: ("rear_three_quarter", 45.0), 4: ("front_three_quarter", 315.0),
              5: ("front", 292.5), 8: ("shield_forward_side", 225.0)}

def opened(path: Path) -> Image.Image:
    return Image.open(path).convert("RGBA")

def scale_about_hotspot(source: Image.Image, canvas: int, hotspot: tuple[int, int], target_height: int) -> Image.Image:
    """Scale the thresholded sprite while preserving its feet/hotspot vector."""
    source = source.convert("RGBA"); bounds = alpha_bounds(source)
    if bounds is None: raise ValueError("cannot scale an empty source image")
    x1,y1,x2,y2=bounds; factor=target_height/(y2-y1)
    crop=source.crop(bounds); size=(max(1,round(crop.width*factor)),target_height)
    crop=crop.resize(size,Image.Resampling.BICUBIC)
    source_hotspot=(source.width//2,source.height//2)
    left=round(hotspot[0]+(x1-source_hotspot[0])*factor)
    top=round(hotspot[1]+(y1-source_hotspot[1])*factor)
    result=Image.new("RGBA",(canvas,canvas)); result.alpha_composite(crop,(left,top)); return result

def scale_shadow(source: Image.Image, canvas: int, hotspot: tuple[int,int], factor: float,
                 alpha_scale: float=1.0, contact: bool=False) -> Image.Image:
    source=source.convert("RGBA"); bounds=alpha_bounds(source,1)
    if bounds is None: return Image.new("RGBA",(canvas,canvas))
    x1,y1,x2,y2=bounds; crop=source.crop(bounds)
    size=(max(1,round(crop.width*factor)),max(1,round(crop.height*factor)))
    crop=crop.resize(size,Image.Resampling.BICUBIC)
    px=crop.load()
    for y in range(crop.height):
        for x in range(crop.width):
            r,g,b,a=px[x,y]; boosted=min(255,round(a*alpha_scale))
            if contact:
                # Five logical pixels about the feet, retaining the broad soft shadow.
                dx=(x + round(hotspot[0]+(x1-source.width//2)*factor))-hotspot[0]
                dy=(y + round(hotspot[1]+(y1-source.height//2)*factor))-hotspot[1]
                if dx*dx+dy*dy <= (5*canvas/200)**2: boosted=max(boosted,199)
            px[x,y]=(r,g,b,boosted)
    left=round(hotspot[0]+(x1-source.width//2)*factor); top=round(hotspot[1]+(y1-source.height//2)*factor)
    result=Image.new("RGBA",(canvas,canvas)); result.alpha_composite(crop,(left,top)); return result

def player_mask(source: Image.Image, canvas: int, hotspot: tuple[int,int], target_height: int, threshold: int) -> Image.Image:
    scaled=scale_about_hotspot(source,canvas,hotspot,target_height); out=Image.new("RGBA",scaled.size)
    for y in range(canvas):
        for x in range(canvas):
            r,g,b,a=scaled.getpixel((x,y)); value=round(.2126*r+.7152*g+.0722*b)
            # Retain source shading; threshold selects restrained versus broad coverage.
            out.putpixel((x,y),(value,value,value,a if value>=threshold else 0))
    return out

def metrics(image: Image.Image) -> dict:
    values=[]; sats=[]; clipped=0
    for r,g,b,a in image.convert("RGBA").getdata():
        if a<128: continue
        lum=.2126*r+.7152*g+.0722*b; values.append(lum)
        high=max(r,g,b); low=min(r,g,b); sats.append(0 if high==0 else (high-low)/high)
        clipped += high>=250
    values.sort()
    percentile=lambda p: values[min(len(values)-1,round((len(values)-1)*p))]
    return {"opaque_pixels":len(values),"mean_luminance":sum(values)/len(values),
            "luminance_p10":percentile(.1),"luminance_p50":percentile(.5),"luminance_p90":percentile(.9),
            "mean_saturation":sum(sats)/len(sats),"highlight_clipping_percent":100*clipped/len(values)}

def write_sld(path: Path, frames, hotspot, texconv: Path, facets=16):
    factory=lambda:DirectXTexBC1Encoder(texconv)
    if len(frames)==1:
        main,shadow,pc=frames[0]; sld=author_identical_facets(main,shadow,facets,hotspot,encoder=factory(),player_color=pc)
    else: sld=author_direction_frames(frames,hotspot,facets,encoder_factory=factory)
    data=serialize_sld(sld); path.write_bytes(data); parsed=analyze(data,path.name)
    parsed["dat_facet_count"] = facets
    return {"path":path.name,"sha256":hashlib.sha256(data).hexdigest(),"strict":parsed}

def render_path(root: Path,index:int,kind="color"):
    return root/f"sws_stand-sample-0000-direction-{index:02d}-{kind}-4x.png"

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--v2-root",type=Path,required=True); p.add_argument("--v3-root",type=Path,required=True)
    p.add_argument("--brightness-root",type=Path,required=True); p.add_argument("--mask-r",type=Path,required=True)
    p.add_argument("--texconv",type=Path,required=True); p.add_argument("--output-root",type=Path,required=True)
    args=p.parse_args(); root=args.output_root; root.mkdir(parents=True,exist_ok=True)
    report={"format":"rome2aoe2.sld-visual-calibration","version":1,"directions":[],"variants":[],"brightness_metrics":{}}
    # Labeled source-orientation sheet.
    sheet=Image.new("RGBA",(4*240,260),(24,24,24,255)); draw=ImageDraw.Draw(sheet)
    for column,(index,(label,azimuth)) in enumerate(DIRECTIONS.items()):
        image=opened(render_path(args.v3_root,index)); crop=image.crop(alpha_bounds(image)); crop.thumbnail((190,190),Image.Resampling.BICUBIC)
        sheet.alpha_composite(crop,(column*240+(240-crop.width)//2,55+(190-crop.height)//2)); draw.text((column*240+8,8),f"{index}: {label}\nazimuth {azimuth:g}",fill="white")
        report["directions"].append({"index":index,"label":label,"camera_azimuth_degrees":azimuth})
    sheet.save(root/"four-direction-contact-sheet.png")
    # Scale row uses unchanged v2 exposure and front-three-quarter direction.
    source=opened(render_path(args.v2_root,4)); shadow=opened(render_path(args.v2_root,4,"shadow")); source_bounds=alpha_bounds(source)
    for height in (45,50,54,60):
        frames=[]
        for canvas in (200,400):
            logical=height*(canvas//200); main=scale_about_hotspot(source,canvas,(canvas//2,canvas//2),logical)
            factor=logical/(source_bounds[3]-source_bounds[1]); sh=scale_shadow(shadow,canvas,(canvas//2,canvas//2),factor)
            main.save(root/f"scale-{height}_x{canvas//200}-main.png"); sh.save(root/f"scale-{height}_x{canvas//200}-shadow.png")
            result=write_sld(root/f"rome2aoe2_visual_scale_{height}_x{canvas//200}.sld",[(main,sh,None)],(canvas//2,canvas//2),args.texconv)
            frames.append(result)
        report["variants"].append({"kind":"scale","logical_height":height,"assets":frames})
    # Brightness row at the leading 50 px scale.
    brightness=("current","exposure-plus-03","exposure-plus-06","fill-plus")
    for name in brightness:
        high=opened(render_path(args.brightness_root/name,4)); report["brightness_metrics"][name]=metrics(high)
        bounds=alpha_bounds(high); assets=[]
        for canvas in (200,400):
            logical=50*(canvas//200); main=scale_about_hotspot(high,canvas,(canvas//2,canvas//2),logical)
            factor=logical/(bounds[3]-bounds[1]); sh=scale_shadow(shadow,canvas,(canvas//2,canvas//2),factor)
            result=write_sld(root/f"rome2aoe2_visual_brightness_{name}_x{canvas//200}.sld",[(main,sh,None)],(canvas//2,canvas//2),args.texconv)
            assets.append(result)
        report["variants"].append({"kind":"brightness","name":name,"assets":assets})
    # Player colour: authored R channel is the only strong selected-unit channel.
    mask_source=opened(args.mask_r); leading=opened(render_path(args.v3_root,4)); bounds=alpha_bounds(leading)
    for mapping,cutoff in (("restrained",128),("stronger",24)):
        assets=[]
        for canvas in (200,400):
            logical=50*(canvas//200); main=scale_about_hotspot(leading,canvas,(canvas//2,canvas//2),logical)
            factor=logical/(bounds[3]-bounds[1]); sh=scale_shadow(shadow,canvas,(canvas//2,canvas//2),factor,1.17,True)
            pc=player_mask(mask_source,canvas,(canvas//2,canvas//2),logical,cutoff)
            pc.save(root/f"playercolor-{mapping}_x{canvas//200}.png")
            result=write_sld(root/f"rome2aoe2_visual_playercolor_{mapping}_x{canvas//200}.sld",[(main,sh,pc)],(canvas//2,canvas//2),args.texconv)
            assets.append(result)
        report["variants"].append({"kind":"player_color","mapping":mapping,"mask_channel":"R","cutoff":cutoff,"assets":assets})
    # Shadow variants, measured independently from the unchanged main image.
    for name,alpha_scale,contact in (("current",1.0,False),("stronger",1.17,False),("contact",1.17,True)):
        assets=[]
        for canvas in (200,400):
            logical=50*(canvas//200); main=scale_about_hotspot(leading,canvas,(canvas//2,canvas//2),logical)
            factor=logical/(bounds[3]-bounds[1]); sh=scale_shadow(shadow,canvas,(canvas//2,canvas//2),factor,alpha_scale,contact)
            sh.save(root/f"shadow-{name}_x{canvas//200}.png")
            assets.append(write_sld(root/f"rome2aoe2_visual_shadow_{name}_x{canvas//200}.sld",[(main,sh,None)],(canvas//2,canvas//2),args.texconv))
        report["variants"].append({"kind":"shadow","name":name,"alpha_scale":alpha_scale,"contact":contact,"assets":assets})
    # Four genuine views assigned to the nearest of 16 facets.
    four=[]
    for facet in range(16):
        nearest=min(DIRECTIONS,key=lambda i:min((facet-i)%16,(i-facet)%16)); hi=opened(render_path(args.v3_root,nearest)); b=alpha_bounds(hi)
        main=scale_about_hotspot(hi,200,(100,100),50); factor=50/(b[3]-b[1]); sh=scale_shadow(opened(render_path(args.v3_root,nearest,"shadow")),200,(100,100),factor,1.17,True)
        four.append((main,sh,None))
    x1=write_sld(root/"rome2aoe2_visual_four_directions_x1.sld",four,(100,100),args.texconv,16)
    four2=[]
    for facet in range(16):
        nearest=min(DIRECTIONS,key=lambda i:min((facet-i)%16,(i-facet)%16)); hi=opened(render_path(args.v3_root,nearest)); b=alpha_bounds(hi)
        main=scale_about_hotspot(hi,400,(200,200),100); factor=100/(b[3]-b[1]); sh=scale_shadow(opened(render_path(args.v3_root,nearest,"shadow")),400,(200,200),factor,1.17,True)
        four2.append((main,sh,None))
    x2=write_sld(root/"rome2aoe2_visual_four_directions_x2.sld",four2,(200,200),args.texconv,16)
    report["variants"].append({"kind":"four_directions","source_indices":list(DIRECTIONS),"nearest_facet_fill":True,"assets":[x1,x2]})
    (root/"visual-calibration-report.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return 0
if __name__=="__main__": raise SystemExit(main())
