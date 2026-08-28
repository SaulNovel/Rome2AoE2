import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'build/python-deps/pillow'))
from PIL import Image,ImageDraw,ImageFont
F=ImageFont.load_default()
def main():
 p=argparse.ArgumentParser();p.add_argument('report',type=Path);a=p.parse_args();d=json.loads(a.report.read_text());rows=d['records'];tile=150;head=20;out=Image.new('RGB',(tile*2,(tile+head)*len(rows)),(15,17,19));draw=ImageDraw.Draw(out)
 for y,r in enumerate(rows):
  for x,k in enumerate(('v5','lift')):
   im=Image.open(r['outputs'][k]['path']).convert('RGBA');im.thumbnail((tile,tile),Image.Resampling.LANCZOS);px=x*tile;py=y*(tile+head);out.paste((20,22,24),(px,py,px+tile,py+tile+head));out.paste(im.convert('RGB'),(px+(tile-im.width)//2,py+head));draw.text((px+3,py+4),f"{r['category']} {r['phase']} D{r['direction']} {k}",font=F,fill='white')
 path=a.report.parent/'animation-stability-v5-vs-lift-only.png';out.save(path);print(path)
if __name__=='__main__':main()
