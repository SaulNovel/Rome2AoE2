"""Apples-to-apples final-SLD UHD analysis for stock and Hastati candidates."""
from __future__ import annotations
import hashlib,json,math,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build/python-deps/pillow"),str(ROOT/"src")]
from PIL import Image,ImageChops,ImageDraw,ImageFilter,ImageFont
from aoe2.sld import LAYER_MAIN,LAYER_SHADOW,LAYER_PLAYERCOLOR,parse_sld,serialize_sld
from aoe2.sld_blocks import decode_bc4_block
from aoe2.analyze_sld import decode_frame
from aoe2.analyze_aoe_style_references import REFS,FACET,GRAPHICS

OUT=ROOT/"build/local-integration/rome2/aoe-style-calibration";LOCAL=OUT/"ROME2AOE2_AOE_STYLE_HASTATI/resources/_common/drs/graphics"
INSTALLED=Path(r"C:\Users\sauln\Games\Age of Empires 2 DE\0\mods\local\ROME2AOE2_AOE_STYLE_HASTATI\resources\_common\drs\graphics")
PROOF=OUT/"hastati-style-proof.json";DEC=OUT/"decoded-final-x2";BG=(47,71,48,255)
BLUE_PAL=Path(r"C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\palettes\playercolor_blue.pal")
def palette(path):
 lines=path.read_text().splitlines();return [tuple(map(int,x.split())) for x in lines[3:259]]
P1_BLUE=palette(BLUE_PAL)

