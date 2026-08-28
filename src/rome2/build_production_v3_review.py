"""Validate complete Principes V3 production and build its human review package."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageChops,ImageDraw
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.production import EXPECTED_DIRECTIONS,category_output,resolve_production_profile
MANIFEST=ROOT/"build/manifests/rom_principes-explicit-animations-v2.json"
PROFILE="aoe2-infantry-animation-production-v3-weapon-forward"; CATEGORIES=("idle","walk","attack","death")
CANVASES={"master":(800,800),"x1":(200,200),"x2":(400,400)}
def tile(path,size=160):
 im=Image.open(path).convert("RGBA");im.thumbnail((size,size),Image.Resampling.LANCZOS);out=Image.new("RGBA",(size,size),(25,25,25,255));out.alpha_composite(im,((size-im.width)//2,(size-im.height)//2));return out
def sheet(rows,path,title):
 out=Image.new("RGBA",(max(len(v) for _,v in rows)*160,34+len(rows)*190),(25,25,25,255));d=ImageDraw.Draw(out);d.text((8,8),title,fill="white")
 for ri,(label,images) in enumerate(rows):
  y=34+ri*190;d.text((8,y),label,fill="white")
  for ii,p in enumerate(images):out.alpha_composite(tile(p),(ii*160,y+24))
 path.parent.mkdir(parents=True,exist_ok=True);out.save(path)
def validate(paths,size,label):
 for p in paths:
  if not p.is_file():raise RuntimeError(f"missing {label}: {p}")
  with Image.open(p) as im:
   if im.size!=size:raise RuntimeError(f"canvas mismatch {label}: {p}: {im.size}")
   if im.convert("RGBA").getchannel("A").getbbox() is None:raise RuntimeError(f"empty frame {label}: {p}")
def main():
 req=load_and_validate_manifest(MANIFEST);profile=resolve_production_profile(PROFILE);unit=req.unit.definition.main_unit;base=ROOT/"build/production/rome2aoe2"/unit.casefold()/req.manifest_hash[:16];review=base/PROFILE/"review"
 report={"format":"rome2aoe2.production-review","version":3,"manifest_hash":req.manifest_hash,"profile":profile,"visual_scale":1.0,"canonical_orthographic_scale":7.27480212108078,"effective_orthographic_scale":7.27480212108078,"categories":{}}
 roots={};overview=[];edge=overscan=safe=overflow=0;fingerprints={}
 for cat in CATEGORIES:
  row=req.manifest["animations"][cat];root=category_output(unit,req.manifest_hash,cat,row,PROFILE,1.0);roots[cat]=root;n=row["frame_count"];expected=16*n
  def paths(kind,zoom):return [root/kind/zoom/f"{cat}-direction-{d:02d}-frame-{f:03d}.png" for d in range(16) for f in range(n)]
  master=[root/"main/master"/f"{cat}-direction-{d:02d}-frame-{f:03d}.png" for d in range(16) for f in range(n)];validate(master,CANVASES["master"],f"{cat} main/master")
  for kind in ("main","shadow"):
   for zoom in ("x1","x2"):validate(paths(kind,zoom),CANVASES[zoom],f"{cat} {kind}/{zoom}")
  main=json.loads((root/"render-report.json").read_text());shadow=json.loads((root/"shadow-report.json").read_text())
  if len(main["records"])!=expected or len(shadow["records"])!=expected:raise RuntimeError(f"{cat} report inventory mismatch")
  for doc in (main,shadow):
   if doc["direction_order"]!=list(range(16)) or doc["direction_yaws"]!=EXPECTED_DIRECTIONS:raise RuntimeError(f"{cat} direction mismatch")
   if doc["visual_scale"]!=1.0 or doc["effective_orthographic_scale"]!=7.27480212108078:raise RuntimeError(f"{cat} scale mismatch")
   if doc["action_fingerprint_before"]!=doc["action_fingerprint_after"]:raise RuntimeError(f"{cat} Action changed")
  if main["profile"]!=PROFILE or main["main_illumination"]!=profile["main_illumination"]:raise RuntimeError(f"{cat} lighting/profile mismatch")
  if shadow["profile"]!="fixed-global-cast-shadow-v1":raise RuntimeError(f"{cat} shadow profile mismatch")
  vals=[r["canvas_validation"] for r in main["records"]+shadow["records"]];edge+=sum(v["edge_contact"] for v in vals);overscan+=sum(v["overscan_performed"] for v in vals);safe+=sum(v["overscan_performed"] and not v["confirmed_overflow"] for v in vals);overflow+=sum(v["confirmed_overflow"] for v in vals)
  if any(v["confirmed_overflow"] for v in vals):raise RuntimeError(f"{cat} confirmed overflow")
  fingerprints[cat]=main["action_fingerprint_before"];rep=n//2;dirs=[root/"main/x2"/f"{cat}-direction-{d:02d}-frame-{rep:03d}.png" for d in range(16)];ids=sorted({round((n-1)*i/8) for i in range(9)});temporal=[root/"main/x2"/f"{cat}-direction-13-frame-{f:03d}.png" for f in ids]
  outputs=[review/f"{cat}-16-directions.png",review/f"{cat}-temporal.png",review/f"{cat}-x1-x2.png",review/f"{cat}-main-shadow.png"]
  sheet([("directions 0-7",dirs[:8]),("directions 8-15",dirs[8:])],outputs[0],f"{cat} - 16 canonical directions");sheet([("direction 13",temporal)],outputs[1],f"{cat} - temporal {ids}")
  sheet([("x1",[root/"main/x1"/f"{cat}-direction-13-frame-{rep:03d}.png"]),("x2",[root/"main/x2"/f"{cat}-direction-13-frame-{rep:03d}.png"])],outputs[2],f"{cat} x1/x2")
  sheet([("main",[root/"main/x2"/f"{cat}-direction-13-frame-{rep:03d}.png"]),("shadow",[root/"shadow/x2"/f"{cat}-direction-13-frame-{rep:03d}.png"])],outputs[3],f"{cat} main/shadow")
  seam=None
  if cat in {"idle","walk"}:
   a=Image.open(root/"main/x2"/f"{cat}-direction-13-frame-000.png").convert("RGBA");b=Image.open(root/"main/x2"/f"{cat}-direction-13-frame-{n-1:03d}.png").convert("RGBA");seam=sum(sum(p) for p in ImageChops.difference(a,b).getdata())/(400*400*4)
  report["categories"][cat]={"root":str(root),"native_samples":n,"inventory":{"main_master":expected,"main_x1":expected,"main_x2":expected,"shadow_x1":expected,"shadow_x2":expected},"action_fingerprint":fingerprints[cat],"loop_seam_rgba_mae":seam,"sheets":[str(p) for p in outputs]};overview.append((cat,[root/"main/x2"/f"{cat}-direction-13-frame-{rep:03d}.png"]))
 overview_path=review/"production-overview.png";sheet(overview,overview_path,f"{unit} complete V3 overview")
 attack=roots["attack"];an=req.manifest["animations"]["attack"]["frame_count"];strike=round((an-1)*.44);attack_path=review/"attack-anticipation-strike-recovery.png";sheet([("anticipation / strike / recovery",[attack/"main/x2"/f"attack-direction-13-frame-{i:03d}.png" for i in (0,strike,an-1)])],attack_path,"attack phases")
 weapon_path=review/"weapon-forward.png";sheet([("strike directions",[attack/"main/x2"/f"attack-direction-{d:02d}-frame-{strike:03d}.png" for d in range(16)])],weapon_path,"one_handed_blade_v3_source_frame_forward_corrected")
 death=roots["death"];dn=req.manifest["animations"]["death"]["frame_count"];death_path=review/"death-held-fall-released-final.png";sheet([("held / fall / released / final",[death/"main/x2"/f"death-direction-13-frame-{i:03d}.png" for i in (0,round((dn-1)*.4),round((dn-1)*.75),dn-1)])],death_path,"native death release")
 lighting=review/"lighting-direction-summary.png";sheet(overview,lighting,"world-fixed environment yaw 0.0; readability fill 0.6")
 walk_shadow=json.loads((roots["walk"]/"shadow-report.json").read_text());d5=next(r for r in walk_shadow["records"] if r["direction"]==5 and r["output_frame"]==3)["canvas_validation"]
 report.update({"action_fingerprints":fingerprints,"canvas_validation":{"edge_contact_count":edge,"overscan_probe_count":overscan,"confirmed_safe_count":safe,"confirmed_overflow_count":overflow,"walk_d5_sample3_shadow":d5},"overview":str(overview_path),"weapon_forward":str(weapon_path),"attack_closeup":str(attack_path),"death_review":str(death_path),"lighting_summary":str(lighting)})
 out=review/"production-review-report.json";out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(out)
if __name__=="__main__":main()
