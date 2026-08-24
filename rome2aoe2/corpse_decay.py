"""Deterministic sprite-space corpse linger/sink policy."""
from __future__ import annotations
import math

DEFAULT={"mode":"inherit_template","corpse_linger_seconds":2.0,"corpse_sink_seconds":1.5,"corpse_fps":10.0,"sink_pixels_x2":28,"fade_final_fraction":0.35,"shadow_policy":"linger_then_fade_during_sink"}
GENERATED="generated_corpse_decay_v1"
def resolve_corpse_policy(value=None):
 policy={**DEFAULT,**(value or {})}
 if policy["mode"] not in {"inherit_template",GENERATED}:raise ValueError("unknown corpse policy")
 if policy["corpse_linger_seconds"]<0 or policy["corpse_sink_seconds"]<=0 or policy["corpse_fps"]<=0:raise ValueError("invalid corpse timing")
 return policy
def decay_frames(final_main,final_shadow,fps,policy=None):
 """Return (main, shadow, y_offset, alpha) descriptors; source pixels stay unchanged."""
 p=resolve_corpse_policy(policy);linger=round(p["corpse_linger_seconds"]*fps);sink=max(2,round(p["corpse_sink_seconds"]*fps));out=[]
 for _ in range(linger):out.append({"main":final_main,"shadow":final_shadow,"y_offset":0,"alpha":1.0})
 for i in range(sink):
  t=i/(sink-1);fade_start=1-p["fade_final_fraction"];alpha=1.0 if t<=fade_start else max(0.0,1-(t-fade_start)/p["fade_final_fraction"])
  out.append({"main":final_main,"shadow":final_shadow,"y_offset":round(p["sink_pixels_x2"]*t),"alpha":alpha})
 return out
def transform_frame(source,y_offset:int,alpha:float,clip_y:int|None=None):
 """Translate the complete death composition vertically on its fixed canvas/hotspot."""
 from PIL import Image
 source=source.convert("RGBA");result=Image.new("RGBA",source.size,(0,0,0,0));result.alpha_composite(source,(0,int(y_offset)))
 if clip_y is not None:
  clipped=Image.new("RGBA",source.size,(0,0,0,0));clipped.paste(result.crop((0,0,source.width,int(clip_y))),(0,0));result=clipped
 if alpha<1.0:result.putalpha(result.getchannel("A").point(lambda value:round(value*alpha)))
 return result
def generate_decay_images(final_main,final_shadow,policy=None):
 p=resolve_corpse_policy(policy);descriptors=decay_frames("main","shadow",p["corpse_fps"],p);linger=round(p["corpse_linger_seconds"]*p["corpse_fps"]);frames=[];main_box=final_main.convert("RGBA").getchannel("A").getbbox();shadow_box=final_shadow.convert("RGBA").getchannel("A").getbbox();main_clip=main_box[3] if main_box else final_main.height;shadow_clip=shadow_box[3] if shadow_box else final_shadow.height
 for index,item in enumerate(descriptors):
  sink_t=0.0 if index<linger else (index-linger)/max(len(descriptors)-linger-1,1)
  clip=None if index<linger else main_clip;main=transform_frame(final_main,item["y_offset"],item["alpha"],clip)
  shadow_alpha=item["alpha"] if index<linger else max(0.0,1.0-sink_t)
  shadow=transform_frame(final_shadow,item["y_offset"],shadow_alpha,None if index<linger else shadow_clip)
  frames.append((main,shadow,{**item,"shadow_alpha":shadow_alpha,"clip_y":clip,"phase":"linger" if index<linger else "sink"}))
 return frames