def scalar_layer(frame,layer_type):
 out=Image.new("L",(frame.canvas_width,frame.canvas_height),0);present=Image.new("L",out.size,0);layer=next((l for l in frame.layers if l.layer_type==layer_type),None)
 if not layer:return out,present
 main=next(l for l in frame.layers if l.layer_type==LAYER_MAIN);cols=(main.offset_x2-main.offset_x1)//4;cursor=bi=0
 for skip,draw in layer.commands:
  cursor+=skip
  for _ in range(draw):
   x=main.offset_x1+(cursor%cols)*4;y=main.offset_y1+(cursor//cols)*4;b=decode_bc4_block(layer.blocks[bi])
   for yy in range(4):
    for xx in range(4):
     if x+xx<out.width and y+yy<out.height:out.putpixel((x+xx,y+yy),b[yy][xx]);present.putpixel((x+xx,y+yy),255)
   cursor+=1;bi+=1
 return out,present
def decode(path,index):
 raw=path.read_bytes();d=parse_sld(raw)
 if raw!=serialize_sld(d):raise ValueError(f"nondeterministic {path}")
 main,shadow=decode_frame(d,index);f=d.frames[index];pc,presence=scalar_layer(f,LAYER_PLAYERCOLOR)
 return {"doc":d,"main":main,"shadow":shadow,"pc":pc,"pc_presence":presence,"unknown_bytes":sum(len(l.raw_content) for l in f.layers if l.layer_type not in (1,2,16)),"sha256":hashlib.sha256(raw).hexdigest()}
def display(x):
 main=x["main"].convert("RGBA");pc=x["pc"];shadow=x["shadow"].convert("L");canvas=Image.new("RGBA",main.size,BG)
 # Shadow is an independent final opacity layer.
 dark=Image.new("RGBA",main.size,(10,14,10,255));canvas=Image.composite(dark,canvas,shadow)
 canvas.alpha_composite(main)
 # Exact locally installed P1 palette lookup; scalar layer values are indices.
 tinted=Image.new("RGBA",main.size);tinted.putdata([(*P1_BLUE[v],255) for v in pc.getdata()]);mask=ImageChops.multiply(x["pc_presence"],main.getchannel("A"));canvas=Image.composite(tinted,canvas,mask)
 return canvas
def metrics(x,scale=2):
 im=x["main"].convert("RGBA");a=im.getchannel("A");box=a.getbbox();body=[]
 if box:
  for r,g,b,aa in im.crop(box).getdata():
   if aa>8:
    y=.2126*r+.7152*g+.0722*b;mx=max(r,g,b);body.append((y,0 if mx==0 else (mx-min(r,g,b))/mx*255))
 ys=sorted(q[0] for q in body);sat=[q[1] for q in body];gray=im.convert("L");blur=gray.filter(ImageFilter.GaussianBlur(1.2*scale));local=[abs(v-b) for v,b,aa in zip(gray.getdata(),blur.getdata(),a.getdata()) if aa>8]
 # Acutance spans an equivalent logical distance (two x2 pixels).
 edge=[]
 for y in range(im.height):
  for xx in range(im.width):
   if a.getpixel((xx,y))<=8:continue
   x0=max(0,xx-scale);x1=min(im.width-1,xx+scale);y0=max(0,y-scale);y1=min(im.height-1,y+scale)
   edge.append((abs(gray.getpixel((x1,y))-gray.getpixel((x0,y)))+abs(gray.getpixel((xx,y1))-gray.getpixel((xx,y0))))/2)
 sh=list(x["shadow"].getdata());pc=list(x["pc_presence"].getdata());n=len(body)
 def q(p):return round(ys[int((len(ys)-1)*p)],3) if ys else 0
 return {"bbox":list(box) if box else None,"bbox_width":box[2]-box[0] if box else 0,"bbox_height":box[3]-box[1] if box else 0,"opaque_pixel_count":n,"silhouette_density":round(n/((box[2]-box[0])*(box[3]-box[1])),5) if box else 0,"luminance":{f"p{int(p*100):02d}":q(p) for p in (.05,.1,.25,.5,.75,.9,.95)},"dark_pixel_percent":round(100*sum(v<=40 for v in ys)/n,3) if n else 0,"mean_saturation":round(statistics.fmean(sat),3) if sat else 0,"local_contrast":round(statistics.fmean(local),3) if local else 0,"edge_contrast":round(statistics.fmean(edge),3) if edge else 0,"edge_acutance_p90":round(sorted(edge)[int(.9*(len(edge)-1))],3) if edge else 0,"highlight_clipping_percent":round(100*sum(v>=250 for v in ys)/n,4) if n else 0,"player_colour_coverage":round(sum(v>8 and aa>8 for v,aa in zip(pc,a.getdata()))/n,4) if n else 0,"shadow_area_pixels":sum(v>8 for v in sh),"shadow_area_relative_to_body":round(sum(v>8 for v in sh)/n,4) if n else 0,"shadow_opacity_mean":round(statistics.fmean(v for v in sh if v>0),3) if any(sh) else 0}
def quality_loss(x2,x1):
 ideal=x2["main"].resize(x1["main"].size,Image.Resampling.LANCZOS);native=x1["main"];union=ImageChops.lighter(ideal.getchannel("A"),native.getchannel("A"));vals=[]
 for a,b,m in zip(ideal.convert("RGB").getdata(),native.convert("RGB").getdata(),union.getdata()):
  if m>8:vals.extend(abs(a[i]-b[i]) for i in range(3))
 ia=ideal.getchannel("A");na=native.getchannel("A");inter=sum(a>8 and b>8 for a,b in zip(ia.getdata(),na.getdata()));uni=sum(a>8 or b>8 for a,b in zip(ia.getdata(),na.getdata()))
 return {"ideal_downsample_vs_native_x1_rgb_mae":round(statistics.fmean(vals),3) if vals else 0,"alpha_iou":round(inter/uni,5) if uni else 1,"ideal_downsample_metrics":metrics({**x2,"main":ideal,"shadow":x2["shadow"].resize(native.size,Image.Resampling.LANCZOS),"pc":x2["pc"].resize(native.size,Image.Resampling.NEAREST),"pc_presence":x2["pc_presence"].resize(native.size,Image.Resampling.NEAREST)},1),"native_x1_metrics":metrics(x1,1)}
def sheet(items,path,logical=False):
 font=ImageFont.load_default();cellw=210;cellh=180;out=Image.new("RGBA",(cellw*len(items),cellh),BG);d=ImageDraw.Draw(out)
 for i,(name,x) in enumerate(items):
  im=display(x);b=ImageChops.lighter(x["main"].getchannel("A"),x["shadow"].convert("L")).getbbox();crop=im.crop((max(0,b[0]-10),max(0,b[1]-10),min(im.width,b[2]+10),min(im.height,b[3]+10))) if b else im
  if logical:crop=crop.resize((max(1,crop.width//2),max(1,crop.height//2)),Image.Resampling.LANCZOS)
  out.alpha_composite(crop,(i*cellw+(cellw-crop.width)//2,10));d.text((i*cellw+5,155),name,fill="white",font=font)
 out.save(path)
def uhd_sheet(stocks,candidates):
 font=ImageFont.load_default();items=stocks+[(c["id"]+" "+c["name"],c["x2"]) for c in candidates];cols=4;cw,ch=240,220;rows=math.ceil(len(items)/cols)+1;out=Image.new("RGBA",(cols*cw,rows*ch),BG);d=ImageDraw.Draw(out);d.text((8,4),"UHD / x2 FINAL SLD DECODE",fill="white",font=font)
 for i,(name,x) in enumerate(items):
  row=i//cols;col=i%cols;im=display(x);b=ImageChops.lighter(x["main"].getchannel("A"),x["shadow"].convert("L")).getbbox();crop=im.crop((max(0,b[0]-8),max(0,b[1]-8),min(im.width,b[2]+8),min(im.height,b[3]+8))) if b else im
  out.alpha_composite(crop,(col*cw+(cw-crop.width)//2,row*ch+22));d.text((col*cw+5,row*ch+195),name,fill="white",font=font)
 crops=[stocks[2],stocks[1]]+[(c["id"]+" crop",c["x2"]) for c in candidates if c["id"] in ("A01","F01","F02","F03")]
 y=(rows-1)*ch+15
 for i,(name,x) in enumerate(crops):
  b=x["main"].getchannel("A").getbbox();crop=display(x).crop(b).resize(((b[2]-b[0])*2,(b[3]-b[1])*2),Image.Resampling.NEAREST);xx=i*(cols*cw//6);out.alpha_composite(crop,(xx,y));d.text((xx,y+170),name,fill="white",font=font)
 out.save(OUT/"hastati-artistic-sweep-uhd.png")
def main():
 DEC.mkdir(parents=True,exist_ok=True);stock=[];report={"format":"rome2aoe2.aoe-style-uhd-analysis","version":1,"comparison":"final decoded native x2 SLD layers","spatial_filter_scale":2,"stock":{},"custom":{},"x1_x2_quality_loss":{},"unknown_stock_layer_note":"Layer type 4 raw payload is preserved by strict parsing but has no project decoder; RGB, shadow, and player-colour final visual layers are decoded separately."}
 for key,r in REFS.items():
  z={}
  for zoom in ("x1","x2"):
   z[zoom]=decode(GRAPHICS/f"{r['stem']}_{zoom}.sld",FACET*r["frames_per_facet"])
  for kind in ("main","shadow","pc","pc_presence"):z["x2"][kind].save(DEC/f"stock-{key}-x2-{kind}.png")
  report["stock"][key]={"unit_id":r["unit_id"],"graphic_id":r["graphic_id"],"stem":r["stem"],"metrics_x2":metrics(z["x2"]),"unknown_layer_bytes":z["x2"]["unknown_bytes"]};report["x1_x2_quality_loss"]["stock-"+key]=quality_loss(z["x2"],z["x1"]);stock.append(("Stock "+key,z["x2"]))
 proof=json.loads(PROOF.read_text());custom=[]
 for c in proof["candidates"]:
  zs={}
  for zoom in ("x1","x2"):
   lp=LOCAL/f"{c['stem']}_{zoom}.sld";ip=INSTALLED/f"{c['stem']}_{zoom}.sld"
   if hashlib.sha256(lp.read_bytes()).digest()!=hashlib.sha256(ip.read_bytes()).digest():raise ValueError(f"installed mismatch {c['id']} {zoom}")
   zs[zoom]=decode(lp,0)
  report["custom"][c["id"]]={"name":c["name"],"unit_id":c["unit_id"],"graphic_id":c["graphic_id"],"stem":c["stem"],"metrics_x2":metrics(zs["x2"]),"installed_sha256_x2":zs["x2"]["sha256"]};report["x1_x2_quality_loss"][c["id"]]=quality_loss(zs["x2"],zs["x1"]);custom.append({**c,"x2":zs["x2"]})
 focus=stock+[("Current Hastati A01",next(c["x2"] for c in custom if c["id"]=="A01"))]+[(c["id"],c["x2"]) for c in custom if c["id"] in ("F01","F02","F03")]
 sheet(focus,OUT/"reference-comparison-x2-native.png",False);sheet(focus,OUT/"reference-comparison-x2-logical-scale.png",True);uhd_sheet(stock,custom)
 report["pipeline_verification"]={"x1":"master high-resolution candidate -> independent 200 canvas downsample -> x1 SLD","x2":"same master high-resolution candidate -> independent 400 canvas downsample -> x2 SLD","x2_upscaled_from_x1":False,"source":"src/aoe2/generate_hastati_style_proof.py"}
 (OUT/"aoe-reference-analysis-x2.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n");print(json.dumps({"stock":{k:v["metrics_x2"] for k,v in report["stock"].items()},"focus_custom":{k:report["custom"][k]["metrics_x2"] for k in ("A01","F01","F02","F03")}},indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
