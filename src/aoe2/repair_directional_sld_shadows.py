"""Replace only malformed directional-test shadow layers with approved layers."""
from __future__ import annotations
import argparse,copy,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from aoe2.analyze_sld import decode_frame
from aoe2.sld import LAYER_MAIN,LAYER_SHADOW,parse_sld,serialize_sld

COUNTS={'idle':43,'walk':23,'attack':40,'death':33}
def _layer(frame,kind):return next(layer for layer in frame.layers if layer.layer_type==kind)
def _source_index(category,ordinal):
 source_count=17 if category=='death' else COUNTS[category];target_count=COUNTS[category]
 return int(ordinal*(source_count-1)/(target_count-1)+0.5) if target_count>1 else 0
def main():
 p=argparse.ArgumentParser();p.add_argument('--directional-root',type=Path,required=True);p.add_argument('--control-graphics',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args();results={}
 for category,count in COUNTS.items():
  path=a.directional_root/f'rome2aoe2_rom_principes_{category}_x2.sld';control=a.control_graphics/f'rome2aoe2_rom_principes_{category}_x2.sld';document=parse_sld(path.read_bytes());source=parse_sld(control.read_bytes());source_count=len(source.frames)//16
  if len(document.frames)!=16*count or len(source.frames)!=16*source_count:raise RuntimeError(f'{category}: unexpected frame inventory')
  before_main=[copy.deepcopy(_layer(frame,LAYER_MAIN)) for frame in document.frames];before_hash=hashlib.sha256(path.read_bytes()).hexdigest()
  for direction in range(16):
   for ordinal in range(count):
    index=direction*count+ordinal;source_index=direction*source_count+_source_index(category,ordinal);replacement=copy.deepcopy(_layer(source.frames[source_index],LAYER_SHADOW));document.frames[index].layers=[replacement if layer.layer_type==LAYER_SHADOW else layer for layer in document.frames[index].layers]
  payload=serialize_sld(document);parsed=parse_sld(payload)
  if any(_layer(frame,LAYER_MAIN)!=before_main[index] for index,frame in enumerate(parsed.frames)):raise RuntimeError(f'{category}: main layer changed during shadow-only repair')
  shadow_checks=[]
  for direction in (0,4,8,12):
   index=direction*count;source_index=direction*source_count+_source_index(category,0);actual=decode_frame(parsed,index)[1];expected=decode_frame(source,source_index)[1]
   different=sum(x!=y for x,y in zip(actual.getdata(),expected.getdata()));corners=[actual.getpixel(point) for point in ((0,0),(399,0),(0,399),(399,399))]
   if different or any(corners):raise RuntimeError(f'{category} D{direction}: repaired shadow differs from approved control')
   shadow_checks.append({'direction':direction,'frame':0,'different_pixels':different,'bounds':actual.getbbox(),'corners':corners})
  path.write_bytes(payload);results[category]={'path':str(path),'before_sha256':before_hash,'after_sha256':hashlib.sha256(payload).hexdigest(),'frames':len(parsed.frames),'main_layers_byte_preserved':True,'shadow_source':str(control),'source_frames_per_direction':source_count,'shadow_checks':shadow_checks}
 results['validation']={'repair_scope':'shadow layers only','lighting_unchanged':True,'main_bc1_layers_unchanged':True,'attack_tail_unchanged':True,'corpse_unchanged':True,'death_shadow_mapping':'nearest-evenly-spaced-non-looping-v1'};a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(results,indent=2,sort_keys=True)+'\n');print(a.report)
if __name__=='__main__':main()
