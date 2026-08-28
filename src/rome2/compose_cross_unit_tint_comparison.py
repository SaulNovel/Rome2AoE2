"""Compose the single-light seven-unit neutral/player-colour comparison."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"build"/"python-deps"/"pillow"))
from PIL import Image,ImageDraw,ImageFont
BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";R=BASE/"renders-set-a";M=BASE/"tint-masks"
UNITS=[("hastati","Hastati"),("principes","Principes"),("triarii","Triarii"),("velites","Velites"),("hoplites","Hoplites"),("celtic-warriors","Celtic Warriors"),("eastern-spearmen","Eastern Spearmen")]
COLS=[("Neutral",None),("AoE blue preview",(45,90,230)),("AoE red preview",(220,45,40))]
def tint(base,mask,color):
 out=base.copy();p=out.load();m=mask.load()
 for y in range(out.height):
  for x in range(out.width):
   if p[x,y][3]<=8:continue
   cov=max(m[x,y][:3])/255
   if cov<=.01:continue
   lum=(.2126*p[x,y][0]+.7152*p[x,y][1]+.0722*p[x,y][2])/255
   p[x,y]=(round(p[x,y][0]*(1-cov)+color[0]*lum*cov),round(p[x,y][1]*(1-cov)+color[1]*lum*cov),round(p[x,y][2]*(1-cov)+color[2]*lum*cov),p[x,y][3])
 return out
def main():
 cell=(330,310);top=32;out=Image.new("RGB",(3*cell[0],top+7*cell[1]),(26,29,32));d=ImageDraw.Draw(out);font=ImageFont.load_default();d.text((8,8),"Seven-unit L11 comparison — previews only; AoE2 owns runtime player palette",fill="white",font=font)
 for row,(slug,name) in enumerate(UNITS):
  base=Image.open(R/f"{slug}-L11.png").convert("RGBA");mask=Image.open(M/f"{slug}-mask-rgb.png").convert("RGBA")
  for col,(label,color) in enumerate(COLS):
   im=base if color is None else tint(base,mask,color);box=im.getchannel("A").getbbox();crop=im.crop(box);crop.thumbnail((250,255),Image.Resampling.LANCZOS);x=col*cell[0]+(cell[0]-crop.width)//2;y=top+row*cell[1]+30;out.paste(crop,(x,y),crop);d.text((col*cell[0]+7,top+row*cell[1]+7),f"{name} — {label}",fill="white",font=font)
 out.save(BASE/"render-comparison-seven-unit-neutral-blue-red.png")
if __name__=="__main__":main()
