"""Author FAST x2 death/corpse SLDs using cached final-pose world heights."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"build/python-deps/pillow")]
from PIL import Image
from aoe2.sld import LAYER_MAIN,LAYER_SHADOW,parse_sld,serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_facet_animation
from rome2aoe2.corpse_decay import PHYSICAL_GROUND,generate_physical_ground_images,read_float32_height,resolve_corpse_policy
def _encode(frames,count,texconv,output):
 document=author_facet_animation(frames,(200,244),16,count,encoder_factory=lambda:DirectXTexBC1Encoder(texconv));payload=serialize_sld(document);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(payload);parsed=parse_sld(payload)
 if parsed.version!=4 or len(parsed.frames)!=16*count:raise RuntimeError("corpse SLD readback frame count mismatch")
 if any(frame.frame_type!=(LAYER_MAIN|LAYER_SHADOW) or (frame.center_x,frame.center_y)!=(200,244) for frame in parsed.frames):raise RuntimeError("corpse SLD layer/hotspot mismatch")
 return {"path":str(output),"sha256":hashlib.sha256(payload).hexdigest(),"frames_per_direction":count,"total_frames":len(parsed.frames),"version":parsed.version,"read_back":True}
def author(report_path:Path,height_report_path:Path,texconv:Path,output_root:Path,unit_slug:str,policy):
 report=json.loads(report_path.read_text());height_report=json.loads(height_report_path.read_text());root=report_path.parent;count=int(report["rendered_sample_count"]);policy=resolve_corpse_policy(policy)
 if policy["mode"]!=PHYSICAL_GROUND or report.get("render_mode")!="fast" or height_report["render_count"]!=16 or height_report["passes_per_direction"]!=1:raise RuntimeError("physical FAST corpse evidence mismatch")
 required=float(height_report["geometry"]["required_world_sink"]);vector=height_report["camera"]["negative_world_z_screen_vector_x2"];height_rows={int(row["direction"]):row for row in height_report["directions"]};death=[];corpse=[];placement=[];coverage=[]
 for direction in range(16):
  direction_death=[]
  for ordinal in range(count):
   stem=f"death-direction-{direction:02d}-frame-{ordinal:03d}.png";direction_death.append((Image.open(root/"main/x2"/stem).convert("RGBA"),Image.open(root/"shadow/x2"/stem).convert("RGBA"),None))
  death.extend(direction_death);final_main,_,_=direction_death[-1];heights=read_float32_height(height_rows[direction]["height_f32"],final_main.width,final_main.height);generated,audit=generate_physical_ground_images(final_main,heights,policy,required,vector);coverage.append({"direction":direction,**audit})
  for ordinal,(main,shadow,state) in enumerate(generated):corpse.append((main,shadow,None));placement.append({"direction":direction,"frame":ordinal,**state})
 death_result=_encode(death,count,texconv,output_root/f"rome2aoe2_{unit_slug}_death_x2.sld");corpse_count=len(corpse)//16;corpse_path=output_root/f"rome2aoe2_{unit_slug}_corpse_x2.sld";corpse_result=_encode(corpse,corpse_count,texconv,corpse_path);repeat=output_root/"determinism-repeat"/corpse_path.name;repeat_result=_encode(corpse,corpse_count,texconv,repeat);corpse_result["deterministic"]=corpse_result["sha256"]==repeat_result["sha256"]
 continuity=[{"direction":d,"last_death_sha256":hashlib.sha256(death[(d+1)*count-1][0].tobytes()).hexdigest(),"first_corpse_sha256":hashlib.sha256(corpse[d*corpse_count][0].tobytes()).hexdigest(),"first_corpse_shadow_empty":corpse[d*corpse_count][1].getchannel("A").getbbox() is None,"final_corpse_main_empty":corpse[(d+1)*corpse_count-1][0].getchannel("A").getbbox() is None} for d in range(16)];shadows_empty=all(frame[1].getchannel("A").getbbox() is None for frame in corpse)
 result={"format":"rome2aoe2.generated-corpse-sld","version":4,"render_mode":"fast","release_eligible":False,"source_death_report":str(report_path),"world_height_report":str(height_report_path),"policy":policy,"death_fps":float(report["effective_render_fps"]),"corpse_fps":policy["corpse_fps"],"frame_duration":1/float(policy["corpse_fps"]),"linger_frames":round(policy["corpse_linger_seconds"]*policy["corpse_fps"]),"sink_frames":round(policy["corpse_sink_seconds"]*policy["corpse_fps"]),"death":death_result,"corpse":corpse_result,"placement":placement,"height_coverage":coverage,"continuity":continuity,"validation":{"world_height_passes":height_report["render_count"],"one_pass_per_direction":height_report["passes_per_direction"]==1,"authoritative_colour_only":True,"first_corpse_matches_last_death":all(x["last_death_sha256"]==x["first_corpse_sha256"] for x in continuity),"all_corpse_shadows_empty":shadows_empty,"all_final_corpse_mains_empty":all(x["final_corpse_main_empty"] for x in continuity),"complete_height_coverage":all(x["complete_source_coverage"] for x in coverage),"fixed_hotspot":True,"alpha_fade":False,"asset_specific_rules":False}}
 path=output_root/"generated-corpse-sld-report.json";path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");return path,result
def main():
 p=argparse.ArgumentParser();p.add_argument("--render-report",type=Path,required=True);p.add_argument("--world-height-report",type=Path,required=True);p.add_argument("--texconv",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--unit-slug",required=True);p.add_argument("--profile",type=Path,required=True);a=p.parse_args();policy=json.loads(a.profile.read_text())["corpse"];path,_=author(a.render_report,a.world_height_report,a.texconv,a.output_root,a.unit_slug,policy);print(path)
if __name__=="__main__":main()
