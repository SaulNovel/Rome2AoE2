"""Strict deterministic SLDX v4 inspection command."""
from __future__ import annotations
import argparse, json
from pathlib import Path
from PIL import Image
from .sld import LAYER_MAIN, LAYER_SHADOW, parse_sld
from .sld_blocks import decode_bc1_block, decode_bc4_block

def decode_frame(sld, frame_index: int = 0) -> tuple[Image.Image, Image.Image]:
    frame=sld.frames[frame_index]
    main=Image.new("RGBA",(frame.canvas_width,frame.canvas_height)); shadow=Image.new("L",main.size)
    for layer in frame.layers:
        if layer.layer_type not in (LAYER_MAIN,LAYER_SHADOW): continue
        width=layer.offset_x2-layer.offset_x1; columns=(width+3)//4; cursor=0; block_index=0
        for skip,draw in layer.commands:
            cursor += skip
            for _ in range(draw):
                x=layer.offset_x1+(cursor%columns)*4; y=layer.offset_y1+(cursor//columns)*4
                decoded=decode_bc1_block(layer.blocks[block_index]) if layer.layer_type==LAYER_MAIN else decode_bc4_block(layer.blocks[block_index])
                for row in range(4):
                    for column in range(4):
                        if x+column < frame.canvas_width and y+row < frame.canvas_height:
                            (main if layer.layer_type==LAYER_MAIN else shadow).putpixel((x+column,y+row),decoded[row][column])
                cursor += 1; block_index += 1
    return main,shadow

def analyze(data: bytes, filename: str) -> dict:
    sld = parse_sld(data)
    return {"format":"rome2aoe2.sld-inspection","version":1,"file":Path(filename).name,
            "sld_version":sld.version,"frame_count":len(sld.frames),"facet_count":sld.facet_count,
            "frames":[{"index":frame.frame_index,"canvas":[frame.canvas_width,frame.canvas_height],
                       "hotspot":[frame.center_x,frame.center_y],"layer_mask":frame.frame_type,
                       "layers":[{"type":layer.layer_type,"bounds":[layer.offset_x1,layer.offset_y1,layer.offset_x2,layer.offset_y2],
                                  "command_count":len(layer.commands),"block_count":len(layer.blocks)} for layer in frame.layers]}
                      for frame in sld.frames]}
def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("input"); parser.add_argument("--output"); parser.add_argument("--decode-root")
    args=parser.parse_args(); path=Path(args.input); result=json.dumps(analyze(path.read_bytes(),path.name),indent=2,sort_keys=True)+"\n"
    if args.output: Path(args.output).write_text(result,encoding="utf-8")
    else: print(result,end="")
    if args.decode_root:
        root=Path(args.decode_root); root.mkdir(parents=True,exist_ok=True); main_image,shadow_image=decode_frame(parse_sld(path.read_bytes()))
        main_image.save(root/"main.png"); shadow_image.save(root/"shadow.png")
    return 0
if __name__ == "__main__": raise SystemExit(main())
