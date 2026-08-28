"""Compose requested source-material reconstruction diagnostics."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"build"/"python-deps"/"pillow"))
from PIL import Image,ImageDraw,ImageFont
MR=ROOT/"build"/"local-integration"/"rome2"/"material-reconstruction";R=MR/"renders";CU=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";FONT=ImageFont.load_default()
UNITS=[("hastati","Hastati"),("principes","Principes"),("triarii","Triarii"),("velites","Velites"),("hoplites","Hoplites"),("celtic-warriors","Celtic Warriors"),("eastern-spearmen","Eastern Spearmen")]
def fit(im,size):
 b=im.getchannel("A").getbbox();im=im.crop(b) if b else im;im.thumbnail((size[0]-20,size[1]-35),Image.Resampling.LANCZOS);o=Image.new("RGBA",size,(26,29,32,255));o.alpha_composite(im,((size[0]-im.width)//2,(size[1]-im.height)//2+8));return o
def sheet(rows,cols,path,title,cell=(280,280)):
 o=Image.new("RGBA",(cols*cell[0],28+rows*cell[1]),(20,22,25,255));d=ImageDraw.Draw(o);d.text((8,8),title,font=FONT,fill="white")
 return o,d,cell
def faction():
 allu=UNITS+[("praetorian","Praetorian")];o,d,c=sheet(len(allu),5,MR/"faction-channel-semantics.png","Exact Rome faction equation; TEST colours only")
 for y,(s,n) in enumerate(allu):
  for x,k in enumerate(("neutral","R","G","B","RGB")):
   t=fit(Image.open(R/f"{s}-faction-{k}.png").convert("RGBA"),c);o.alpha_composite(t,(x*c[0],28+y*c[1]));d.text((x*c[0]+5,28+y*c[1]+5),f"{n} {k}",font=FONT,fill="white")
 o.convert("RGB").save(MR/"faction-channel-semantics.png")
def comparisons():
 for filename,title,paths in (("normal-before-after.png","Rome packed normals under fixed L11",[(s,n,R/f"{s}-normal-off.png",R/f"{s}-reconstructed.png") for s,n in UNITS]),("material-reconstruction-v1.png","Current baseline vs source-semantic reconstruction, fixed L11",[(s,n,CU/"renders-set-a"/f"{s}-L11.png",R/f"{s}-reconstructed.png") for s,n in UNITS])):
  o,d,c=sheet(7,2,MR/filename,title,(360,300))
  for y,(s,n,a,b) in enumerate(paths):
   for x,(lab,p) in enumerate((("OFF" if filename.startswith('normal') else "current baseline",a),("ON" if filename.startswith('normal') else "reconstructed",b))):o.alpha_composite(fit(Image.open(p).convert("RGBA"),c),(x*c[0],28+y*c[1]));d.text((x*c[0]+5,28+y*c[1]+5),f"{n} — {lab}",font=FONT,fill="white")
  o.convert("RGB").save(MR/filename)
 # Gameplay scale
 o,d,c=sheet(7,2,MR/"material-reconstruction-v1-gameplay-scale.png","AoE2 x1 logical height 50 px",(250,150))
 for y,(s,n) in enumerate(UNITS):
  for x,(lab,p) in enumerate((("baseline",CU/"renders-set-a"/f"{s}-L11.png"),("reconstructed",R/f"{s}-reconstructed.png"))):
   im=Image.open(p).convert("RGBA");b=im.getchannel("A").getbbox();im=im.crop(b);im=im.resize((max(1,round(im.width*50/im.height)),50),Image.Resampling.LANCZOS);o.alpha_composite(im,(x*c[0]+(c[0]-im.width)//2,28+y*c[1]+55));d.text((x*c[0]+5,28+y*c[1]+5),f"{n} {lab}",font=FONT,fill="white")
 o.convert("RGB").save(MR/"material-reconstruction-v1-gameplay-scale.png")
def player():
 o,d,c=sheet(7,3,MR/"player-color-v2.png","AoE prototype v2: Rome R channel only; preview palette",(320,285))
 for y,(s,n) in enumerate(UNITS):
  base=Image.open(R/f"{s}-reconstructed.png").convert("RGBA");mask=Image.open(CU/"tint-masks"/f"{s}-mask-rgb.png").convert("RGBA").resize(base.size)
  for x,(lab,col) in enumerate((("neutral",None),("AoE blue",(45,90,230)),("AoE red",(220,45,40)))):
   im=base.copy();p=im.load();m=mask.load()
   if col:
    for yy in range(im.height):
     for xx in range(im.width):
      q=p[xx,yy];cov=m[xx,yy][0]/255
      if q[3]>8 and cov>.01:
       # Same source multiplicative/lerp behavior, one AoE-owned colour.
       p[xx,yy]=(round(q[0]*((1-cov)+cov*col[0]/255)),round(q[1]*((1-cov)+cov*col[1]/255)),round(q[2]*((1-cov)+cov*col[2]/255)),q[3])
   o.alpha_composite(fit(im,c),(x*c[0],28+y*c[1]));d.text((x*c[0]+5,28+y*c[1]+5),f"{n} — {lab}",font=FONT,fill="white")
 o.convert("RGB").save(MR/"player-color-v2.png")
def decals():
 cases=[("Celtic shield","celtic-warriors","celtic_oval_shield_diffuse.dds","celtic_oval_shield_decalmask.dds","oval_celtic_chequed_01_diffuse.dds"),("Roman scutum","hastati","roman_early_scutuma_diffuse.dds","roman_early_scutuma_decalmask.dds","legionary_early_01_diffuse.dds"),("Hoplite shield","hoplites","hel_hoplon_paint2_diffuse.dds","hel_hoplon_decalmask.dds","round_shield_barbarian_diffuse.dds")]
 o,d,c=sheet(len(cases),2,MR/"decal-before-after.png","Texture-space decal diagnostic: first array entry only; runtime slice unresolved",(400,330));cand=MR/"decal-candidates"
 for y,(name,slug,bn,mn,dn) in enumerate(cases):
  root=CU/"units"/slug/"textures";bp=next(root.rglob(bn));mp=next(root.rglob(mn));dp=next(cand.rglob(dn));base=Image.open(bp).convert("RGBA");mask=Image.open(mp).convert("RGBA").resize(base.size);dec=Image.open(dp).convert("RGBA").resize(base.size);alpha=mask.getchannel("R");alpha=Image.eval(alpha,lambda v:min(255,v));comp=Image.composite(dec,base,alpha)
  for x,(lab,im) in enumerate((("before",base),("diagnostic composition",comp))):im.thumbnail((360,270));tile=Image.new("RGBA",c,(26,29,32,255));tile.alpha_composite(im,((c[0]-im.width)//2,35));o.alpha_composite(tile,(x*c[0],28+y*c[1]));d.text((x*c[0]+5,28+y*c[1]+5),f"{name} — {lab}",font=FONT,fill="white")
 o.convert("RGB").save(MR/"decal-before-after.png")
if __name__=="__main__":faction();comparisons();player();decals()
