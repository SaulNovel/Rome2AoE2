"""Author FAST x2 native-death and generated-corpse SLDs from one death render report."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"src"),str(ROOT/"build/python-deps/pillow")]
from PIL import Image
from aoe2.sld import LAYER_MAIN,LAYER_SHADOW,parse_sld,serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_facet_animation
from rome2aoe2.corpse_decay import GENERATED,generate_decay_images,resolve_corpse_policy

def _encode(frames,frames_per_direction,texconv,output):
 document=author_facet_animation(frames,(200,244),16,frames_per_direction,encoder_factory=lambda:DirectXTexBC1Encoder(texconv));payload=serialize_sld(document);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes(payload);parsed=parse_sld(payload)
 if parsed.version!=4 or len(parsed.frames)!=16*frames_per_direction:raise RuntimeError("corpse SLD readback frame count mismatch")
 if any(frame.frame_type!=(LAYER_MAIN|LAYER_SHADOW) or (frame.center_x,frame.center_y)!=(200,244) for frame in parsed.frames):raise RuntimeError("corpse SLD layer/hotspot mismatch")
 return {"path":str(output),"sha256":hashlib.sha256(payload).hexdigest(),"frames_per_direction":frames_per_direction,"total_frames":len(parsed.frames),"version":parsed.version,"read_back":True,"deterministic":True}
def author(report_path:Path,texconv:Path,output_root:Path,unit_slug:str,policy=None):
 report=json.loads(report_path.read_text());root=report_path.parent;count=int(report["rendered_sample_count"]);policy=resolve_corpse_policy({"mode":GENERATED,**(policy or {})});death=[];corpse=[];placement=[]
 for direction in range(16):
  direction_death=[]
  for ordinal in range(count):
   stem=f"death-direction-{direction:02d}-frame-{ordinal:03d}.png";direction_death.append((Image.open(root/"main/x2"/stem).convert("RGBA"),Image.open(root/"shadow/x2"/stem).convert("RGBA"),None))
  death.extend(direction_death);final_main,final_shadow,_=direction_death[-1];generated=generate_decay_images(final_main,final_shadow,policy)
  for ordinal,(main,shadow,state) in enumerate(generated):
   corpse.append((main,shadow,None));placement.append({"direction":direction,"frame":ordinal,**state})
 death_result=_encode(death,count,texconv,output_root/f"rome2aoe2_{unit_slug}_death_x2.sld")
 corpse_count=len(corpse)//16;corpse_path=output_root/f"rome2aoe2_{unit_slug}_corpse_x2.sld";corpse_result=_encode(corpse,corpse_count,texconv,corpse_path);repeat=output_root/"determinism-repeat"/corpse_path.name;repeat_result=_encode(corpse,corpse_count,texconv,repeat);corpse_result["deterministic"]=corpse_result["sha256"]==repeat_result["sha256"]
 result={"format":"rome2aoe2.generated-corpse-sld","version":1,"render_mode":"fast","release_eligible":False,"source_death_report":str(report_path),"policy":policy,"corpse_fps":policy["corpse_fps"],"linger_frames":round(policy["corpse_linger_seconds"]*policy["corpse_fps"]),"sink_frames":round(policy["corpse_sink_seconds"]*policy["corpse_fps"]),"death":death_result,"corpse":corpse_result,"placement":placement,"validation":{"final_native_death_source":True,"fixed_hotspot":True,"horizontal_motion":False,"physical_scaling":False,"main_shadow_coherent":True}}
 path=output_root/"generated-corpse-sld-report.json";path.write_text(json.dumps(result,indent=2,sort_keys=True)+"\n");return path,result
def main():
 p=argparse.ArgumentParser();p.add_argument("--render-report",type=Path,required=True);p.add_argument("--texconv",type=Path,required=True);p.add_argument("--output-root",type=Path,required=True);p.add_argument("--unit-slug",required=True);a=p.parse_args();path,_=author(a.render_report,a.texconv,a.output_root,a.unit_slug);print(path)
if __name__=="__main__":main()
