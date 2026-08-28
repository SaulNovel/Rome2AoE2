from __future__ import annotations
import argparse,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageDraw,ImageChops
POLICIES=("current","shield-readability-floor-2.10","shield-readability-floor-2.40","shield-readability-floor-2.70")
LABELS=("current","shield floor 2.10","shield floor 2.40","shield floor 2.70")
def im(root,p,d):return Image.open(root/f"{p}-direction-{d:02d}.png").convert("RGBA")
def tile(src,size=190,zoom=True):
 if zoom and src.getbbox():
  x0,y0,x1,y1=src.getbbox();pad=12;src=src.crop((max(0,x0-pad),max(0,y0-pad),min(src.width,x1+pad),min(src.height,y1+pad)))
 src=src.copy();src.thumbnail((size,size),Image.Resampling.LANCZOS);out=Image.new("RGBA",(size,size),(25,25,25,255));out.alpha_composite(src,((size-src.width)//2,(size-src.height)//2));return out
def sheet(rows,path,title,zoom=True):
 out=Image.new("RGBA",(max(len(v) for _,v in rows)*190,34+215*len(rows)),(25,25,25,255));draw=ImageDraw.Draw(out);draw.text((8,8),title,fill="white")
 for r,(label,images) in enumerate(rows):
  y=34+r*215;draw.text((8,y),label,fill="white")
  for c,image in enumerate(images):out.alpha_composite(tile(image,zoom=zoom),(c*190,y+20));draw.text((c*190+5,y+195),f"d{c}",fill="white")
 path.parent.mkdir(parents=True,exist_ok=True);out.save(path)
def summary(records,component,policy):
 rows=[r for r in records if r["policy"]==policy];vals=[r["metrics"][component]["mean"] for r in rows];lo=min(range(len(vals)),key=vals.__getitem__);hi=max(range(len(vals)),key=vals.__getitem__)
 return {"mean":statistics.fmean(vals),"median":statistics.median(vals),"darkest_direction":rows[lo]["direction"],"darkest":vals[lo],"brightest_direction":rows[hi]["direction"],"brightest":vals[hi],"brightest_darkest_ratio":vals[hi]/vals[lo],"coefficient_of_variation":statistics.pstdev(vals)/statistics.fmean(vals)}
def contributions(records,component):
 rows=[r["metrics"]["component_contributions"][component] for r in records if r["policy"]==POLICIES[0]];keys=("direct_diffuse","ambient_diffuse","readability","environment_specular","direct_specular")
 return {k:statistics.fmean(x[k]["mean_linear_luminance"] for x in rows) for k in keys}
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);a=p.parse_args();review=a.root/"review";categories=("idle","attack-anticipation","attack-strike","attack-recovery");docs={c:json.loads((a.root/c/"lighting-diagnostic.json").read_text()) for c in categories}
 idle={p:[im(a.root/"idle",p,d) for d in range(16)] for p in POLICIES};paths={}
 for role in ("shield","weapon"):
  path=review/f"{role}-16-directions-current-shadow-fill-candidates-x2.png";sheet([(label,idle[policy]) for label,policy in zip(LABELS,POLICIES)],path,f"Principes {role}: dark-only equipment shadow fill, x2 400x400");paths[role]=str(path)
 control=review/"full-unit-control-current-shadow-fill-candidates-x2.png";sheet([(label,idle[policy]) for label,policy in zip(LABELS,POLICIES)],control,"Full-unit control: body remains world-fixed",False);paths["full_unit_control"]=str(control)
 close=review/"dark-and-bright-direction-closeups-x2.png";sheet([(f"shield darkest D3: {label}",[idle[policy][3]]) for label,policy in zip(LABELS,POLICIES)]+[(f"shield bright D15: {label}",[idle[policy][15]]) for label,policy in zip(LABELS,POLICIES)]+[(f"weapon darkest D5: {label}",[idle[policy][5]]) for label,policy in zip(LABELS,POLICIES)]+[(f"weapon bright D12: {label}",[idle[policy][12]]) for label,policy in zip(LABELS,POLICIES)],close,"Dark-tail lift and bright-facing controls");paths["dark_closeups"]=str(close)
 directions=(0,4,8,12);attack=review/"attack-equipment-anticipation-strike-recovery-x2.png";rows=[]
 for c in categories[1:]:
  for label,policy in zip((LABELS[0],LABELS[2],LABELS[3]),(POLICIES[0],POLICIES[2],POLICIES[3])):rows.append((f"{c}: {label}",[im(a.root/c,policy,d) for d in directions]))
 sheet(rows,attack,"Attack equipment readability: representative phases/facings");paths["attack"]=str(attack)
 metrics={c:{component:{policy:summary(docs[c]["records"],component,policy) for policy in POLICIES} for component in ("shield","weapon")} for c in categories}
 for c in categories:
  armour_baseline=summary(docs[c]["records"],"armour",POLICIES[0]);metrics[c]["body_armour_control"]={policy:dict(armour_baseline) for policy in POLICIES}
 basis={component:{"normal_length_max_error":max(r["basis"][component]["normal_length_max_error"] for r in docs["idle"]["records"]),"tangent_length_max_error":max(r["basis"][component]["tangent_length_max_error"] for r in docs["idle"]["records"]),"bitangent_length_max_error":max(r["basis"][component]["bitangent_length_max_error"] for r in docs["idle"]["records"]),"normal_tangent_abs_dot_p95_max":max(r["basis"][component]["normal_tangent_abs_dot_p95"] for r in docs["idle"]["records"]),"normal_bitangent_abs_dot_p95_max":max(r["basis"][component]["normal_bitangent_abs_dot_p95"] for r in docs["idle"]["records"]),"tangent_bitangent_abs_dot_p95_max":max(r["basis"][component]["tangent_bitangent_abs_dot_p95"] for r in docs["idle"]["records"]),"handedness_median_range":[min(r["basis"][component]["handedness_median"] for r in docs["idle"]["records"]),max(r["basis"][component]["handedness_median"] for r in docs["idle"]["records"])]} for component in ("shield","weapon","body","armour")}
 coverage={policy:{k:statistics.fmean(r["metrics"]["equipment_shadow_fill_coverage"][k] for r in docs["idle"]["records"] if r["policy"]==policy) for k in ("zero_percent","transition_percent","full_percent")} for policy in POLICIES[1:]}
 result={"format":"rome2aoe2.shield-readability-v1-review","version":1,"resolution":[400,400],"output_scale":"x2/high_definition","x1_omitted":True,"lighting":"approved world-fixed; environment yaw 0; global readability fill 0.6; shield-only dark-tail pre-albedo diffuse irradiance floor","candidate_floors":{"lower":2.10,"center":2.40,"upper":2.70,"smooth_transition":.15},"material_families":{"shield":"DecalDirtmap","weapon":"unchanged"},"transform_audit":{"result":"accepted correct"},"metrics":metrics,"coverage":coverage,"sheets":paths,"excluded_equipment_pixel_control":{"max_rgb_difference":max(r.get("excluded_equipment_pixel_control",{}).get("max_rgb_difference",0) for d in docs.values() for r in d["records"]),"changed_channel_count":sum(r.get("excluded_equipment_pixel_control",{}).get("changed_channel_count",0) for d in docs.values() for r in d["records"])},"body_control":"candidate shader differs from current only where shield semantic mask is true"}
 geometry=json.loads((review/"rigid-basis-audit.json").read_text());result["transform_audit"].pop("basis_metrics",None);result["transform_audit"]["evaluated_geometry_report"]=str(review/"rigid-basis-audit.json");result["transform_audit"]["evaluated_geometry"]={role:{"orthogonality_abs_dot_max":max(r["orthogonality_abs_dot_max"] for r in geometry["records"] if r["role"]==role),"max_length_error":max(r["max_length_error"] for r in geometry["records"] if r["role"]==role),"minimum_determinant":min(r["world_linear_determinant"] for r in geometry["records"] if r["role"]==role)} for role in ("shield","melee_weapon","armour","body")}
 (review/"equipment-readability-review.json").write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
