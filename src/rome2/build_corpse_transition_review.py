"""Build targeted x2 death/corpse continuity and sink-timing review sheets."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/"build/python-deps/pillow")]
from PIL import Image,ImageDraw
from rome2aoe2.corpse_decay import generate_decay_images

def tile(image,label):
 out=Image.new("RGBA",(400,425),(25,25,25,255));out.alpha_composite(image);ImageDraw.Draw(out).text((8,405),label,fill="white");return out
def sheet(rows,path):
 out=Image.new("RGBA",(max(len(row) for row in rows)*400,len(rows)*425),(25,25,25,255))
 for y,row in enumerate(rows):
  for x,item in enumerate(row):out.alpha_composite(item,(x*400,y*425))
 path.parent.mkdir(parents=True,exist_ok=True);out.save(path)
def composite(main,shadow):
 out=Image.new("RGBA",main.size,(0,0,0,0));out.alpha_composite(shadow);out.alpha_composite(main);return out
def at_seconds(frames,fps,seconds):return frames[min(len(frames)-1,round(seconds*fps))]
def main():
 p=argparse.ArgumentParser();p.add_argument("--report",type=Path,required=True);p.add_argument("--old-report",type=Path,required=True);p.add_argument("--output",type=Path,required=True);a=p.parse_args();doc=json.loads(a.report.read_text());old_doc=json.loads(a.old_report.read_text());source=Path(doc["source_death_report"]);root=source.parent;count=json.loads(source.read_text())["rendered_sample_count"]
 old=old_doc["policy"];new=doc["policy"];directions=(0,4,8,12);transition=[];timing=[];snapshots=[]
 for d in directions:
  stem=f"death-direction-{d:02d}-frame-{count-1:03d}.png";main_image=Image.open(root/"main/x2"/stem).convert("RGBA");shadow_image=Image.open(root/"shadow/x2"/stem).convert("RGBA");generated=generate_decay_images(main_image,shadow_image,new);old_frames=generate_decay_images(main_image,shadow_image,old)
  transition.append([tile(main_image,f"D{d} final death main"),tile(generated[0][0],f"D{d} corpse 0 main"),tile(composite(main_image,shadow_image),f"D{d} death + shadow"),tile(composite(generated[0][0],generated[0][1]),f"D{d} corpse 0, no shadow")])
  old_times=(0,old["corpse_linger_seconds"],old["corpse_linger_seconds"]+old["corpse_sink_seconds"]*.5,old["corpse_linger_seconds"]+old["corpse_sink_seconds"]);new_times=(0,new["corpse_linger_seconds"],new["corpse_linger_seconds"]+new["corpse_sink_seconds"]*.5,new["corpse_linger_seconds"]+new["corpse_sink_seconds"])
  timing.append([tile(at_seconds(old_frames,old["corpse_fps"],t)[0],f"old {t:.1f}s") for t in old_times]+[tile(at_seconds(generated,new["corpse_fps"],t)[0],f"new {t:.1f}s") for t in new_times]);snapshots.append([tile(at_seconds(generated,new["corpse_fps"],t)[0],f"D{d} {t:.1f}s") for t in (3,8,23,38,43)])
 transition_path=a.output/"death-to-corpse-continuity-x2.png";timing_path=a.output/"corpse-sink-old-vs-new-x2.png";snapshots_path=a.output/"corpse-sink-early-mid-late-x2.png";timeline_path=a.output/"corpse-sink-compact-timeline-x2.png";sheet(transition,transition_path);sheet(timing,timing_path);sheet(snapshots,snapshots_path)
 d=0;stem=f"death-direction-{d:02d}-frame-{count-1:03d}.png";main_image=Image.open(root/"main/x2"/stem).convert("RGBA");shadow_image=Image.open(root/"shadow/x2"/stem).convert("RGBA");frames=generate_decay_images(main_image,shadow_image,new);timeline_times=(0,3,8,13,18,23,28,33,38,43);sheet([[tile(at_seconds(frames,new["corpse_fps"],t)[0],f"{t:.0f}s") for t in timeline_times]],timeline_path)
 result={"format":"rome2aoe2.corpse-transition-review","version":2,"directions":directions,"continuity_sheet":str(transition_path),"sink_sheet":str(timing_path),"snapshots_sheet":str(snapshots_path),"timeline_sheet":str(timeline_path),"old_policy":old,"new_policy":new,"equipment_linger":{"feasible":False,"reason":"single composited main layer has no body/equipment ownership mask"},"blood":{"implemented":False,"reason":"intentionally deferred"},"ground_layer":{"implemented":False,"reason":"timing, vertical translation, and clipping only"}};(a.output/"corpse-transition-review.json").write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
