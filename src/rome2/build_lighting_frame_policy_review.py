from __future__ import annotations
import argparse,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageDraw
CURRENT="current-world-fixed-fill-0.6";COMP="facet-compensated-fill-0.6";NOFILL="facet-compensated-fill-0.0"
def image(root,policy,d):return Image.open(root/f"{policy}-direction-{d:02d}.png").convert("RGBA")
def tile(im,size=190,zoom=False):
 if zoom and im.getbbox():
  box=im.getbbox();pad=10;box=(max(0,box[0]-pad),max(0,box[1]-pad),min(im.width,box[2]+pad),min(im.height,box[3]+pad));im=im.crop(box)
 im=im.copy();im.thumbnail((size,size),Image.Resampling.LANCZOS);out=Image.new("RGBA",(size,size),(26,26,26,255));out.alpha_composite(im,((size-im.width)//2,(size-im.height)//2));return out
def sheet(rows,path,title,zoom=False):
 w=max(len(v) for _,v in rows)*190;h=34+215*len(rows);out=Image.new("RGBA",(w,h),(26,26,26,255));draw=ImageDraw.Draw(out);draw.text((8,8),title,fill="white")
 for ri,(label,items) in enumerate(rows):
  y=34+ri*215;draw.text((8,y),label,fill="white")
  for i,im in enumerate(items):out.alpha_composite(tile(im,zoom=zoom),(i*190,y+20));draw.text((i*190+5,y+195),f"d{i}",fill="white")
 path.parent.mkdir(parents=True,exist_ok=True);out.save(path)
def summarize(records,component,policy):
 rows=[r for r in records if r["policy"]==policy and r["metrics"][component]["mean"] is not None];values=[r["metrics"][component]["mean"] for r in rows];lo=min(range(len(values)),key=values.__getitem__);hi=max(range(len(values)),key=values.__getitem__)
 return {"mean_luminance":statistics.fmean(values),"median_luminance":statistics.median(values),"darkest_direction":rows[lo]["direction"],"brightest_direction":rows[hi]["direction"],"brightest_darkest_ratio":values[hi]/values[lo],"coefficient_of_variation":statistics.pstdev(values)/statistics.fmean(values),"direction_values":[{"direction":r["direction"],"mean_luminance":r["metrics"][component]["mean"],"pixels":r["metrics"][component]["pixels"]} for r in rows]}
def shadow_composite(main,shadow):
 out=Image.new("RGBA",main.size,(0,0,0,0));mask=shadow.convert("RGBA").getchannel("A");layer=Image.new("RGBA",main.size,(0,0,0,0));layer.putalpha(mask);out.alpha_composite(layer);out.alpha_composite(main);return out
def main():
 p=argparse.ArgumentParser();p.add_argument("--root",type=Path,required=True);p.add_argument("--idle-shadow",type=Path,required=True);p.add_argument("--attack-shadow",type=Path,required=True);a=p.parse_args();review=a.root/"review";reports={c:json.loads((a.root/c/"lighting-diagnostic.json").read_text()) for c in ("idle","attack")};paths={}
 for category in ("idle","attack"):
  root=a.root/category;cur=[image(root,CURRENT,d) for d in range(16)];comp=[image(root,COMP,d) for d in range(16)];nofill=[image(root,NOFILL,d) for d in range(16)]
  full=review/f"{category}-full-unit-current-vs-facet-compensated-x2.png";sheet([("current world-fixed + fill 0.6",cur),("facet-compensated + fill 0.6",comp),("facet-compensated + fill 0.0",nofill)],full,f"Principes {category}: 400x400 x2 lighting-frame diagnostic")
  shield=review/f"{category}-shield-close-current-vs-facet-compensated-x2.png";sheet([("current shield emphasis",cur),("compensated shield emphasis",comp)],shield,f"Principes {category}: shield close review",True)
  weapon=review/f"{category}-weapon-metal-close-current-vs-facet-compensated-x2.png";sheet([("current sword/metal",cur),("compensated sword/metal",comp)],weapon,f"Principes {category}: sword/metal close review",True)
  side=review/f"{category}-current-vs-compensated-pairs-x2.png";sheet([(f"direction {d}: current | compensated",[cur[d],comp[d]]) for d in range(16)],side,f"Principes {category}: paired lighting policy")
  shadow_root=a.idle_shadow if category=="idle" else a.attack_shadow;ordinal=21 if category=="idle" else 13;composites=[shadow_composite(comp[d],Image.open(shadow_root/f"{category}-direction-{d:02d}-frame-{ordinal:03d}.png")) for d in range(16)];shadow=review/f"{category}-facet-compensated-main-fixed-global-shadow-x2.png";sheet([("compensated main + fixed-global shadow",composites)],shadow,f"Principes {category}: proposed split main/shadow policy")
  paths[category]={"full_unit":str(full),"shield_close":str(shield),"weapon_close":str(weapon),"paired":str(side),"fixed_global_shadow_composite":str(shadow)}
 metrics={c:{component:{p:summarize(reports[c]["records"],component,p) for p in (CURRENT,COMP,NOFILL)} for component in ("shield","weapon")} for c in reports}
 result={"format":"rome2aoe2.lighting-frame-policy-review","version":1,"resolution":[400,400],"output_scale":"x2/high_definition","x1_omitted":True,"policies":{"current":"world-fixed captured illumination + readability fill 0.6","facet_compensated":"Renv=Rz(FacetRoot yaw) coherently rotates sun, ambient cube, and environment specular; readability fill 0.6","facet_compensated_no_fill":"same coherent transform; fill 0.0"},"shadow_policy":"existing fixed-global-cast-shadow-v1; shadow was not rerendered or rotated","metrics":metrics,"sheets":paths}
 (review/"lighting-frame-policy-review.json").write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
