"""Build all-facing review sheets from an optimized physical corpse report."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT),str(ROOT/'src'),str(ROOT/'build/python-deps/pillow')]
from PIL import Image,ImageDraw,ImageFont
from rome2aoe2.corpse_decay import generate_physical_ground_images,read_float32_height
FONT=ImageFont.load_default();PICKS=(0,13,27,40,53)
def tile(image,label,scale):
 if scale!=1:image=image.resize((round(image.width*scale),round(image.height*scale)),Image.Resampling.LANCZOS)
 out=Image.new('RGBA',(image.width,image.height+22),(24,27,30,255));out.alpha_composite(image,(0,22));ImageDraw.Draw(out).text((4,5),label,font=FONT,fill='white');return out
def sheet(rows,path,scale):
 rows=[[tile(image,label,scale) for image,label in row] for row in rows];width=max(sum(image.width for image in row) for row in rows);height=sum(max(image.height for image in row) for row in rows);out=Image.new('RGBA',(width,height),(14,16,18,255));y=0
 for row in rows:
  x=0
  for image in row:out.alpha_composite(image,(x,y));x+=image.width
  y+=max(image.height for image in row)
 path.parent.mkdir(parents=True,exist_ok=True);out.convert('RGB').save(path)
def main():
 p=argparse.ArgumentParser();p.add_argument('--corpse-report',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();report=json.loads(a.corpse_report.read_text());colour_report=Path(report['source_death_report']);colour=json.loads(colour_report.read_text());height_report_path=Path(report['world_height_report']);height_report=json.loads(height_report_path.read_text());height_rows={int(row['direction']):row for row in height_report['directions']};rows=[]
 for direction in range(16):
  source=Image.open(colour_report.parent/'main/x2'/f"death-direction-{direction:02d}-frame-{int(colour['rendered_sample_count'])-1:03d}.png").convert('RGBA');heights=read_float32_height(height_rows[direction]['height_f32'],source.width,source.height);frames,_=generate_physical_ground_images(source,heights,report['policy'],height_report['geometry']['required_world_sink'],height_report['camera']['negative_world_z_screen_vector_x2']);rows.append([(frames[index][0],f'D{direction} {fraction}%') for index,fraction in zip(PICKS,(0,25,50,75,100))])
 full=a.output/'corpse-physical-world-height-0-25-50-75-100-x2.png';game=a.output/'corpse-physical-world-height-game-scale.png';sheet(rows,full,1);sheet(rows,game,.5);result={'format':'rome2aoe2.physical-world-height-corpse-review','version':1,'directions':16,'fractions':[0,.25,.5,.75,1],'outputs':[str(full),str(game)]};(a.output/'physical-world-height-review.json').write_text(json.dumps(result,indent=2)+'\n')
if __name__=='__main__':main()
