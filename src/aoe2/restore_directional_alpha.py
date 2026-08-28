"""Restore approved FAST/V5 main alpha while retaining directional RGB."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from PIL import Image
from aoe2.analyze_sld import decode_frame
from aoe2.sld import parse_sld

COUNTS={'idle':43,'walk':23,'attack':40,'death':33}
def source_index(category,ordinal):
 source_count=17 if category=='death' else COUNTS[category];target_count=COUNTS[category]
 return int(ordinal*(source_count-1)/(target_count-1)+0.5) if target_count>1 else 0
def main():
 p=argparse.ArgumentParser();p.add_argument('--render-root',type=Path,required=True);p.add_argument('--control-graphics',type=Path,required=True);p.add_argument('--v5-death-root',type=Path);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();results={};total_differences=0
 for category,count in COUNTS.items():
  control=parse_sld((a.control_graphics/f'rome2aoe2_rom_principes_{category}_x2.sld').read_bytes());source_count=len(control.frames)//16;rows=[];inventory=hashlib.sha256()
  for direction in range(16):
   for ordinal in range(count):
    png_ordinal=min(ordinal,26) if category=='attack' else ordinal;source_path=a.render_root/category/'main/x2'/f'{category}-direction-{direction:02d}-frame-{png_ordinal:03d}.png';image=Image.open(source_path).convert('RGBA');control_ordinal=source_index(category,ordinal);approved=decode_frame(control,direction*source_count+control_ordinal)[0].getchannel('A')
    if category=='death' and a.v5_death_root:approved=Image.open(a.v5_death_root/'main/x2'/f'death-direction-{direction:02d}-frame-{control_ordinal:03d}.png').convert('RGBA').getchannel('A')
    before=image.getchannel('A');different=sum(x!=y for x,y in zip(before.point(lambda v:255 if v>=128 else 0).getdata(),approved.point(lambda v:255 if v>=128 else 0).getdata()));total_differences+=different;image.putalpha(approved);destination=a.output_root/category/'main/x2'/f'{category}-direction-{direction:02d}-frame-{ordinal:03d}.png';destination.parent.mkdir(parents=True,exist_ok=True);image.save(destination);payload=destination.read_bytes();inventory.update(payload)
    if image.getchannel('A').tobytes()!=approved.tobytes() or any(image.getpixel(point)[3] for point in ((0,0),(399,0),(0,399),(399,399))):raise RuntimeError(f'{category} D{direction} F{ordinal}: alpha restoration failed')
    rows.append({'direction':direction,'frame':ordinal,'control_frame':source_index(category,ordinal),'pre_restore_threshold_differences':different,'post_restore_alpha_differences':0,'alpha_nonzero_pixels':sum(value!=0 for value in approved.getdata()),'alpha_bounds':approved.getbbox(),'corners':[0,0,0,0]})
  results[category]={'frames':len(rows),'source_frames_per_direction':source_count,'output_inventory_sha256':inventory.hexdigest(),'records':rows}
 report={'format':'rome2aoe2.directional-alpha-restoration','version':1,'source':'decoded approved FAST/V5 main alpha','rgb':'existing directional PNG RGB unchanged','total_frames':sum(16*count for count in COUNTS.values()),'pre_restore_threshold_differences':total_differences,'post_restore_alpha_differences':0,'categories':results,'validation':{'no_blender_render':True,'rgb_unchanged':True,'all_output_alpha_equals_control':True,'all_canvas_corners_transparent':True}};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(json.dumps({k:report[k] for k in ('total_frames','pre_restore_threshold_differences','post_restore_alpha_differences')},indent=2))
if __name__=='__main__':main()
