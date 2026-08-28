"""Author bounded Rome-II-mask -> AoE2 runtime player-colour diagnostics."""
import json,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path[:0]=[str(ROOT/"build"/"python-deps"/"pillow"),str(ROOT/"src"),str(ROOT/"third_party"/"python-deps"),str(ROOT/"third_party"/"AoE2ScenarioParser")];V=ROOT/"build"/"python-deps"/"sld-authoring"
if V.is_dir():sys.path.insert(0,str(V))
from PIL import Image,ImageDraw,ImageFont
from aoe2_genie_tooling import GenieWorkspace
from aoe2.sld import serialize_sld
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets
from aoe2.generate_v4_ingame_proof import downsample_about_feet,make_shadow
BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration";R=BASE/"renders-set-a";MASK=BASE/"tint-masks";SOURCE_DAT=ROOT/"test_data"/"empires2_x2_p1.dat";TEMPLATE=ROOT/"test_data"/"EmptyMap.aoe2scenario";TEXCONV=ROOT/"build"/"tools"/"directxtex-may2026"/"texconv.exe"
OUT=BASE/"player-color-diagnostic";MOD=OUT/"ROME2AOE2_PLAYER_COLOR_DIAGNOSTIC";G=MOD/"resources"/"_common"/"drs"/"graphics";DAT=OUT/"player_color_diagnostic.dat";MODDAT=MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat";SCEN=OUT/"Rome2PlayerColorDiagnostic.aoe2scenario"
UNITS=[("hastati","Hastati",2851),("principes","Principes",2852),("triarii","Triarii",2853),("celtic-warriors","Celtic Warrior",2854),("praetorian","Praetorian",2855)]
def source(slug):return Image.open((ROOT/"build"/"local-integration"/"rome2"/"lighting-sweep"/"L11.png") if slug=="praetorian" else (R/f"{slug}-L11.png")).convert("RGBA")
def pc_layer(base,mask):
 out=Image.new("RGBA",base.size)
 for y in range(base.height):
  for x in range(base.width):
   b=base.getpixel((x,y));m=mask.getpixel((x,y));cov=max(m[:3])/255;lum=round((.2126*b[0]+.7152*b[1]+.0722*b[2])*cov);out.putpixel((x,y),(lum,lum,lum,b[3] if cov>.01 else 0))
 return out
def preview(rows):
 cell=(260,250);im=Image.new("RGB",(2*cell[0],len(rows)*cell[1]+24),(35,38,41));d=ImageDraw.Draw(im);d.text((8,6),"Offline mask preview only; AoE2 owns runtime palette",fill="white",font=ImageFont.load_default())
 for r,(name,base,pc) in enumerate(rows):
  for c,(label,col) in enumerate((("Player 1 blue",(45,90,230)),("Player 2 red",(220,45,40)))):
   v=base.copy();p=v.load();q=pc.load()
   for y in range(v.height):
    for x in range(v.width):
     cov=q[x,y][3]/255
     if cov: 
      l=q[x,y][0]/255;p[x,y]=(round(p[x,y][0]*(1-cov)+col[0]*l*cov),round(p[x,y][1]*(1-cov)+col[1]*l*cov),round(p[x,y][2]*(1-cov)+col[2]*l*cov),p[x,y][3])
   b=v.getchannel("A").getbbox();v=v.crop(b);v.thumbnail((170,190),Image.Resampling.LANCZOS);x=c*cell[0]+(cell[0]-v.width)//2;y=r*cell[1]+40;im.paste(v,(x,y),v);d.text((c*cell[0]+6,r*cell[1]+28),f"{name} — {label}",fill="white")
 im.save(OUT/"player-color-blue-red-preview.png")
def main():
 OUT.mkdir(parents=True,exist_ok=True);G.mkdir(parents=True,exist_ok=True);ws=GenieWorkspace.load(SOURCE_DAT);enc=DirectXTexBC1Encoder(TEXCONV);rows=[];report=[]
 for slug,name,uid in UNITS:
  stem=f"rome2_pc_{slug.replace('-','_')}";g=ws.graphic_manager.add_graphic(stem,name=f"{name} Player Color",frame_count=1,angle_count=16,frame_duration=1);u=ws.unit_manager.clone_into(uid,74,on_conflict="error",fill_gaps="placeholder");u.name=f"{name} Player Color";u.standing_sprite_id1=u.standing_sprite_id2=g.id
  src=source(slug);msrc=Image.open(MASK/f"{slug}-mask-rgb.png").convert("RGBA")
  for z,canvas,logical,h in (("x1",200,50,(100,100)),("x2",400,100,(200,200))):
   base=downsample_about_feet(src,canvas,logical,h);mask=downsample_about_feet(msrc,canvas,logical,h);pc=pc_layer(base,mask);s=author_identical_facets(base,make_shadow(base),16,h,encoder=enc,player_color=pc);(G/f"{stem}_{z}.sld").write_bytes(serialize_sld(s))
   if z=="x1":rows.append((name,base,pc))
  report.append({"unit":name,"unit_id":uid,"graphic_id":g.id,"stem":stem})
 ws.save(DAT);MODDAT.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(DAT,MODDAT);(MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Rome II tint-mask to AoE2 player-colour diagnostic.","Title":"Rome2AoE2 Player Color Diagnostic"},indent=2)+"\n")
 from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
 sc=AoE2DEScenario.from_file(str(TEMPLATE));placements=[]
 for player,x in ((1,7),(2,27)):
  for col,(stock,n) in enumerate(((74,"Militia"),(75,"Man-at-Arms"),(1793,"Legionary"))):sc.unit_manager.add_unit(player=player,unit_const=stock,x=x+col*4,y=38,rotation=0);placements.append({"player":player,"name":"Stock "+n,"x":x+col*4,"y":38})
  for row,item in enumerate(report):sc.unit_manager.add_unit(player=player,unit_const=item["unit_id"],x=x+4,y=33-row*5,rotation=0);placements.append({"player":player,"name":item["unit"],"unit_id":item["unit_id"],"x":x+4,"y":33-row*5})
 sc.write_to_file(str(SCEN));preview(rows);(OUT/"player-color-diagnostic.json").write_text(json.dumps({"format":"rome2aoe2.player-color-diagnostic","version":1,"mask_strategy":"union max(R,G,B), excluding skin/hair/leather/conductors; player layer intensity = base luminance * coverage","units":report,"placements":placements,"scenario":str(SCEN),"mod_root":str(MOD)},indent=2,sort_keys=True)+"\n");print(json.dumps(report,indent=2))
if __name__=="__main__":main()
