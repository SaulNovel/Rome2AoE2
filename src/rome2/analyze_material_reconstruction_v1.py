"""Quantify reconstruction class response and mixed-material texture evidence."""
import json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"build"/"python-deps"/"pillow"));from PIL import Image
CU=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";MR=ROOT/"build"/"local-integration"/"rome2"/"material-reconstruction";R=MR/"renders"
UNITS=("hastati","principes","triarii","velites","hoplites","celtic-warriors","eastern-spearmen")
PAL={"skin":(255,137,177),"bronze":(255,255,50),"iron/steel":(61,177,255),"wood":(255,174,50),"cloth":(79,255,120),"leather":(153,84,43),"hair/fur":(255,110,255),"unknown":(255,0,255)}
def near(p):return min(PAL,key=lambda k:sum((p[i]-PAL[k][i])**2 for i in range(3)))
def lum(p):return .2126*p[0]+.7152*p[1]+.0722*p[2]
def main():
 rows=[]
 for s in UNITS:
  im=Image.open(R/f"{s}-reconstructed.png").convert("RGBA");fm=Image.open(CU/"renders-set-a"/f"{s}-material-classes.png").convert("RGBA");classes={k:[] for k in PAL}
  for p,q in zip(im.getdata(),fm.getdata()):
   if p[3]>8 and q[3]>8:classes[near(q[:3])].append(lum(p))
  rows.append({"unit":s,"class_luminance":{k:round(statistics.fmean(v),2) if v else None for k,v in classes.items()}})
 mixed=[]
 for s in UNITS:
  doc=json.loads((CU/"units"/s/"texture-manifest.json").read_text())
  for m in doc["materials"]:
   name=m["material_name"].lower()
   if not any(x in name for x in ("spear","pilum","javelin","gladius","sword","shield","scutum","hoplon")):continue
   textures={t["semantic"]:CU/"units"/s/"textures"/Path(t["extracted_path"]) for t in m["textures"] if t["status"]=="resolved"}
   stats={}
   for sem in ("Specular","GlossMap","Mask"):
    if sem in textures:
     vals=[lum(p[:3]) for p in Image.open(textures[sem]).convert("RGB").getdata()];stats[sem]={"mean":round(statistics.fmean(vals),2),"p10":round(sorted(vals)[len(vals)//10],2),"p90":round(sorted(vals)[9*len(vals)//10],2)}
   mixed.append({"unit":s,"material":m["material_name"],"texture_statistics":stats,"finding":"texture variation exists, but no source channel identifies physical metal-vs-wood class; do not threshold without ground truth"})
 (MR/"material-reconstruction-v1-analysis.json").write_text(json.dumps({"format":"rome2aoe2.material-reconstruction-analysis","version":1,"class_response":rows,"mixed_materials":mixed},indent=2,sort_keys=True)+"\n")
if __name__=="__main__":main()
