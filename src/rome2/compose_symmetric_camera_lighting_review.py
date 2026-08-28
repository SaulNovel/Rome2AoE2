"""Review sheets for symmetric camera-light and contributor decomposition audit."""
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'build/python-deps/pillow'))
from PIL import Image,ImageDraw,ImageFont
FONT=ImageFont.load_default()
def tile(path,label,scale=.5,crop=None):
 im=Image.open(path).convert('RGBA');im=im.crop(crop) if crop else im;im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);out=Image.new('RGB',(im.width,im.height+20),(15,17,19));out.paste(im.convert('RGB'),(0,20));ImageDraw.Draw(out).text((4,5),label,font=FONT,fill='white');return out
def grid(items,cols,path):
 w=max(x.width for x in items);h=max(x.height for x in items);out=Image.new('RGB',(cols*w,math.ceil(len(items)/cols)*h),(10,12,14))
 for i,item in enumerate(items):out.paste(item,((i%cols)*w,(i//cols)*h))
 out.save(path)
def main():
 p=argparse.ArgumentParser();p.add_argument('audit',type=Path);a=p.parse_args();d=json.loads(a.audit.read_text());out=a.audit.parent;names=[]
 for r in d['records']:
  if r['candidate'] not in names:names.append(r['candidate'])
 by={(r['candidate'],r['direction']):r for r in d['records']};order=[x for q in range(8) for x in (q,q+8)]
 grid([tile(by[n,q]['output'],f'{n} D{q}') for q in range(16) for n in names],len(names),out/'all-16-comparison-x2.png');grid([tile(by[n,q]['output'],f'{n} D{q}',.35) for q in range(16) for n in names],len(names),out/'all-16-comparison-game-scale.png');grid([tile(by[n,q]['output'],f'{n} D{q}',.42) for q in order for n in names],len(names),out/'opposite-pair-comparison.png')
 focus=(2,3,4,5,6,10,11,12,13,14);grid([tile(by[n,q]['output'],f'{n} D{q}',.65) for q in focus for n in names],len(names),out/'d2-d6-vs-d10-d14-focus.png')
 crops={'body-armour':(95,115,305,315),'helmet-crest':(110,35,290,180),'shield':(45,90,225,335),'sword':(175,95,355,335)}
 for label,crop in crops.items():grid([tile(by[n,q]['output'],f'{n} D{q}',1,crop) for q in (2,4,6,10,12,14) for n in names],len(names),out/f'close-{label}.png')
 dec={(r['kind'],r['name'],r['direction']):r for r in d['decomposition']};layers=('direct-directional-diffuse','direct-directional-specular','six-lobe-ambient','environment-reflection','orientation-independent-readability','v4-shield-readability','v5-weapon-readability');abl=('direct-key-only','ambient-only','environment-only','direct-plus-ambient','direct-plus-environment','complete')
 grid([tile(dec['layer',n,q]['output'],f'{n} D{q}',.7) for q in d['selected_decomposition_directions'] for n in layers],len(layers),out/'linear-component-aov-sheet.png');grid([tile(dec['ablation',n,q]['output'],f'{n} D{q}',.7) for q in d['selected_decomposition_directions'] for n in abl],len(abl),out/'controlled-ablation-sheet.png')
 grid([tile(dec['ablation',n,q]['output'],f'{n} D{q}',1,(90,45,310,330)) for q in d['selected_decomposition_directions'] for n in abl],len(abl),out/'controlled-ablation-body-closeups.png')
if __name__=='__main__':main()
