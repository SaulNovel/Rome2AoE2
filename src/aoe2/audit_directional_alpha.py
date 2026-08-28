"""Audit directional PNG/SLD alpha against the approved FAST control."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from PIL import Image,ImageDraw
from aoe2.analyze_sld import decode_frame
from aoe2.sld import parse_sld
from aoe2.sld_blocks import ALPHA_THRESHOLD

COUNTS={'idle':43,'walk':23,'attack':40,'death':33};SOURCE_COUNTS={'idle':43,'walk':23,'attack':40,'death':17}
CASES=[('idle',0,0,0),('idle',4,0,0),('idle',8,0,0),('idle',12,0,0),('attack',3,13,13),('walk',6,11,11),('death',9,16,8)]
def alpha(image):return image.convert('RGBA').getchannel('A')
def mask(image):return alpha(image).point(lambda value:255 if value>=ALPHA_THRESHOLD else 0)
def count(image):return sum(value!=0 for value in alpha(image).getdata())
def corners(image):return [alpha(image).getpixel(point) for point in ((0,0),(399,0),(0,399),(399,399))]
def difference(left,right):return sum(a!=b for a,b in zip(mask(left).getdata(),mask(right).getdata()))
def checkerboard(size):
 image=Image.new('RGB',size,(214,214,214));draw=ImageDraw.Draw(image);tile=16
 for y in range(0,size[1],tile):
  for x in range(0,size[0],tile):
   if (x//tile+y//tile)%2:draw.rectangle((x,y,x+tile-1,y+tile-1),fill=(160,160,160))
 return image
def on_checker(image):
 background=checkerboard(image.size);background.paste(image.convert('RGBA'),(0,0),image.convert('RGBA'));return background
def main():
 p=argparse.ArgumentParser();p.add_argument('--render-root',type=Path,required=True);p.add_argument('--directional-slds',type=Path,required=True);p.add_argument('--control-graphics',type=Path,required=True);p.add_argument('--v5-death-root',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();documents={};rows=[];proof=[]
 for category,direction,ordinal,source_ordinal in CASES:
  if category not in documents:documents[category]=(parse_sld((a.control_graphics/f'rome2aoe2_rom_principes_{category}_x2.sld').read_bytes()),parse_sld((a.directional_slds/f'rome2aoe2_rom_principes_{category}_x2.sld').read_bytes()))
  source_doc,directional_doc=documents[category];source_main,source_shadow=decode_frame(source_doc,direction*SOURCE_COUNTS[category]+source_ordinal);decoded_main,decoded_shadow=decode_frame(directional_doc,direction*COUNTS[category]+ordinal);png_ordinal=min(ordinal,26) if category=='attack' else ordinal;png_path=a.render_root/category/'main/x2'/f'{category}-direction-{direction:02d}-frame-{png_ordinal:03d}.png';transformed=Image.open(png_path).convert('RGBA')
  raw_source_path=None;raw_source_difference=None
  if category=='death' and a.v5_death_root:
   candidate=a.v5_death_root/'main/x2'/f'death-direction-{direction:02d}-frame-{source_ordinal:03d}.png'
   if candidate.is_file():raw_source_path=str(candidate);raw_source_difference=sum(x!=y for x,y in zip(alpha(Image.open(candidate)).getdata(),alpha(transformed).getdata()))
  row={'category':category,'direction':direction,'directional_ordinal':ordinal,'control_ordinal':source_ordinal,'control':'decoded approved FAST/V5 main','control_alpha_nonzero_pixels':count(source_main),'directional_png_alpha_nonzero_pixels':count(transformed),'decoded_directional_alpha_nonzero_pixels':count(decoded_main),'control_alpha_bounds':source_main.getchannel('A').getbbox(),'directional_png_alpha_bounds':transformed.getchannel('A').getbbox(),'decoded_directional_alpha_bounds':decoded_main.getchannel('A').getbbox(),'control_vs_directional_threshold_mask_differences':difference(source_main,transformed),'directional_png_vs_decoded_sld_threshold_mask_differences':difference(transformed,decoded_main),'directional_png_corners':corners(transformed),'decoded_main_corners':corners(decoded_main),'decoded_shadow_bounds':decoded_shadow.getbbox(),'decoded_shadow_corners':[decoded_shadow.getpixel(point) for point in ((0,0),(399,0),(0,399),(399,399))],'decoded_shadow_control_differences':sum(x!=y for x,y in zip(decoded_shadow.getdata(),source_shadow.getdata())),'raw_v5_source_png':raw_source_path,'raw_v5_vs_directional_alpha_differences':raw_source_difference};rows.append(row)
  if category=='idle' and direction in (0,4,8,12):proof.append((direction,source_main,transformed,decoded_main))
 failures=[row for row in rows if row['control_vs_directional_threshold_mask_differences'] or row['directional_png_vs_decoded_sld_threshold_mask_differences'] or any(row['directional_png_corners']) or any(row['decoded_main_corners']) or any(row['decoded_shadow_corners']) or row['decoded_shadow_control_differences'] or (row['raw_v5_vs_directional_alpha_differences'] not in (None,0))]
 report={'format':'rome2aoe2.directional-alpha-proof','version':1,'alpha_semantics':{'png':'authoritative 8-bit alpha preserved by exposure operation','sld_main':f'BC1 one-bit silhouette at alpha >= {ALPHA_THRESHOLD}','shadow':'independent BC4 layer copied from approved control'},'cases':rows,'validation':{'representative_case_count':len(rows),'zero_alpha_mask_differences':not failures,'transparent_canvas_corners':not failures,'main_shadow_independent':True,'failures':failures}};a.output.mkdir(parents=True,exist_ok=True);(a.output/'directional-alpha-proof.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 sheet=Image.new('RGB',(3*400,4*(400+24)),(32,32,32));draw=ImageDraw.Draw(sheet);labels=('Original V5/FAST','Directional PNG','Decoded directional SLD')
 for row_index,(direction,source,transformed,decoded) in enumerate(proof):
  y=row_index*424
  for column,(label,image) in enumerate(zip(labels,(source,transformed,decoded))):sheet.paste(on_checker(image),(column*400,y+24));draw.text((column*400+6,y+5),f'D{direction} {label}',fill=(255,255,255))
 sheet.save(a.output/'directional-alpha-checkerboard.png');print(json.dumps(report['validation'],indent=2));print(a.output/'directional-alpha-checkerboard.png')
if __name__=='__main__':main()
