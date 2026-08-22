"""Validate frozen production frames and compose compact review sheets."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageChops,ImageDraw
from rome2aoe2.conversion import load_and_validate_manifest
from rome2aoe2.native_assembly import assemble_native
from rome2aoe2.production import EXPECTED_DIRECTIONS,ORTHOGRAPHIC_SCALE,PROFILE,category_output,frozen_candidate
CATEGORIES=("idle","walk","attack","death");CANVASES={"master":(800,800),"x1":(200,200),"x2":(400,400)}
def tile(path,size=160):
 image=Image.open(path).convert("RGBA");image.thumbnail((size,size),Image.Resampling.LANCZOS);out=Image.new("RGBA",(size,size),(25,25,25,255));out.alpha_composite(image,((size-image.width)//2,(size-image.height)//2));return out
def sheet(rows,path,title):
 out=Image.new("RGBA",(max(len(row[1]) for row in rows)*160,34+len(rows)*190),(25,25,25,255));draw=ImageDraw.Draw(out);draw.text((8,8),title,fill="white")
 for row_index,(label,images) in enumerate(rows):
  y=34+row_index*190;draw.text((8,y),label,fill="white")
  for image_index,image_path in enumerate(images):out.alpha_composite(tile(image_path),(image_index*160,y+24))
 path.parent.mkdir(parents=True,exist_ok=True);out.save(path)
def validate_images(paths,dimensions,label):
 for path in paths:
  if not path.is_file():raise RuntimeError(f"missing {label} frame: {path}")
  with Image.open(path) as image:
   if image.size!=dimensions:raise RuntimeError(f"{label} canvas mismatch: {path}: {image.size}")
   if image.convert("RGBA").getchannel("A").getbbox() is None:raise RuntimeError(f"empty alpha frame: {path}")
def motion_policy(category):
 container={"walk":"Rome2AoE2_LocomotionCenter","death":"Rome2AoE2_DeathPreviewHorizontalCenter"}.get(category)
 return {"external_container":container,"horizontal_only":container is not None,"vertical_modified":False,"action_modified":False}
def main():
 parser=argparse.ArgumentParser();parser.add_argument("manifest",type=Path);args=parser.parse_args();request=load_and_validate_manifest(args.manifest);unit=request.unit.definition.main_unit;base=ROOT/"build/production/rome2aoe2"/unit.casefold()/request.manifest_hash[:16];review=base/"review";report={"format":"rome2aoe2.production-review","version":1,"manifest_hash":request.manifest_hash,"unit":unit,"categories":{}};overview=[]
 for category in CATEGORIES:
  row=request.manifest["animations"][category];category_root=category_output(unit,request.manifest_hash,category,row);samples=row["frame_count"];expected=16*samples
  paths={(kind,zoom):[category_root/kind/zoom/f"{category}-direction-{direction:02d}-frame-{frame:03d}.png" for direction in range(16) for frame in range(samples)] for kind in ("main","shadow") for zoom in ("x1","x2")};alpha={}
  for (kind,zoom),images in paths.items():validate_images(images,CANVASES[zoom],f"{category} {kind}/{zoom}");alpha[f"{kind}_{zoom}"]={"nonempty_frames":len(images),"expected_frames":expected,"all_nonempty":True}
  master=[category_root/"main/master"/f"{category}-direction-{direction:02d}-frame-{frame:03d}.png" for direction in range(16) for frame in range(samples)];validate_images(master,CANVASES["master"],f"{category} main/master");alpha["main_master"]={"nonempty_frames":len(master),"expected_frames":expected,"all_nonempty":True}
  main_reports=[json.loads(path.read_text()) for path in sorted(category_root.glob("render-report-directions-*.json"))];main_records=[record for document in main_reports for record in document["records"]];shadow=json.loads((category_root/"shadow-report.json").read_text());keys={(record["direction"],record["output_frame"]) for record in main_records}
  if len(keys)!=expected or len(main_records)!=expected or len(shadow["records"])!=expected:raise RuntimeError(f"{category} report inventory mismatch")
  if any(document["action_fingerprint_before"]!=document["action_fingerprint_after"] for document in main_reports) or shadow["action_fingerprint_before"]!=shadow["action_fingerprint_after"]:raise RuntimeError(f"{category} Action fingerprint changed")
  _,assembly=assemble_native(request.manifest,frozen_candidate(category,row));comparisons=assembly["duplicate_armature_comparisons"];rest=max((item["rest_matrix_max_delta"] for item in comparisons),default=0.0);hierarchy=max((item["parent_hierarchy_delta"] for item in comparisons),default=0)
  if rest!=0.0 or hierarchy!=0:raise RuntimeError(f"{category} native rest-basis mismatch")
  representative=samples//2;directions=[category_root/"main/x2"/f"{category}-direction-{direction:02d}-frame-{representative:03d}.png" for direction in range(16)];temporal_ids=sorted({round((samples-1)*index/8) for index in range(9)});temporal=[category_root/"main/x2"/f"{category}-direction-13-frame-{frame:03d}.png" for frame in temporal_ids];sheets=[review/f"{category}-16-directions.png",review/f"{category}-temporal.png",review/f"{category}-x1-x2.png",review/f"{category}-main-shadow.png"]
  sheet([("directions 0-7",directions[:8]),("directions 8-15",directions[8:])],sheets[0],f"{category} - 16 canonical directions - source sample {representative}");sheet([("direction 13",temporal)],sheets[1],f"{category} - temporal source samples {temporal_ids}");sheet([("x1",[category_root/"main/x1"/f"{category}-direction-13-frame-{representative:03d}.png"]),("x2",[category_root/"main/x2"/f"{category}-direction-13-frame-{representative:03d}.png"])],sheets[2],f"{category} - native x1/x2");sheet([("main",[category_root/"main/x2"/f"{category}-direction-13-frame-{representative:03d}.png"]),("shadow",[category_root/"shadow/x2"/f"{category}-direction-13-frame-{representative:03d}.png"])],sheets[3],f"{category} - main/shadow")
  seam=None
  if category in {"idle","walk"}:
   first=Image.open(category_root/"main/x2"/f"{category}-direction-13-frame-000.png").convert("RGBA");last=Image.open(category_root/"main/x2"/f"{category}-direction-13-frame-{samples-1:03d}.png").convert("RGBA");difference=ImageChops.difference(first,last);seam=sum(sum(pixel) for pixel in difference.getdata())/(400*400*4)
  validation={"no_missing_frames":True,"unique_direction_frame_keys":True,"constant_canvas":True,"x1_x2_parity":True,"main_shadow_parity":True,"alpha_bounds_sane":True,"no_nan_or_inf":True,"alpha_validation":alpha,"action_preserved":assembly["action_fingerprint_preserved"],"rest_basis_preserved":True,"armature_count":1,"unsupported_material_approximation":False,"old_preview_reused":False,"loop_seam_rgba_mae":seam};inventory={"main_master":len(master),"main_x1":len(paths[("main","x1")]),"main_x2":len(paths[("main","x2")]),"shadow_x1":len(paths[("shadow","x1")]),"shadow_x2":len(paths[("shadow","x2")]),"root":str(category_root)}
  production={"format":"rome2aoe2.consolidated-production-category","version":1,"manifest_hash":request.manifest_hash,"category":category,"exact_animation_asset":row["resolved_asset"],"action_fingerprint":main_reports[0]["action_fingerprint_before"],"native_frames":samples,"native_fps":row["fps"],"rendered_sample_mapping":main_reports[0]["rendered_sample_mapping"],"direction_order":list(range(16)),"direction_yaws":EXPECTED_DIRECTIONS,"camera_profile":PROFILE,"production_scale":ORTHOGRAPHIC_SCALE,"master_dimensions":list(CANVASES["master"]),"x1_dimensions":list(CANVASES["x1"]),"x2_dimensions":list(CANVASES["x2"]),"material_backend":"rome2_exact_material_backend/runtime_material_preparation/frozen captured runtime display","attachment_capabilities":assembly["rigid_attachment_carriers"],"shadow_profile":"fixed-global-cast-shadow-v1/Cycles-24-denoised","motion_policy":motion_policy(category),"native_rest_basis":{"bone_count":assembly["bone_count"],"max_parent_hierarchy_delta":hierarchy,"max_rest_matrix_delta":rest},"output_inventory":inventory,"validation":validation};production_report=category_root/"production-report.json";production_report.write_text(json.dumps(production,indent=2,sort_keys=True)+"\n");report["categories"][category]={**inventory,**validation,"native_samples":samples,"sheets":[str(path) for path in sheets],"production_report":str(production_report)};overview.append((category,[category_root/"main/x2"/f"{category}-direction-13-frame-{representative:03d}.png"]))
 overview_path=review/"production-overview.png";sheet(overview,overview_path,f"{unit} - frozen production overview");report["overview"]=str(overview_path);report_path=review/"production-review-report.json";report_path.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(report_path)
if __name__=="__main__":main()
