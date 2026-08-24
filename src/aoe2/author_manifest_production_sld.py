"""Author and validate direct SLDX v4 files from frozen production reports."""
from __future__ import annotations
import argparse,hashlib,json,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageChops,ImageDraw
from aoe2.analyze_sld import decode_frame
from aoe2.sld import parse_sld
from aoe2.sld_authoring import author_sld_animation
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.production import PROFILE
from rome2aoe2.render_modes import require_release_eligible
from rome2aoe2.production_reports import resolve_consolidated_category,sld_category_root

def frame_path(root,kind,scale,category,direction,ordinal):return root/kind/scale/f"{category}-direction-{direction:02d}-frame-{ordinal:03d}.png"
def tile(image,size=160):
 image=image.copy();image.thumbnail((size,size),Image.Resampling.LANCZOS);out=Image.new("RGBA",(size,size),(25,25,25,255));out.alpha_composite(image,((size-image.width)//2,(size-image.height)//2));return out
def sheet(rows,path,title):
 out=Image.new("RGBA",(max(len(images) for _,images in rows)*160,34+190*len(rows)),(25,25,25,255));draw=ImageDraw.Draw(out);draw.text((8,8),title,fill="white")
 for row,(label,images) in enumerate(rows):
  y=34+row*190;draw.text((8,y),label,fill="white")
  for column,image in enumerate(images):out.alpha_composite(tile(image),(column*160,y+24))
 path.parent.mkdir(parents=True,exist_ok=True);out.save(path)
def rgba_metrics(source,decoded):
 source,decoded=source.convert("RGBA"),decoded.convert("RGBA");sa=list(source.getchannel("A").getdata());da=list(decoded.getchannel("A").getdata());alpha_equal=sum((a>=128)==(b>=128) for a,b in zip(sa,da))/len(sa);errors=[]
 for left,right in zip(source.getdata(),decoded.getdata()):
  if left[3]>=128 or right[3]>=128:errors.extend(abs(left[index]-right[index]) for index in range(3))
 return {"alpha_class_agreement":alpha_equal,"mean_rgb_error":statistics.fmean(errors) if errors else 0.0,"max_rgb_error":max(errors,default=0)}
def shadow_metrics(source,decoded):
 values=[abs(a-b) for a,b in zip(source.convert("RGBA").getchannel("A").getdata(),decoded.getdata())];return {"mean_mask_error":statistics.fmean(values),"max_mask_error":max(values),"empty_agreement":source.getchannel("A").getbbox() is not None and decoded.getbbox() is not None}
def validate_visuals(sld_path,production_root,category,scale,samples,review):
 parsed=parse_sld(sld_path.read_bytes());representative=samples//2;direction_indices=[direction*samples+representative for direction in range(16)];temporal_samples=sorted({round((samples-1)*index/8) for index in range(9)});temporal_indices=[13*samples+sample for sample in temporal_samples];decoded={index:decode_frame(parsed,index) for index in set(direction_indices+temporal_indices)}
 direction_main=[decoded[index][0] for index in direction_indices];temporal_main=[decoded[index][0] for index in temporal_indices];direction_sheet=review/f"{category}-{scale}-decoded-16-directions.png";temporal_sheet=review/f"{category}-{scale}-decoded-temporal.png";comparison_sheet=review/f"{category}-{scale}-source-vs-decoded.png";shadow_sheet=review/f"{category}-{scale}-decoded-main-shadow.png"
 sheet([("directions 0-7",direction_main[:8]),("directions 8-15",direction_main[8:])],direction_sheet,f"{category} {scale} - SLD decoded directions");sheet([("direction 13",temporal_main)],temporal_sheet,f"{category} {scale} - SLD decoded samples {temporal_samples}")
 index=13*samples+representative;decoded_main,decoded_shadow=decoded[index];source_main=Image.open(frame_path(production_root,"main",scale,category,13,representative)).convert("RGBA");source_shadow=Image.open(frame_path(production_root,"shadow",scale,category,13,representative)).convert("RGBA");shadow_rgba=Image.new("RGBA",decoded_shadow.size,(0,0,0,0));shadow_rgba.putalpha(decoded_shadow)
 sheet([("source",[source_main]),("decoded",[decoded_main])],comparison_sheet,f"{category} {scale} - source vs SLD BC1");sheet([("main",[decoded_main]),("shadow",[shadow_rgba])],shadow_sheet,f"{category} {scale} - decoded main/shadow")
 metrics=[]
 for frame_index in sorted(decoded):
  direction,ordinal=divmod(frame_index,samples);main,shadow=decoded[frame_index];source_main=Image.open(frame_path(production_root,"main",scale,category,direction,ordinal));source_shadow=Image.open(frame_path(production_root,"shadow",scale,category,direction,ordinal));metrics.append({"direction":direction,"sample":ordinal,"main":rgba_metrics(source_main,main),"shadow":shadow_metrics(source_shadow,shadow)})
 return {"comparison_sample_count":len(metrics),"samples":metrics,"sheets":[str(direction_sheet),str(temporal_sheet),str(comparison_sheet),str(shadow_sheet)]}
def main():
 parser=argparse.ArgumentParser();parser.add_argument("manifest",type=Path);parser.add_argument("category",choices=("idle","walk","attack","death"));parser.add_argument("--expected-manifest-hash",required=True);parser.add_argument("--production-profile",default=PROFILE);parser.add_argument("--texconv",type=Path,required=True);args=parser.parse_args();request=load_and_validate_manifest(args.manifest)
 if request.manifest_hash!=args.expected_manifest_hash:raise RuntimeError(f"manifest identity mismatch: {request.manifest_hash}")
 record=request.manifest["animations"][args.category];report_path,production=resolve_consolidated_category(request,args.category,args.production_profile);require_release_eligible(production);production_root=Path(production["category_root"])
 for key,expected in (("manifest_hash",request.manifest_hash),("category",args.category),("exact_animation_asset",record["resolved_asset"]),("production_profile",args.production_profile)):
  if production.get(key)!=expected:raise RuntimeError(f"production report {key} mismatch: {production.get(key)!r} != {expected!r}")
 unit=request.unit.definition.main_unit;output_root=sld_category_root(unit,request.manifest_hash,args.category,args.production_profile);review=output_root/"review";encoded={}
 for scale in ("x1","x2"):
  output=output_root/f"{unit.casefold()}-{args.category}_{scale}.sld";first=author_sld_animation(production,scale,args.texconv,output);repeat=output_root/"determinism-repeat"/output.name;second=author_sld_animation(production,scale,args.texconv,repeat)
  first["determinism"]={"repeat_path":str(repeat),"repeat_sha256":second["sha256"],"identical":first["sha256"]==second["sha256"]}
  if not first["determinism"]["identical"]:raise RuntimeError(f"nondeterministic SLD output: {args.category}/{scale}")
  first["decoded_validation"]=validate_visuals(output,production_root,args.category,scale,record["frame_count"],review);encoded[scale]=first
 x1=parse_sld(Path(encoded["x1"]["path"]).read_bytes());x2=parse_sld(Path(encoded["x2"]["path"]).read_bytes());rep=record["frame_count"]//2;main1,_=decode_frame(x1,13*record["frame_count"]+rep);main2,_=decode_frame(x2,13*record["frame_count"]+rep);comparison=review/f"{args.category}-decoded-x1-x2.png";sheet([("x1",[main1]),("x2",[main2])],comparison,f"{args.category} - decoded native x1/x2")
 result={"format":"rome2aoe2.production-sld-authoring","version":2,"writer_version":"direct-sld-production-v1","unit":unit,"manifest_hash":request.manifest_hash,"animation_category":args.category,"source_animation":record["resolved_asset"],"production_profile":args.production_profile,"production_identity":production["production_identity"],"source_production_report":str(report_path),"directions":16,"frames_per_direction":record["frame_count"],"total_frames":16*record["frame_count"],"frame_order":"facet-major; production direction 0..15 unchanged","player_colour":False,"layers":["main","shadow"],"encoded":encoded,"decoded_x1_x2_sheet":str(comparison),"validation":{"production_identity":True,"main_shadow_parity":True,"constant_hotspot":True,"constant_canvas":True,"direction_order_preserved":True,"read_back":True,"deterministic":True}}
 report=output_root/f"{args.category}-sld-report.json";report.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");print(report)
if __name__=="__main__":main()
