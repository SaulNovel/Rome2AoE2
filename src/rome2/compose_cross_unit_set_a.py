"""Compose Set A sheets and calculate alpha/material-mask diagnostics."""
import json, math, statistics, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"build"/"python-deps"/"pillow"))
from PIL import Image, ImageDraw, ImageFont, ImageStat

BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";R=BASE/"renders-set-a"
UNITS=[("hastati","Hastati"),("principes","Principes"),("triarii","Triarii"),("velites","Velites"),("celtic-warriors","Celtic Warriors")];LIGHTS=["L06","L10","L11"]
# Observed Standard-transform output of the diagnostic emission colors at +0.65.
PALETTE={"skin":(255,137,177),"bronze":(255,255,50),"iron/steel":(61,177,255),"wood":(255,174,50),"cloth":(79,255,120),"leather":(153,84,43),"hair/fur":(255,110,255),"other":(137,137,137),"unknown":(255,0,255)}
FONT=ImageFont.load_default()
def bbox(im): return im.getchannel("A").getbbox()
def fit(im,size,pad=12):
    b=bbox(im); crop=im.crop(b) if b else im; crop.thumbnail((size[0]-2*pad,size[1]-2*pad),Image.Resampling.LANCZOS); out=Image.new("RGBA",size,(22,24,27,255));out.alpha_composite(crop,((size[0]-crop.width)//2,(size[1]-crop.height)//2));return out
def label(draw,xy,text): draw.text(xy,text,font=FONT,fill=(240,240,240,255))
def sheet(paths,rows,cols,cell,out,title):
    top=28;im=Image.new("RGBA",(cols*cell[0],top+rows*cell[1]),(18,19,22,255));d=ImageDraw.Draw(im);label(d,(8,8),title)
    for r,c,path,caption in paths:
        tile=fit(Image.open(path).convert("RGBA"),(cell[0],cell[1]-20));im.alpha_composite(tile,(c*cell[0],top+r*cell[1]));label(d,(c*cell[0]+6,top+(r+1)*cell[1]-18),caption)
    im.convert("RGB").save(out)
def lum(rgb):
    v=[x/255 for x in rgb];lin=[x/12.92 if x<=.04045 else ((x+.055)/1.055)**2.4 for x in v];return 255*(.2126*lin[0]+.7152*lin[1]+.0722*lin[2])
def percentile(xs,p):
    if not xs:return None
    a=sorted(xs);q=(len(a)-1)*p;i=int(q);return a[i] if i==len(a)-1 else a[i]*(i+1-q)+a[i+1]*(q-i)
def nearest(rgb): return min(PALETTE,key=lambda k:sum((rgb[i]-PALETTE[k][i])**2 for i in range(3)))
def metrics(slug,light):
    im=Image.open(R/f"{slug}-{light}.png").convert("RGBA");false=Image.open(R/f"{slug}-material-classes.png").convert("RGBA");px=list(im.getdata());fp=list(false.getdata());active=[i for i,p in enumerate(px) if p[3]>8];ls=[lum(px[i][:3]) for i in active]
    sats=[]
    for i in active:
        r,g,b=[x/255 for x in px[i][:3]];mx=max(r,g,b);sats.append(0 if mx==0 else (mx-min(r,g,b))/mx)
    classes={k:[] for k in PALETTE}
    for i in active:
        if fp[i][3]>8: classes[nearest(fp[i][:3])].append(lum(px[i][:3]))
    return {"unit":dict(UNITS)[slug],"light":light,"whole_unit_luminance":round(statistics.fmean(ls),2),"p10":round(percentile(ls,.1),2),"p50":round(percentile(ls,.5),2),"p90":round(percentile(ls,.9),2),"saturation":round(statistics.fmean(sats),4),"clipping_percent":round(100*sum(max(px[i][:3])>=250 for i in active)/len(active),3),"local_contrast_stddev":round(statistics.pstdev(ls),2),"skin_luminance":round(statistics.fmean(classes["skin"]),2) if classes["skin"] else None,"bronze_luminance":round(statistics.fmean(classes["bronze"]),2) if classes["bronze"] else None,"iron_steel_luminance":round(statistics.fmean(classes["iron/steel"]),2) if classes["iron/steel"] else None,"wood_luminance":None,"wood_note":"no defensibly isolated wood material; all Set A shafts are mixed with metal","cloth_luminance":round(statistics.fmean(classes["cloth"]),2) if classes["cloth"] else None,"shield_luminance":None,"shield_note":"mixed shield material shares UNKNOWN mask with mixed weapons; no defensible isolated metric"}
def gameplay():
    cw,ch=220,220;top=28;out=Image.new("RGBA",(3*cw,top+5*ch),(44,48,43,255));d=ImageDraw.Draw(out);label(d,(8,8),"Set A at AoE2 x1 logical height (50 px)")
    for r,(slug,name) in enumerate(UNITS):
        for c,light in enumerate(LIGHTS):
            src=Image.open(R/f"{slug}-{light}.png").convert("RGBA");b=bbox(src);crop=src.crop(b);w=max(1,round(crop.width*50/crop.height));crop=crop.resize((w,50),Image.Resampling.LANCZOS);x=c*cw+(cw-w)//2;y=top+r*ch+95;out.alpha_composite(crop,(x,y));label(d,(c*cw+5,top+r*ch+5),f"{name} {light}")
    out.convert("RGB").save(BASE/"render-comparison-set-a-gameplay-scale.png")
def main():
    sheet([(r,0,R/f"{s}-material-classes.png",n) for r,(s,n) in enumerate(UNITS)],5,1,(420,330),BASE/"material-classes-set-a.png","Set A material classes")
    sheet([(r,c,R/f"{s}-{l}.png",f"{n} {l}") for r,(s,n) in enumerate(UNITS) for c,l in enumerate(LIGHTS)],5,3,(340,330),BASE/"render-comparison-set-a.png","Set A common-light comparison")
    gameplay();rows=[metrics(s,l) for s,_ in UNITS for l in LIGHTS];(BASE/"metrics-set-a.json").write_text(json.dumps({"format":"rome2aoe2.metrics-set-a","version":1,"notes":["Metrics use non-transparent pixels and diagnostic false-color class masks.","No wood-only source material exists in Set A weapons; mixed shafts remain UNKNOWN."],"renders":rows},indent=2,sort_keys=True)+"\n");print(json.dumps(rows,indent=2))
if __name__=="__main__":main()
