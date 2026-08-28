"""Author non-release x2 SLDs from frozen-gain HDR diagnostic renders."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from PIL import Image
from aoe2.analyze_sld import decode_frame
from aoe2.sld import LAYER_MAIN,LAYER_SHADOW,parse_sld,serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_facet_animation

COUNTS={'idle':43,'walk':23,'attack':27,'death':33}

def _png(root:Path,category:str,direction:int,ordinal:int):
 return Image.open(root/category/'main/x2'/f'{category}-direction-{direction:02d}-frame-{ordinal:03d}.png').convert('RGBA')

def _source_shadows(path:Path,count:int):
 doc=parse_sld(path.read_bytes())
 if len(doc.frames)!=16*count:raise RuntimeError(f'{path}: expected {16*count} frames, got {len(doc.frames)}')
 shadows=[]
 for index in range(len(doc.frames)):
  alpha=decode_frame(doc,index)[1];rgba=Image.new('RGBA',alpha.size,(0,0,0,0));rgba.putalpha(alpha);shadows.append(rgba)
 return shadows

def _expand_directional_frames(frames:list,source_count:int,target_count:int):
 if source_count==target_count:return frames
 if len(frames)!=16*source_count:raise RuntimeError('directional frame inventory mismatch')
 # The approved FAST death asset samples the complete non-looping interval at
 # 17 evenly spaced points.  Map the 33 native samples to their nearest
 # approved temporal sample while retaining the 16 direction-major blocks.
 expanded=[]
 for direction in range(16):
  block=frames[direction*source_count:(direction+1)*source_count]
  for ordinal in range(target_count):
   source_ordinal=int(ordinal*(source_count-1)/(target_count-1)+0.5) if target_count>1 else 0
   expanded.append(block[source_ordinal])
 return expanded

def _author(frames,texconv:Path,path:Path,count:int):
 doc=author_facet_animation(frames,(200,244),16,count,encoder_factory=lambda:DirectXTexBC1Encoder(texconv));payload=serialize_sld(doc);again=serialize_sld(author_facet_animation(frames,(200,244),16,count,encoder_factory=lambda:DirectXTexBC1Encoder(texconv)));parsed=parse_sld(payload)
 if parsed.version!=4 or len(parsed.frames)!=16*count:raise RuntimeError('SLD parser/readback mismatch')
 if any(f.frame_type!=(LAYER_MAIN|LAYER_SHADOW) for f in parsed.frames):raise RuntimeError('SLD layer inventory mismatch')
 path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
 return {'path':str(path),'sha256':hashlib.sha256(payload).hexdigest(),'version':4,'directions':16,'frames_per_direction':count,'total_frames':len(parsed.frames),'parser_readback':True,'deterministic_repeat':payload==again}

def main():
 p=argparse.ArgumentParser();p.add_argument('--render-root',type=Path,required=True);p.add_argument('--base-graphics',type=Path,required=True);p.add_argument('--attack-tail-sld',type=Path,required=True);p.add_argument('--texconv',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--category',action='append',dest='categories');a=p.parse_args();report=a.output_root/'directional-exposure-sld-report.json';results=json.loads(report.read_text()) if a.categories and report.is_file() else {};results.pop('validation',None);selected=set(a.categories or COUNTS)
 for category,count in COUNTS.items():
  if category not in selected:continue
  source=a.attack_tail_sld if category=='attack' else a.base_graphics/f'rome2aoe2_rom_principes_{category}_x2.sld';target_count=40 if category=='attack' else count
  source_doc=parse_sld(source.read_bytes());shadow_count=len(source_doc.frames)//16
  if len(source_doc.frames)!=16*shadow_count:raise RuntimeError(f'{source}: shadow frames are not direction-major')
  shadows=_expand_directional_frames(_source_shadows(source,shadow_count),shadow_count,target_count);frames=[]
  if category=='death':
   shadow_root=a.render_root/category/'shadow/x2';shadow_root.mkdir(parents=True,exist_ok=True)
   for direction in range(16):
    for ordinal in range(count):shadows[direction*count+ordinal].save(shadow_root/f'death-direction-{direction:02d}-frame-{ordinal:03d}.png')
  for direction in range(16):
   for ordinal in range(target_count):
    source_ordinal=min(ordinal,count-1);main=_png(a.render_root,category,direction,source_ordinal);shadow=shadows[direction*target_count+ordinal];frames.append((main,shadow,None))
  results[category]=_author(frames,a.texconv,a.output_root/f'rome2aoe2_rom_principes_{category}_x2.sld',target_count)
 results['validation']={'release_eligible':False,'categories':sorted(selected),'main_source':'linear/HDR frozen-gain RGB with authoritative approved V5/FAST alpha','shadow_source':'decoded approved V5/attack-tail SLD layers; death expanded from 17 FAST samples to 33 native samples by nearest temporal sample','death_shadow_source_frames':17,'death_shadow_target_frames':33,'death_shadow_mapping':'nearest-evenly-spaced-non-looping-v1','attack_native_prefix_frames':27,'attack_held_frames':13,'attack_hold_source_ordinal':26,'attack_held_main_exact_rgba':None if 'attack' not in selected else all(_png(a.render_root,'attack',d,26).tobytes()==_png(a.render_root,'attack',d,min(i,26)).tobytes() for d in range(16) for i in range(27,40))}
 report.write_text(json.dumps(results,indent=2,sort_keys=True)+'\n');print(report)
if __name__=='__main__':main()
