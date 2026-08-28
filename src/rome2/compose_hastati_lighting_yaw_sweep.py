"""Compose enlarged ignored contact sheets for the coherent yaw sweep."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"build/python-deps/pillow"))
from PIL import Image,ImageDraw

OUT=ROOT/"build/local-integration/rome2/runtime-parity-proof"
YAWS=tuple(range(0,360,45))
UNIT=(1390,850,1810,1660)
REGIONS={"helmet":(1470,900,1620,1100),"cuirass":(1420,1020,1660,1275),"tunic":(1420,1180,1670,1460),"skin":(1450,1070,1660,1610)}

def fit(im,size):
    q=im.copy();q.thumbnail(size,Image.Resampling.LANCZOS);c=Image.new("RGB",size,(8,8,8));c.paste(q,((size[0]-q.width)//2,(size[1]-q.height)//2));return c

def main():
    ims={yaw:Image.open(OUT/f"lighting-yaw-{yaw:03d}.png").convert("RGB") for yaw in YAWS}
    cell=(520,720);sheet=Image.new("RGB",(cell[0]*4,cell[1]*2+50),(18,20,22));d=ImageDraw.Draw(sheet)
    d.text((16,15),"Hastati facet 03 - coherent recovered-environment yaw (identical scale)",fill="white")
    for i,yaw in enumerate(YAWS):
        x=(i%4)*cell[0];y=50+(i//4)*cell[1];sheet.paste(fit(ims[yaw].crop(UNIT),cell),(x,y));d.text((x+12,y+10),f"yaw {yaw:03d}",fill="white")
    sheet.save(OUT/"lighting-yaw-contact-sheet.png")
    cw,ch=280,360;crops=Image.new("RGB",(cw*8,ch*len(REGIONS)+45),(18,20,22));d=ImageDraw.Draw(crops);d.text((12,12),"Material crops: helmet / cuirass / tunic / skin",fill="white")
    for row,(name,box) in enumerate(REGIONS.items()):
        for col,yaw in enumerate(YAWS):
            x=col*cw;y=45+row*ch;crops.paste(fit(ims[yaw].crop(box),(cw,ch)),(x,y));d.text((x+8,y+8),f"{name} {yaw:03d}",fill="white")
    crops.save(OUT/"lighting-yaw-material-crops.png")

if __name__=="__main__":main()
