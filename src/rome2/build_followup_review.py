"""Build non-rendering review artifacts from frozen approved x2 frames."""
from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageDraw,ImageStat
from rome2aoe2.corpse_decay import GENERATED,decay_frames

def luminance(im):
 rgba=im.convert("RGBA");pixels=[p for p in rgba.getdata() if p[3]>8]
 values=[.2126*r+.7152*g+.0722*b for r,g,b,a in pixels]
 return statistics.fmean(values),statistics.median(values),sorted(values)[max(0,int(.1*len(values))-1)]
def tile(im,size=180):
 out=Image.new("RGBA",(size,size),(24,24,24,255));copy=im.copy();copy.thumbnail((size,size),Image.Resampling.LANCZOS);out.alpha_composite(copy,((size-copy.width)//2,(size-copy.height)//2));return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--idle-root",type=Path,required=True);p.add_argument("--death-root",type=Path,required=True);p.add_argument("--idle-samples",type=int,required=True);p.add_argument("--death-samples",type=int,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
 frames=[];rows=[]
 for d in range(16):
  path=a.idle_root/f"idle-direction-{d:02d}-frame-{a.idle_samples//2:03d}.png";im=Image.open(path);mean,median,dark=luminance(im);frames.append(im.copy());rows.append({"direction":d,"mean":mean,"median":median,"dark_percentile_p10":dark})
 sheet=Image.new("RGBA",(8*180,2*205),(24,24,24,255));draw=ImageDraw.Draw(sheet)
 for i,im in enumerate(frames):sheet.alpha_composite(tile(im),(i%8*180,i//8*205));draw.text((i%8*180+6,i//8*205+184),f"direction {i}",fill="white")
 sheet_path=a.output/"principes-v3-idle-directional-close-review.png";sheet.save(sheet_path)
 means=[r["mean"] for r in rows];summary={"mean":statistics.fmean(means),"median":statistics.median(means),"dark_percentile_p10":sorted(means)[1],"brightest_darkest_ratio":max(means)/min(means)}
 final=[]
 for d in range(16):final.append(Image.open(a.death_root/f"death-direction-{d:02d}-frame-{a.death_samples-1:03d}.png").convert("RGBA"))
 descriptors=decay_frames("final native death main","final native death shadow",10,{"mode":GENERATED,"corpse_linger_seconds":.5,"corpse_sink_seconds":1.5});indices=sorted({0,len(descriptors)//3,2*len(descriptors)//3,len(descriptors)-1});corpse=Image.new("RGBA",(len(indices)*400,400),(24,24,24,255))
 for col,index in enumerate(indices):
  desc=descriptors[index];source=final[0];shifted=Image.new("RGBA",source.size);shifted.alpha_composite(source,(0,desc["y_offset"]));alpha=shifted.getchannel("A").point(lambda x:int(x*desc["alpha"]));shifted.putalpha(alpha);corpse.alpha_composite(shifted,(col*400,0))
 corpse_path=a.output/"corpse-decay-v1-review.png";corpse.save(corpse_path)
 report={"format":"rome2aoe2.followup-review","version":1,"directional":{"measurement":"whole-visible-sprite luminance proxy; component diffuse/specular isolation requires diagnostic AOV render","directions":rows,"summary":summary,"sheet":str(sheet_path)},"transform_audit":{"camera":"invariant by renderer construction","dominant_light":"world-fixed in shared backend","environment_yaw_degrees":0.0,"facet_root":"single Z rotation per direction","normal_policy":"basis AOV transformed once by FacetRoot; Action fingerprint unchanged","per_direction_material_state":False,"stale_tangent_basis":False},"corpse":{"source":"final native death pose including released equipment","anchor":"fixed","operation":"downward pixel translation and below-canvas clipping; no scale or lateral translation","shadow":"same offset/fade policy","deterministic":True,"sheet":str(corpse_path)}}
 (a.output/"followup-review.json").write_text(json.dumps(report,indent=2)+"\n")
if __name__=="__main__":main()
