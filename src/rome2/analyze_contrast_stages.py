"""Measure contrast loss from Blender output through downsample and decoded BC1."""
from __future__ import annotations
import json, statistics, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"build"/"python-deps"/"pillow")]
from PIL import Image
from aoe2.analyze_sld import decode_frame
from aoe2.sld import parse_sld
from aoe2.generate_v4_ingame_proof import downsample_about_feet

BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
RENDERS=BASE/"renders-set-a"
PC=BASE/"ROME2AOE2_INFANTRY_CALIBRATION_SET_A"/"resources"/"_common"/"drs"/"graphics"
UNITS={slug:f"rome2_seta_{slug.replace('-','_')}_l11" for slug in ("hastati","principes","triarii","velites","celtic-warriors")}

def luminance(rgb):
    c=[v/255 for v in rgb]; c=[v/12.92 if v<=.04045 else ((v+.055)/1.055)**2.4 for v in c]
    return 255*(.2126*c[0]+.7152*c[1]+.0722*c[2])
def percentile(v,p):
    a=sorted(v); x=(len(a)-1)*p; lo=int(x); hi=min(lo+1,len(a)-1); return a[lo]*(hi-x)+a[hi]*(x-lo)
def metric(im):
    im=im.convert("RGBA"); px=im.load(); values=[]; sats=[]; gradients=[]
    for y in range(im.height):
        for x in range(im.width):
            p=px[x,y]
            if p[3]<=8: continue
            values.append(luminance(p[:3])); mx=max(p[:3]); sats.append(0 if not mx else (mx-min(p[:3]))/mx)
            if x+1<im.width and px[x+1,y][3]>8: gradients.append(abs(luminance(p[:3])-luminance(px[x+1,y][:3])))
            if y+1<im.height and px[x,y+1][3]>8: gradients.append(abs(luminance(p[:3])-luminance(px[x,y+1][:3])))
    return {"pixels":len(values),"mean_luminance":round(statistics.fmean(values),3),"p10":round(percentile(values,.1),3),"p50":round(percentile(values,.5),3),"p90":round(percentile(values,.9),3),"local_range_p90_p10":round(percentile(values,.9)-percentile(values,.1),3),"luminance_stddev":round(statistics.pstdev(values),3),"mean_saturation":round(statistics.fmean(sats),5),"mean_neighbor_contrast":round(statistics.fmean(gradients),3)}
def main():
    rows=[]
    for slug,stem in UNITS.items():
        high=Image.open(RENDERS/f"{slug}-L11.png").convert("RGBA")
        pre=downsample_about_feet(high,200,50,(100,100))
        decoded,_=decode_frame(parse_sld((PC/f"{stem}_x1.sld").read_bytes()))
        stages={"high_resolution":metric(high),"pre_sld_200px":metric(pre),"decoded_x1_bc1":metric(decoded)}
        pre_m=stages["pre_sld_200px"]; dec_m=stages["decoded_x1_bc1"]
        stages["bc1_delta"]={k:round(dec_m[k]-pre_m[k],5) for k in ("mean_luminance","local_range_p90_p10","luminance_stddev","mean_saturation","mean_neighbor_contrast")}
        rows.append({"unit":slug,"stages":stages})
    out={"format":"rome2aoe2.contrast-stage-analysis","version":1,"pipeline":["Blender 800px Standard exposure +0.65","Lanczos downsample_about_feet to x1 200px canvas/50px unit","strict decoded native SLD BC1 main layer"],"units":rows}
    (BASE/"contrast-stage-analysis.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps(out,indent=2))
if __name__=="__main__": main()
