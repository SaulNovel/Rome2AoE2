"""Compose the three runtime-resolution representative renders."""
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];R=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"/"renders"
def main():
 labels=("Hastati - rom_rome","Eastern Spearman - rom_parthia","Praetorian - base Roman VMD")
 names=("hastati","eastern-spearman","praetorian");sheet=Image.new("RGBA",(1200,470),(38,42,38,255));draw=ImageDraw.Draw(sheet);font=ImageFont.load_default(18)
 for i,(name,label) in enumerate(zip(names,labels)):
  im=Image.open(R/f"{name}-runtime-resolved-representative.png").convert("RGBA");box=im.getbbox();crop=im.crop(box).resize((320,320),Image.Resampling.LANCZOS) if box else im;sheet.alpha_composite(crop,(40+i*400,45));draw.text((40+i*400,385),label,fill="white",font=font);draw.text((40+i*400,415),"Representative seed; see effective-unit.json",fill=(210,210,210),font=font)
 sheet.convert("RGB").save(R/"effective-unit-diagnostics.png")
if __name__=="__main__":main()
