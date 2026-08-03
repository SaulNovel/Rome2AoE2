"""Build the ignored native-SLD runtime diagnostic set."""
from __future__ import annotations
import argparse, json, sys
import math, colorsys
from pathlib import Path

from PIL import Image, ImageDraw
from .analyze_sld import decode_frame
from .sld import parse_sld, serialize_sld
from .sld_authoring import DirectXTexBC1Encoder, author_identical_facets, bleed_transparent_rgb, premultiplied_bicubic
from .sld_authoring import alpha_bounds
from .sld_blocks import decode_bc1_block

SHADOW_OPACITY=0.58

def synthetic_rgb_control(scale: int = 1) -> Image.Image:
    if scale not in (1,2): raise ValueError("RGB control scale must be 1 or 2")
    image=Image.new("RGBA",(200*scale,200*scale),(0,0,0,0)); draw=ImageDraw.Draw(image)
    colors=[(255,0,0,255),(0,255,0,255),(0,0,255,255),(255,255,0,255),(0,255,255,255),(255,0,255,255)]
    for index,color in enumerate(colors):
        x=(70+(index%3)*20)*scale; y=(68+(index//3)*24)*scale
        draw.rectangle((x,y,x+18*scale-1,y+20*scale-1),fill=color)
    draw.rectangle((70*scale,112*scale,78*scale-1,126*scale-1),fill=(255,0,0,255))
    return image

def debug_scale_about_hotspot(image: Image.Image, scale: float, hotspot=(100,100)) -> Image.Image:
    source=image.convert("RGBA"); resized=source.resize((round(source.width*scale),round(source.height*scale)),Image.Resampling.BICUBIC)
    output=Image.new("RGBA",source.size); left=round(hotspot[0]-hotspot[0]*scale); top=round(hotspot[1]-hotspot[1]*scale)
    output.alpha_composite(resized,(left,top)); return output

def write_sld(main,shadow,path,encoder,hotspot,facets=16):
    sld=author_identical_facets(main,shadow,facets,hotspot,encoder=encoder); path.write_bytes(serialize_sld(sld)); return sld

def decoded_directxtex(image,executable):
    prepared=bleed_transparent_rgb(image); encoder=DirectXTexBC1Encoder(executable); encoder.prepare(prepared,128)
    output=Image.new("RGBA",prepared.size)
    for index,block in enumerate(encoder.blocks):
        x=(index%encoder.blocks_per_row)*4; y=(index//encoder.blocks_per_row)*4; pixels=decode_bc1_block(block)
        if not any(image.getpixel((x+column,y+row))[3]>=128 for row in range(4) for column in range(4)): continue
        for row in range(4):
            for column in range(4): output.putpixel((x+column,y+row),pixels[row][column])
    return output

def color_metrics(source,target):
    source_pixels=list(source.get_flattened_data()); target_pixels=list(target.get_flattened_data())
    pairs=[(a,b) for a,b in zip(source_pixels,target_pixels) if a[3]>=128]
    source_visible=[p[3]>=128 for p in source_pixels]; target_visible=[p[3]>=128 for p in target_pixels]
    errors=[(a[c]-b[c])**2 for a,b in pairs for c in range(3)]; mse=sum(errors)/len(errors)
    pixels=[b for _,b in pairs]; means=[sum(p[c] for p in pixels)/len(pixels) for c in range(3)]
    saturation=[colorsys.rgb_to_hsv(p[0]/255,p[1]/255,p[2]/255)[1] for p in pixels]
    luminance=[0.2126*p[0]+0.7152*p[1]+0.0722*p[2] for p in pixels]
    return {"mean_rgb":sum(means)/3,"channel_means":means,"mean_saturation":sum(saturation)/len(saturation),
            "mean_luminance":sum(luminance)/len(luminance),"low_saturation_percent":100*sum(v<0.15 for v in saturation)/len(saturation),
            "opaque_rgb_psnr_db":None if mse==0 else 10*math.log10(255*255/mse),"false_opaque":sum(not a and b for a,b in zip(source_visible,target_visible)),
            "false_transparent":sum(a and not b for a,b in zip(source_visible,target_visible))}

def main()->int:
    parser=argparse.ArgumentParser(); parser.add_argument("--render-root",type=Path,required=True); parser.add_argument("--output-root",type=Path,required=True); parser.add_argument("--texconv",type=Path,required=True)
    args=parser.parse_args(); root=args.output_root; root.mkdir(parents=True,exist_ok=True)
    def paths(direction,size_suffix=""):
        stem=f"sws_stand-sample-0000-direction-{direction:02d}"
        return args.render_root/f"{stem}-color{size_suffix}.png",args.render_root/f"{stem}-shadow{size_suffix}.png"
    encoder=lambda:DirectXTexBC1Encoder(args.texconv)
    d0_main,d0_shadow=paths(0); hi_main,hi_shadow=paths(0,"-4x")
    x1_main=Image.open(d0_main).convert("RGBA"); x1_shadow=Image.open(d0_shadow).convert("RGBA")
    x2_main=premultiplied_bicubic(Image.open(hi_main), (400,400)); x2_shadow=premultiplied_bicubic(Image.open(hi_shadow),(400,400),SHADOW_OPACITY)
    # Cycles leaves isolated one-byte shadow noise in the retained 800px pass.
    # Constrain only that noise to the calibrated x1 shadow envelope at 2x;
    # all retained x2 values inside the envelope still come from the 800px render.
    sx1,sy1,sx2,sy2=alpha_bounds(x1_shadow,1)
    for y in range(x2_shadow.height):
        for x in range(x2_shadow.width):
            if not (sx1*2 <= x < sx2*2 and sy1*2 <= y < sy2*2):
                r,g,b,_=x2_shadow.getpixel((x,y)); x2_shadow.putpixel((x,y),(r,g,b,0))
    x2_main.save(root/"praetorian-direction00-x2-source.png"); x2_shadow.save(root/"praetorian-direction00-x2-shadow.png")
    outputs={}
    for zoom,main_image,shadow_image,hotspot in (("x1",x1_main,x1_shadow,(100,100)),("x2",x2_main,x2_shadow,(200,200))):
        path=root/f"rome2aoe2_praetorian_sld_diagnostic_{zoom}.sld"; sld=write_sld(main_image,shadow_image,path,encoder(),hotspot); outputs[zoom]={"path":path.name,"frames":len(sld.frames),"canvas":list(main_image.size),"hotspot":list(hotspot)}
    color=synthetic_rgb_control(); color_x2=synthetic_rgb_control(2)
    color.save(root/"rgb-control-source.png"); color_sld=root/"rome2aoe2_rgb_sld_diagnostic_x1.sld"; write_sld(color,None,color_sld,encoder(),(100,100))
    color_x2.save(root/"rgb-control-source-x2.png"); color_sld_x2=root/"rome2aoe2_rgb_sld_diagnostic_x2.sld"; write_sld(color_x2,None,color_sld_x2,encoder(),(200,200))
    decoded,_=decode_frame(parse_sld(color_sld.read_bytes())); decoded.save(root/"rgb-control-sld-decoded.png")
    bleed_transparent_rgb(color).save(root/"rgb-control-bleed.png")
    sheet=Image.new("RGBA",(800,200),(24,24,24,255)); labels=("source","edge bleed","SLD decode","expected in game")
    for index,image in enumerate((color,bleed_transparent_rgb(color),decoded,decoded)):
        sheet.alpha_composite(image,(index*200,0)); ImageDraw.Draw(sheet).text((index*200+4,4),labels[index],fill="white")
    sheet.save(root/"rgb-control-contact-sheet.png")
    # Readable direction 04 and a 60-pixel debug-only enlargement.
    front_main,front_shadow=paths(4); front_hi_main,front_hi_shadow=paths(4,"-4x")
    fm=Image.open(front_main).convert("RGBA"); fs=Image.open(front_shadow).convert("RGBA")
    front_path=root/"rome2aoe2_praetorian_front3q_x1.sld"; write_sld(fm,fs,front_path,encoder(),(100,100))
    fm_x2=premultiplied_bicubic(Image.open(front_hi_main),(400,400)); fs_x2=premultiplied_bicubic(Image.open(front_hi_shadow),(400,400),SHADOW_OPACITY)
    fx1,fy1,fx2,fy2=alpha_bounds(fs,1)
    for y in range(400):
        for x in range(400):
            if not (fx1*2<=x<fx2*2 and fy1*2<=y<fy2*2):
                r,g,b,_=fs_x2.getpixel((x,y)); fs_x2.putpixel((x,y),(r,g,b,0))
    fm_x2.save(root/"praetorian-front3q-x2-source.png"); fs_x2.save(root/"praetorian-front3q-x2-shadow.png")
    front_path_x2=root/"rome2aoe2_praetorian_front3q_x2.sld"; write_sld(fm_x2,fs_x2,front_path_x2,encoder(),(200,200))
    bleed=bleed_transparent_rgb(fm); bleed.save(root/"praetorian-front3q-bleed.png")
    dds_decoded=decoded_directxtex(fm,args.texconv); dds_decoded.save(root/"praetorian-front3q-directxtex-decoded.png")
    sld_decoded,_=decode_frame(parse_sld(front_path.read_bytes())); sld_decoded.save(root/"praetorian-front3q-sld-decoded.png")
    debug_main=debug_scale_about_hotspot(fm,60/42); debug_shadow=debug_scale_about_hotspot(fs,60/42)
    debug_main.save(root/"praetorian-front3q-debug60.png"); debug_path=root/"rome2aoe2_praetorian_front3q_debug60_x1.sld"; write_sld(debug_main,debug_shadow,debug_path,encoder(),(100,100))
    production_x2_height=alpha_bounds(fm_x2,128)[3]-alpha_bounds(fm_x2,128)[1]
    debug_x2_scale=120/production_x2_height
    debug_main_x2=debug_scale_about_hotspot(fm_x2,debug_x2_scale,(200,200)); debug_shadow_x2=debug_scale_about_hotspot(fs_x2,debug_x2_scale,(200,200))
    debug_main_x2.save(root/"praetorian-front3q-debug120-x2.png"); debug_path_x2=root/"rome2aoe2_praetorian_front3q_debug60_x2.sld"; write_sld(debug_main_x2,debug_shadow_x2,debug_path_x2,encoder(),(200,200))
    report={"format":"rome2aoe2.sld-runtime-diagnostics","version":1,"praetorian_identical_facets":outputs,
            "rgb_control":{"paths":[color_sld.name,color_sld_x2.name],"frames":16,"facet_count":16},"readable_direction":{"index":4,"camera_azimuth_degrees":315.0,"paths":[front_path.name,front_path_x2.name]},
            "debug_scale":{"target_logical_height_pixels":60,"paths":[debug_path.name,debug_path_x2.name]},"alpha_threshold":128,
            "front3q_color_metrics":{"bleed":color_metrics(fm,bleed),"directxtex":color_metrics(fm,dds_decoded),"sld":color_metrics(fm,sld_decoded)}}
    (root/"runtime-diagnostics.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); return 0
if __name__=="__main__": raise SystemExit(main())
