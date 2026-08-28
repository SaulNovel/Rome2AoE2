"""Compose review sheets from the FAST whole-unit lighting audit."""
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'build/python-deps/pillow'))
from PIL import Image,ImageDraw,ImageFont
FONT=ImageFont.load_default()
def tile(path,label,scale=.5,crop=None):
 im=Image.open(path).convert('RGBA');im=im.crop(crop) if crop else im;im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);out=Image.new('RGBA',(im.width,im.height+20),(18,20,22,255));out.alpha_composite(im,(0,20));ImageDraw.Draw(out).text((4,5),label,font=FONT,fill='white');return out
def grid(items,cols,path):
 rows=math.ceil(len(items)/cols);w=max(i.width for i in items);h=max(i.height for i in items);out=Image.new('RGB',(cols*w,rows*h),(12,14,16))
 for n,item in enumerate(items):out.paste(item.convert('RGB'),((n%cols)*w,(n//cols)*h))
 out.save(path)
def yaw(record):return record.get('yaw',record.get('facet_root_yaw_degrees'))
def main():
 p=argparse.ArgumentParser();p.add_argument('report',type=Path);a=p.parse_args();doc=json.loads(a.report.read_text());root=a.report.parent;available=doc.get('candidates',doc.get('variants'));preferred=('v5-control','symmetric-normalization','lift-only-normalization','complement-weak','complement-medium','complement-strong','orbit-camera-key','orbit-full-studio');candidates=[c for c in preferred if c in available]+[c for c in available if c not in preferred];by={(r['candidate'],r['direction']):r for r in doc['records']}
 for c in candidates:
  grid([tile(by[c,d]['output'],f'D{d} yaw {yaw(by[c,d]):.1f}') for d in range(16)],4,root/f'{c}-all-16-x2.png')
  order=[x for d in range(8) for x in (d,d+8)];grid([tile(by[c,d]['output'],f'D{d} yaw {yaw(by[c,d]):.1f}') for d in order],2,root/f'{c}-opposite-pairs-x2.png')
  grid([tile(by[c,d]['output'],f'D{d}',.25) for d in range(16)],4,root/f'{c}-game-scale.png')
 crops={'helmet-crest':(110,35,290,175),'body-armour':(95,120,305,310),'shield':(45,95,225,330),'sword':(175,100,355,330)}
 for label,crop in crops.items():
  items=[]
  for d in (2,6,10,14):
   for c in candidates:items.append(tile(by[c,d]['output'],f'{c} D{d}',1,crop))
  grid(items,len(candidates),root/f'close-{label}-candidates-x2.png')
 # Direct human comparison: candidates are columns, canonical directions rows.
 prefix='v5-symmetric-lift-only' if 'symmetric-normalization' in candidates else ('v5-orbit-key-orbit-studio' if 'orbit-camera-key' in candidates else 'v5-weak-medium-strong')
 grid([tile(by[c,d]['output'],f'{c} D{d}',.5) for d in range(16) for c in candidates],len(candidates),root/f'{prefix}-all-16.png')
 focus=(2,3,4,5,6,10,11,12,13,14)
 grid([tile(by[c,d]['output'],f'{c} D{d}',.65) for d in focus for c in candidates],len(candidates),root/'dark-and-bright-hemisphere-focus.png')
 grid([tile(by[c,d]['output'],f'{c} D{d}',.25) for d in focus for c in candidates],len(candidates),root/'game-scale-focus-comparison.png')
 pair_order=[x for d in range(8) for x in (d,d+8)]
 grid([tile(by[c,d]['output'],f'{c} D{d}',.4) for d in pair_order for c in candidates],len(candidates),root/f'{prefix}-opposite-pairs.png')
if __name__=='__main__':main()
