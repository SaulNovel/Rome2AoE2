"""Deterministic generated-corpse policies and physical-ground composition."""
from __future__ import annotations
from array import array
import math

DEFAULT={"mode":"inherit_template","corpse_linger_seconds":2.0,"corpse_sink_seconds":1.5,"corpse_fps":10.0,"sink_pixels_x2":28,"fade_final_fraction":0.35,"shadow_policy":"linger_then_fade_during_sink"}
GENERATED="generated_corpse_decay_v1"
PHYSICAL_GROUND="physical_ground_world_height_v1"
def resolve_corpse_policy(value=None):
 policy={**DEFAULT,**(value or {})}
 if policy["mode"] not in {"inherit_template",GENERATED,PHYSICAL_GROUND}:raise ValueError("unknown corpse policy")
 if policy["corpse_linger_seconds"]<0 or policy["corpse_sink_seconds"]<=0 or policy["corpse_fps"]<=0:raise ValueError("invalid corpse timing")
 if policy["mode"]==PHYSICAL_GROUND:
  duration=1/float(policy["corpse_fps"]);linger=round(policy["corpse_linger_seconds"]/duration);sink=round(policy["corpse_sink_seconds"]/duration)
  if linger<1 or sink<1 or not math.isclose(linger*duration,policy["corpse_linger_seconds"],abs_tol=1e-9) or not math.isclose(sink*duration,policy["corpse_sink_seconds"],abs_tol=1e-9):raise ValueError("physical corpse timing must be an exact positive frame count")
 return policy
def decay_frames(final_main,final_shadow,fps,policy=None):
 """Legacy generated-corpse descriptors retained for historical profiles."""
 p=resolve_corpse_policy(policy);linger=round(p["corpse_linger_seconds"]*fps);sink=max(2,round(p["corpse_sink_seconds"]*fps));out=[]
 for _ in range(linger):out.append({"main":final_main,"shadow":final_shadow,"y_offset":0,"alpha":1.0})
 for i in range(sink):
  t=i/(sink-1);fade_start=1-p["fade_final_fraction"];alpha=1.0 if t<=fade_start else max(0.0,1-(t-fade_start)/p["fade_final_fraction"])
  out.append({"main":final_main,"shadow":final_shadow,"y_offset":round(p["sink_pixels_x2"]*t),"alpha":alpha})
 return out
def transform_frame(source,y_offset:int,alpha:float,clip_y:int|None=None):
 from PIL import Image
 source=source.convert("RGBA");result=Image.new("RGBA",source.size,(0,0,0,0));result.alpha_composite(source,(0,int(y_offset)))
 if clip_y is not None:
  clipped=Image.new("RGBA",source.size,(0,0,0,0));clipped.paste(result.crop((0,0,source.width,int(clip_y))),(0,0));result=clipped
 if alpha<1.0:result.putalpha(result.getchannel("A").point(lambda value:round(value*alpha)))
 return result
def generate_decay_images(final_main,final_shadow,policy=None):
 """Legacy RGBA-only generator retained for old independently resolvable profiles."""
 from PIL import Image
 p=resolve_corpse_policy(policy);frames=[]
 for item in decay_frames("main","shadow",p["corpse_fps"],p):
  main=transform_frame(final_main,item["y_offset"],item["alpha"]);no_shadow=p.get("shadow_policy")=="no_corpse_shadow";shadow=Image.new("RGBA",final_shadow.size) if no_shadow else transform_frame(final_shadow,item["y_offset"],item["alpha"])
  frames.append((main,shadow,{**item,"shadow_alpha":0.0 if no_shadow else item["alpha"],"phase":"linger" if item["y_offset"]==0 else "sink"}))
 return frames
def read_float32_height(path,width,height):
 values=array("f")
 with open(path,"rb") as stream:values.fromfile(stream,width*height)
 if len(values)!=width*height:raise ValueError(f"world-height cache size mismatch: {path}")
 return values
def physical_sink_states(policy,required_world_sink):
 """One or more held frames followed by N non-zero sink states."""
 p=resolve_corpse_policy(policy);duration=1/float(p["corpse_fps"]);linger=round(p["corpse_linger_seconds"]/duration);sink=round(p["corpse_sink_seconds"]/duration);states=[]
 for _ in range(linger):states.append({"phase":"linger","sink_fraction":0.0,"world_sink":0.0})
 for i in range(1,sink+1):
  fraction=i/sink;states.append({"phase":"sink","sink_fraction":fraction,"world_sink":required_world_sink*fraction})
 return states
def generate_physical_ground_images(final_main,heights,policy,required_world_sink,screen_vector):
 """Translate exact source RGBA and hide surfaces after their world Z crosses terrain."""
 from PIL import Image
 source=final_main.convert("RGBA");w,h=source.size
 if len(heights)!=w*h:raise ValueError("height/source canvas mismatch")
 pixels=source.load();surfaces=[(x,y,pixels[x,y],heights[y*w+x]) for y in range(h) for x in range(w) if pixels[x,y][3]];visible=len(surfaces);coverage=sum(1 for _,_,_,height in surfaces if math.isfinite(height))
 if coverage!=visible:raise ValueError(f"world-height AOV does not cover source RGBA: {coverage}/{visible}")
 frames=[];empty=Image.new("RGBA",source.size)
 for index,state in enumerate(physical_sink_states(policy,required_world_sink)):
  depth=state["world_sink"]
  if index==0:main=source.copy();dx=dy=0
  else:
   dx=round(screen_vector[0]*depth);dy=round(screen_vector[1]*depth);main=Image.new("RGBA",source.size);out=main.load()
   for sx,sy,rgba,height in surfaces:
    if height-depth>=0:
     x=sx+dx;y=sy+dy
     if 0<=x<w and 0<=y<h:out[x,y]=rgba
  frames.append((main,empty.copy(),{**state,"screen_offset_x":dx,"screen_offset_y":dy,"shadow_alpha":0.0}))
 return frames,{"source_visible_pixels":visible,"height_covered_source_pixels":coverage,"complete_source_coverage":coverage==visible}
