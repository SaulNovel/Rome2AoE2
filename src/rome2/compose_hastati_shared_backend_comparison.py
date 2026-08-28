"""Compose ignored production-bridge before/after crops and measurements."""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"build/python-deps/pillow"))
from PIL import Image, ImageChops, ImageDraw, ImageStat
OUT=ROOT/"build/local-integration/rome2/runtime-parity-proof"
CROPS={
    "skin":(1460,1080,1650,1600),
    "cuirass":(1430,1030,1650,1270),
    "helmet":(1480,900,1615,1100),
    "shield":(1610,1040,1790,1570),
    "tunic":(1430,1190,1660,1450),
}

def fit(im,size):
    q=im.copy();q.thumbnail(size,Image.Resampling.NEAREST)
    canvas=Image.new("RGB",size,(15,15,15));canvas.paste(q,((size[0]-q.width)//2,(size[1]-q.height)//2));return canvas

def main():
    before=Image.open(OUT/"runtime-parity-f03-pre-shared-backend.png").convert("RGB")
    after=Image.open(OUT/"runtime-parity-f03.png").convert("RGB")
    canvas=Image.new("RGB",(1800,2300),(18,20,22));draw=ImageDraw.Draw(canvas)
    draw.text((20,15),"Production bridge: Blender node preparation (left) vs shared replay preparation (right)",fill="white")
    draw.text((300,48),"BEFORE",fill=(220,220,220));draw.text((1200,48),"SHARED BACKEND",fill=(220,220,220))
    report={"format":"rome2aoe2.shared-material-backend-comparison","version":1,"regions":{}}
    for row,(name,box) in enumerate(CROPS.items()):
        a=fit(before.crop(box),(850,400));b=fit(after.crop(box),(850,400));y=80+row*440
        canvas.paste(a,(20,y));canvas.paste(b,(930,y));draw.text((22,y+5),name,fill="white")
        diff=ImageChops.difference(before.crop(box),after.crop(box));stat=ImageStat.Stat(diff)
        report["regions"][name]={"box":list(box),"mean_absolute_rgb_change":sum(stat.mean)/(3*255),"max_absolute_rgb_change":max(stat.extrema[i][1] for i in range(3))/255}
    canvas.save(OUT/"shared-material-backend-before-after.png")
    (OUT/"shared-material-backend-comparison.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":main()
