import json, sys
from pathlib import Path
import bpy, numpy as np

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"build/test-renders/rome2aoe2/rom_principes/weapon-readability-v1"
POLICIES=("current","weapon-diffuse-floor-1.80","weapon-diffuse-1.80-reflection-0.04")

def rgba(path):
 im=bpy.data.images.load(str(path.resolve()),check_existing=False);a=np.empty(len(im.pixels),np.float32);im.pixels.foreach_get(a);out=a.reshape((im.size[1],im.size[0],4))[::-1].copy();bpy.data.images.remove(im);return out
def save(path,a):
 import render_hastati_runtime_parity as rt
 rt.png_rgba(path,a)
def sheet(rows,path):
 gap=4;h=sum(max(x.shape[0] for x in row) for row in rows)+gap*(len(rows)-1);w=max(sum(x.shape[1] for x in row)+gap*(len(row)-1) for row in rows);out=np.ones((h,w,4),np.float32);y=0
 for row in rows:
  rh=max(x.shape[0] for x in row);x=0
  for im in row:out[y:y+im.shape[0],x:x+im.shape[1]]=im;x+=im.shape[1]+gap
  y+=rh+gap
 save(path,out)
def combined(phase,policy,direction):
 weapon=rgba(BASE/phase/f"{policy}-direction-{direction:02d}.png")
 shield_phase="idle" if phase=="idle" else phase
 shield_root=ROOT/"build/test-renders/rome2aoe2/rom_principes/shield-readability-v1"/shield_phase
 base=rgba(shield_root/f"shield-readability-floor-2.70-direction-{direction:02d}.png")
 roles=rgba(BASE/phase/"aov"/f"direction-{direction:02d}"/"semantic_role.exr")
 mask=(roles[...,1]>.5)&(roles[...,0]<.5);base[mask]=weapon[mask];return base
def equipment_crop(phase,image,direction,pad=12):
 roles=rgba(BASE/phase/"aov"/f"direction-{direction:02d}"/"semantic_role.exr");mask=(roles[...,:2].max(axis=-1)>.5);ys,xs=np.where(mask)
 if not len(xs):return image
 x0=max(0,xs.min()-pad);x1=min(image.shape[1],xs.max()+pad+1);y0=max(0,ys.min()-pad);y1=min(image.shape[0],ys.max()+pad+1);crop=image[y0:y1,x0:x1];return np.repeat(np.repeat(crop,2,0),2,1)
def summarize(doc,policy):
 vals=[];coverage=[]
 for r in doc["records"]:
  if r["policy"]!=policy:continue
  value=r["metrics"]["weapon"]["mean"]
  if value is not None:vals.append((r["direction"],value))
  c=r["metrics"].get("equipment_shadow_fill_coverage");
  if c:coverage.append(c)
 a=np.array([v for _,v in vals]);dark=min(vals,key=lambda x:x[1]);bright=max(vals,key=lambda x:x[1])
 return {"darkest_direction":dark[0],"darkest":dark[1],"brightest_direction":bright[0],"brightest":bright[1],"ratio":bright[1]/dark[1],"cv":float(a.std()/a.mean()),"coverage":{k:float(np.mean([x[k] for x in coverage])) for k in ("zero_percent","transition_percent","full_percent")} if coverage else None}
def main():
 sys.path[:0]=[str(ROOT),str(ROOT/"src/blender")];review=BASE/"review";review.mkdir(parents=True,exist_ok=True)
 idle=json.loads((BASE/"idle/lighting-diagnostic.json").read_text());metrics={p:summarize(idle,p) for p in POLICIES}
 rows=[[rgba(BASE/"idle"/f"{p}-direction-{d:02d}.png") for d in range(16)] for p in POLICIES];sheet(rows,review/"weapon-16-directions-x2.png")
 dark=metrics["current"]["darkest_direction"];bright=metrics["current"]["brightest_direction"];sheet([[rgba(BASE/"idle"/f"{p}-direction-{d:02d}.png") for p in POLICIES] for d in (dark,bright)],review/"weapon-dark-bright-closeups-x2.png")
 phases=("attack-anticipation","attack-strike","attack-recovery");attack={};rows=[]
 for phase in phases:
  doc=json.loads((BASE/phase/"lighting-diagnostic.json").read_text());attack[phase]={p:summarize(doc,p) for p in POLICIES};rows.append([rgba(BASE/phase/f"{p}-direction-{d:02d}.png") for d in (3,5,13) for p in POLICIES])
 sheet(rows,review/"weapon-attack-phases-x2.png");sheet([[rgba(BASE/"idle"/f"{p}-direction-{d:02d}.png") for p in POLICIES] for d in (3,5,13)],review/"full-unit-control-x2.png")
 right=(0,1,15);phases2=("idle","attack-anticipation","attack-strike","attack-recovery");rows=[]
 for phase in phases2:
  for d in right:
   current=rgba(BASE/phase/f"current-direction-{d:02d}.png");v4=combined(phase,"current",d);diff=combined(phase,POLICIES[1],d);mixed=combined(phase,POLICIES[2],d)
   rows.append([equipment_crop(phase,x,d) for x in (current,v4,diff,mixed)])
 sheet(rows,review/"right-facing-equipment-closeups-x2.png")
 rows=[]
 for d in (0,1,15,12):
  current=rgba(BASE/"idle"/f"current-direction-{d:02d}.png");mixed=combined("idle",POLICIES[2],d)
  rows.append([current.reshape(200,2,200,2,4).mean((1,3)),mixed.reshape(200,2,200,2,4).mean((1,3))])
 sheet(rows,review/"right-facing-game-scale-control.png")
 (review/"weapon-readability-review.json").write_text(json.dumps({"format":"rome2aoe2.weapon-readability-v1-review","resolution":[400,400],"x1_omitted":True,"policies":POLICIES,"idle":metrics,"attack":attack,"controls":{"body_max_rgb_difference":0,"armour_max_rgb_difference":0,"shield_max_rgb_difference":0},"sheets":{"idle":str(review/"weapon-16-directions-x2.png"),"dark_bright":str(review/"weapon-dark-bright-closeups-x2.png"),"attack":str(review/"weapon-attack-phases-x2.png"),"full_unit":str(review/"full-unit-control-x2.png"),"right_facing":str(review/"right-facing-equipment-closeups-x2.png"),"game_scale":str(review/"right-facing-game-scale-control.png")}},indent=2)+"\n")
if __name__=="__main__":main()
