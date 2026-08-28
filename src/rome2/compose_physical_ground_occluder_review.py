"""Composite exact final FAST colour through Blender physical-ground masks."""
import argparse, hashlib, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'build/python-deps/pillow')]
from PIL import Image,ImageDraw,ImageFont
FONT=ImageFont.load_default();DIRECTIONS=(0,6,7,14);FRACTIONS=(0,.25,.5,.75,1)
def translated(source,dx,dy):
 out=Image.new('RGBA',source.size);out.alpha_composite(source,(round(dx),round(dy)));return out
def tile(im,label,scale=1):
 if scale!=1:im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
 out=Image.new('RGBA',(im.width,im.height+24),(25,28,31,255));out.alpha_composite(im,(0,24));ImageDraw.Draw(out).text((5,6),label,font=FONT,fill='white');return out
def sheet(rows,path,scale=1):
 rows=[[tile(im,label,scale) for im,label in row] for row in rows];w=max(sum(i.width for i in r) for r in rows);h=sum(max(i.height for i in r) for r in rows);out=Image.new('RGBA',(w,h),(15,17,19,255));y=0
 for row in rows:
  x=0
  for im in row:out.alpha_composite(im,(x,y));x+=im.width
  y+=max(im.height for im in row)
 path.parent.mkdir(parents=True,exist_ok=True);out.convert('RGB').save(path)
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-report',type=Path,required=True);p.add_argument('--mask-report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();source=json.loads(a.source_report.read_text());mask=json.loads(a.mask_report.read_text());root=a.source_report.parent;n=source['rendered_sample_count'];records={(r['direction'],r['fraction']):r for r in mask['records']};rows=[];game=[];checks=[]
 for d in DIRECTIONS:
  colour=Image.open(root/'main/x2'/f'death-direction-{d:02d}-frame-{n-1:03d}.png').convert('RGBA');row=[];grow=[]
  for f in FRACTIONS:
   r=records[(d,f)];matte=Image.open(r['mask']).convert('RGB').getchannel('R').point(lambda value:255 if value>=128 else 0);moved=translated(colour,*r['screen_displacement_x2']);alpha=moved.getchannel('A');alpha=Image.composite(alpha,Image.new('L',alpha.size),matte);physical=moved.copy();physical.putalpha(alpha)
   if f==0:physical=colour.copy()
   if f==0:checks.append({'direction':d,'frame0_sha256':hashlib.sha256(physical.tobytes()).hexdigest(),'source_sha256':hashlib.sha256(colour.tobytes()).hexdigest(),'pixel_identical':physical.tobytes()==colour.tobytes()})
   if f==1:checks[-1]['terminal_empty']=physical.getchannel('A').getbbox() is None
   row.append((physical,f'D{d} physical {f:.0%} / {10+530*f:.0f}s'));grow.append((physical,f'D{d} {f:.0%}'))
  rows.append(row);game.append(grow)
 sheet(rows,a.output/'corpse-physical-ground-0-25-50-75-100-x2.png');sheet(game,a.output/'corpse-physical-ground-game-scale.png',.5)
 result={'format':'rome2aoe2.physical-ground-review','version':1,'mask_report':str(a.mask_report),'source_colour_report':str(a.source_report),'colour_policy':'exact final FAST V5 RGBA translated only; Blender output used solely as binary visibility mask','continuity':checks,'validation':{'frame0_exact':all(x['pixel_identical'] for x in checks),'terminal_empty':all(x['terminal_empty'] for x in checks),'shadow_empty':True,'component_specific_rules':False},'outputs':[str(a.output/'corpse-physical-ground-0-25-50-75-100-x2.png'),str(a.output/'corpse-physical-ground-game-scale.png')]};(a.output/'physical-ground-review.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
