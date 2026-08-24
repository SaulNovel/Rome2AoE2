"""Render-quality presets; full is immutable production, fast is test-only."""
from __future__ import annotations
import hashlib,json,math

MODES={
 "full":{"render_mode":"full","temporal_sample_factor":1.0,"master_resolution":800,"output_scales":["x1","x2"],"high_definition_output":"x2/400x400","low_definition_output":"x1/200x200","release_eligible":True},
 "fast":{"render_mode":"fast","temporal_sample_factor":0.5,"master_resolution":400,"output_scales":["x2"],"high_definition_output":"x2/400x400 retained","low_definition_output":"x1/200x200 omitted","release_eligible":False},
}
def resolve_render_mode(name="full"):
 if name not in MODES:raise ValueError(f"unknown render mode: {name}")
 return dict(MODES[name])
def sample_policy(source_count,fps,looping):
 if source_count<1 or fps<=0:raise ValueError("invalid source sampling")
 duration=(source_count if looping else max(source_count-1,0))/fps
 count=max(1,int(math.ceil(source_count/2)))
 if looping:
  times=[duration*i/count for i in range(count)]
 else:
  times=[0.0] if count==1 else [duration*i/(count-1) for i in range(count)]
 effective=count/duration if looping and duration else ((count-1)/duration if duration else fps)
 return {"source_sample_count":source_count,"test_sample_count":count,"source_fps":fps,"test_effective_fps":effective,"source_duration":duration,"test_duration":duration,"looping":looping,"times_seconds":times}
def sample_positions(start,end,source_count,fps,looping,mode="full"):
 if mode=="full":return [start] if source_count==1 else [start+(end-start)*i/(source_count-1) for i in range(source_count)]
 policy=sample_policy(source_count,fps,looping);duration=policy["source_duration"]
 return [start if not duration else start+(end-start)*(time/duration) for time in policy["times_seconds"]]
def render_identity_payload(mode,**base):return {**base,**resolve_render_mode(mode),"sampling_policy":"deterministic-time-v1"}
def render_identity(mode,**base):return hashlib.sha256(json.dumps(render_identity_payload(mode,**base),sort_keys=True,separators=(",",":")).encode()).hexdigest()
def require_release_eligible(report):
 if report.get("render_mode","full")!="full" or not report.get("release_eligible",True):raise RuntimeError("TEST / NON-PRODUCTION render cannot satisfy release authoring")
