"""Compose camera-basis sign proof and within-sprite left/right review."""
import argparse,json,math,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'build/python-deps/pillow'))
from PIL import Image,ImageDraw,ImageFont
FONT=ImageFont.load_default()
def main():
 p=argparse.ArgumentParser();p.add_argument('audit',type=Path);a=p.parse_args();d=json.loads(a.audit.read_text());out=a.audit.parent;names=list(d['variants']);by={(r['candidate'],r['direction']):r for r in d['records']}
 # Explicit image-coordinate sign proof: positive screen X is camera-right.
 basis=Image.new('RGB',(1200,360),(18,20,22));g=ImageDraw.Draw(basis);origin=(300,190);g.line((80,190,520,190),fill=(180,180,180),width=3);g.polygon(((520,190),(500,180),(500,200)),fill=(255,190,60));g.text((70,210),'SCREEN-LEFT  (-image X)',font=FONT,fill='white');g.text((430,210),'SCREEN-RIGHT  (+image X)',font=FONT,fill=(255,210,90));g.line((origin[0],300,origin[0],70),fill=(180,180,180),width=3);g.polygon(((300,70),(290,90),(310,90)),fill=(160,210,255));g.text((315,75),'camera-up',font=FONT,fill=(160,210,255));g.text((40,25),'Positive key rotation is toward rendered screen-right',font=FONT,fill='white');g.text((590,45),f"view camera->target: {d['camera_basis']['view_camera_to_target']}",font=FONT,fill='white');g.text((590,85),f"camera-right: {d['camera_basis']['screen_right']}",font=FONT,fill=(255,210,90));g.text((590,125),f"camera-up: {d['camera_basis']['screen_up']}",font=FONT,fill=(160,210,255));g.text((590,175),d['rotation']['equation'],font=FONT,fill='white');g.text((590,215),f"dot(up x L0, right) = {d['rotation']['dot_positive_tangent_screen_right']:.9f}",font=FONT,fill='white');basis.save(out/'camera-right-sign-proof.png')
 dirs=(2,4,6,10,12,14);tilew=300;tileh=330;sheet=Image.new('RGB',(len(names)*tilew,len(dirs)*tileh),(12,14,16));draw=ImageDraw.Draw(sheet)
 for row,direction in enumerate(dirs):
  for col,name in enumerate(names):
   r=by[name,direction];im=Image.open(r['output']).convert('RGBA');bbox=im.getchannel('A').getbbox();crop=im.crop((max(0,bbox[0]-30),max(0,bbox[1]-25),min(400,bbox[2]+30),min(400,bbox[3]+25)));crop.thumbnail((270,265),Image.Resampling.LANCZOS);x=col*tilew+(tilew-crop.width)//2;y=row*tileh+45;sheet.paste(crop.convert('RGB'),(x,y));split=col*tilew+tilew//2;draw.line((split,y,split,y+crop.height),fill=(80,180,255),width=1);lm=r['metrics']['screen_left']['mean'];rm=r['metrics']['screen_right']['mean'];draw.text((col*tilew+5,row*tileh+6),f'{name} D{direction}',font=FONT,fill='white');draw.text((col*tilew+5,row*tileh+22),f'SCREEN-L {lm:.3f} | SCREEN-R {rm:.3f} | R-L {r["screen_right_minus_left_relative"]:+.3f}',font=FONT,fill=(190,210,230))
 sheet.save(out/'screen-left-versus-right-surfaces.png')
 strong=[n for n in names if n.startswith('camera-right-') and int(n.rsplit('-',1)[1])>=30]
 def comparison(path,scale):
  directions=(2,3,4,5,6,10,11,12,13,14);w=round(400*scale);h=w+20;canvas=Image.new('RGB',(len(strong)*w,len(directions)*h),(12,14,16));pen=ImageDraw.Draw(canvas)
  for row,direction in enumerate(directions):
   for col,name in enumerate(strong):
    im=Image.open(by[name,direction]['output']).convert('RGBA').resize((w,w),Image.Resampling.LANCZOS);canvas.paste(im.convert('RGB'),(col*w,row*h+20));pen.text((col*w+4,row*h+4),f'{name} D{direction}',font=FONT,fill='white')
  canvas.save(path)
 comparison(out/'right-30-40-50-60-focused-x2.png',1.0);comparison(out/'right-30-40-50-60-focused-game-scale.png',.25)
if __name__=='__main__':main()
