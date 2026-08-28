"""Compose diagnostic-only skin routing and contribution sheets."""
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'build/python-deps/pillow'))
from PIL import Image,ImageDraw,ImageFont

OUT=ROOT/'build/local-integration/rome2/runtime-parity-proof';AUD=OUT/'skin-integration-audit';font=ImageFont.load_default(20)
def contain(im,size):
 r=Image.new('RGBA',size,(27,30,32,255));q=im.copy();q.thumbnail((size[0]-20,size[1]-20),Image.Resampling.LANCZOS);r.alpha_composite(q,((size[0]-q.width)//2,(size[1]-q.height)//2));return r
def main():
 raw=Image.open(OUT/'debug-skin-family-routing.png').convert('RGBA');raw.save(AUD/'routing-full.png');box=raw.convert('RGB').getbbox();box=(max(0,box[0]-20),max(0,box[1]-20),min(raw.width,box[2]+20),min(raw.height,box[3]+20))
 routing=Image.new('RGBA',(1100,900),(22,24,26,255));d=ImageDraw.Draw(routing);routing.alpha_composite(contain(raw.crop(box),(1100,820)),(0,60));d.text((16,14),'RED: roman_body1 (arms, hands, torso, exposed legs)',fill='white',font=font);d.text((16,36),'CYAN: roman_1_head',fill='white',font=font);routing.convert('RGB').save(OUT/'debug-skin-family-routing.png',quality=95)
 names=[('a-source-linear-diffuse.png','A SOURCE / LINEAR DIFFUSE'),('b-skin-mask.png','B SKIN MASK RGB'),('c-world-normal.png','C WORLD NORMAL'),('d-raw-ndotl.png','D RAW NdotL'),('e-wrapped-skin-diffuse.png','E WRAPPED DIRECT DIFFUSE'),('f-six-colour-ambient-diffuse.png','F SIX-COLOUR AMBIENT DIFFUSE'),('g-grazing-ambient-scatter.png','G GRAZING AMBIENT SCATTER'),('h-backscatter.png','H BACKSCATTER'),('i-direct-specular.png','I DIRECT SPECULAR'),('j-final-linear-hdr.png','J FINAL LINEAR HDR')]
 final=Image.open(OUT/'runtime-parity-f03.png').convert('RGBA').crop(box);panels=[]
 for name,label in names:panels.append((Image.open(AUD/name).convert('RGBA').crop(box),label))
 panels.append((final,'K FINAL DISPLAY OUTPUT'))
 sheet=Image.new('RGBA',(1600,3*520),(22,24,26,255));sd=ImageDraw.Draw(sheet)
 for i,(im,label) in enumerate(panels):x=(i%4)*400;y=(i//4)*520;sheet.alpha_composite(contain(im,(400,470)),(x,y+45));sd.text((x+10,y+12),label,fill='white',font=font)
 sheet.convert('RGB').save(OUT/'skin-light-contribution-sheet.png',quality=95)
 before=Image.open(OUT/'runtime-parity-f03-pre-skin-mask-fix.png').convert('RGBA').crop(box);after=final;cmp=Image.new('RGBA',(1200,800),(22,24,26,255));cd=ImageDraw.Draw(cmp)
 for i,(im,label) in enumerate(((before,'BEFORE: DIRT-ATTENUATED SKIN MASK'),(after,'AFTER: RT2 = UNTOUCHED SKIN MASK'))):cmp.alpha_composite(contain(im,(600,740)),(i*600,50));cd.text((i*600+12,14),label,fill='white',font=font)
 cmp.convert('RGB').save(OUT/'skin-mask-fix-before-after.png',quality=95)
 report=json.loads((AUD/'report.json').read_text());corrected=Image.open(OUT/'runtime-parity-f03.png').convert('RGB')
 for t in report['traces']:t['corrected_render_rgb']=[v/255 for v in corrected.getpixel(tuple(t['pixel']))]
 (AUD/'report.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
