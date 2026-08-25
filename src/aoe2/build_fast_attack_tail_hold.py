"""Build a non-release x2 attack-tail hold by reusing compressed SLD frames."""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from PIL import Image,ImageDraw,ImageFont
from aoe2.analyze_sld import decode_frame
from aoe2.sld import parse_sld,serialize_sld
FONT=ImageFont.load_default()
def tail_hold_plan(source_count,frame_duration,reload_time,hold_ordinal=None):
 if source_count<1 or frame_duration<=0 or reload_time<=0:raise ValueError('attack tail timing values must be positive')
 hold=source_count-1 if hold_ordinal is None else hold_ordinal
 if not 0<=hold<source_count:raise ValueError('hold ordinal is outside the source animation')
 target_count=round(reload_time/frame_duration)
 if target_count<=source_count:raise ValueError('native attack duration must be shorter than gameplay reload')
 if abs(target_count*frame_duration-reload_time)>1e-9:raise ValueError('gameplay reload is not exactly representable at the visual frame duration')
 return {'source_count':source_count,'hold_ordinal':hold,'target_count':target_count,'extra_count':target_count-source_count,'frame_duration':frame_duration,'reload_time':reload_time}
def extend(source,facets,source_count,extra_count,hold_ordinal):
 if len(source.frames)!=facets*source_count:raise ValueError('source SLD inventory mismatch')
 frames=[]
 for direction in range(facets):
  group=source.frames[direction*source_count:(direction+1)*source_count];frames.extend(copy.deepcopy(group));frames.extend(copy.deepcopy(group[hold_ordinal]) for _ in range(extra_count))
 result=copy.deepcopy(source);result.frames=frames
 for index,frame in enumerate(result.frames):frame.frame_index=index
 return result
def same_visual_frame(left,right):
 left=copy.deepcopy(left);right=copy.deepcopy(right);left.frame_index=right.frame_index=0;return left==right
def tile(image,label):
 out=Image.new('RGBA',(image.width,image.height+22),(24,27,30,255));out.alpha_composite(image,(0,22));ImageDraw.Draw(out).text((4,5),label,font=FONT,fill='white');return out
def review(source,extended,source_count,extended_count,directions,path):
 rows=[];strike=round((source_count-1)*.44)
 for direction in directions:
  specs=((source,source_count,0,'anticipation'),(source,source_count,strike,'strike'),(source,source_count,source_count-1,'recovery'),(extended,extended_count,source_count,'held tail begins'),(extended,extended_count,extended_count-1,'held tail ends'),(source,source_count,0,'next attack start'));items=[]
  for document,count,ordinal,label in specs:
   main,shadow=decode_frame(document,direction*count+ordinal);display=Image.new('RGBA',main.size);display.putalpha(shadow);display.alpha_composite(main);items.append(tile(display,f'D{direction} F{ordinal}: {label}'))
  rows.append(items)
 width=max(sum(image.width for image in row) for row in rows);height=sum(max(image.height for image in row) for row in rows);sheet=Image.new('RGBA',(width,height),(14,16,18,255));y=0
 for row in rows:
  x=0
  for image in row:sheet.alpha_composite(image,(x,y));x+=image.width
  y+=max(image.height for image in row)
 path.parent.mkdir(parents=True,exist_ok=True);sheet.convert('RGB').save(path)
def main():
 p=argparse.ArgumentParser();p.add_argument('--source-sld',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--source-count',type=int,required=True);p.add_argument('--facets',type=int,default=16);p.add_argument('--frame-duration',type=float,required=True);p.add_argument('--reload-time',type=float,required=True);p.add_argument('--hold-ordinal',type=int);a=p.parse_args();plan=tail_hold_plan(a.source_count,a.frame_duration,a.reload_time,a.hold_ordinal);hold=plan['hold_ordinal'];target_count=plan['target_count'];extra=plan['extra_count']
 source_payload=a.source_sld.read_bytes();source=parse_sld(source_payload)
 extended=extend(source,a.facets,a.source_count,extra,hold);payload=serialize_sld(extended);repeat=serialize_sld(extend(source,a.facets,a.source_count,extra,hold));parsed=parse_sld(payload);prefix_identical=all(same_visual_frame(parsed.frames[d*target_count+i],source.frames[d*a.source_count+i]) for d in range(a.facets) for i in range(a.source_count));a.output_root.mkdir(parents=True,exist_ok=True);output=a.output_root/'rome2aoe2_attack_tail_hold_x2.sld';output.write_bytes(payload);review_path=a.output_root/'attack-anticipation-strike-recovery-held-tail-next-start-x2.png';review(source,parsed,a.source_count,target_count,(0,4,8,12),review_path)
 report={'format':'rome2aoe2.fast-attack-tail-hold','version':1,'release_eligible':False,'source_sld':str(a.source_sld),'source_sha256':hashlib.sha256(source_payload).hexdigest(),'source_frames_per_direction':a.source_count,'frame_duration':a.frame_duration,'native_visual_duration':a.source_count*a.frame_duration,'reload_time':a.reload_time,'visual_gap':a.reload_time-a.source_count*a.frame_duration,'hold_source_ordinal':hold,'extra_hold_frames':extra,'extended_frames_per_direction':target_count,'extended_visual_duration':target_count*a.frame_duration,'directions':a.facets,'total_frames':len(parsed.frames),'sequence_type_policy':'DAT sequence type unchanged','attack_event_policy':'unit frame_delay and gameplay reload unchanged; SLD-only compressed-frame duplication','deterministic':payload==repeat,'parser_readback':len(parsed.frames)==a.facets*target_count,'native_prefix_structurally_identical':prefix_identical,'output_sld':str(output),'output_sha256':hashlib.sha256(payload).hexdigest(),'review':str(review_path)};(a.output_root/'attack-tail-hold-report.json').write_text(json.dumps(report,indent=2)+'\n');print(a.output_root/'attack-tail-hold-report.json')
if __name__=='__main__':main()
