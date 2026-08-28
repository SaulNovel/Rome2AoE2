"""Measure, package, and enumerate the controlled Praetorian lighting sweep."""
from __future__ import annotations
import copy
import json
import math
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/"src"),str(ROOT/"third_party"/"python-deps"),str(ROOT/"third_party"/"AoE2ScenarioParser")]
VENDORED=ROOT/"build"/"python-deps"/"sld-authoring"
if VENDORED.is_dir(): sys.path.insert(0,str(VENDORED))
from PIL import Image,ImageDraw,ImageFont  # noqa: E402
from aoe2_genie_tooling import GenieWorkspace  # noqa: E402
from aoe2.sld import serialize_sld  # noqa: E402
from aoe2.sld_authoring import DirectXTexBC1Encoder,author_identical_facets  # noqa: E402
from aoe2.generate_v4_ingame_proof import downsample_about_feet,make_shadow  # noqa: E402

SWEEP=ROOT/"build"/"local-integration"/"rome2"/"lighting-sweep"
DEFINITIONS=SWEEP/"lighting-definitions.json"; SOURCE_DAT=ROOT/"test_data"/"empires2_x2_p1.dat"
TEMPLATE=ROOT/"test_data"/"EmptyMap.aoe2scenario"; TEXCONV=ROOT/"build"/"tools"/"directxtex-may2026"/"texconv.exe"
BUILD_DAT=SWEEP/"lighting_sweep.dat"; SCENARIO=SWEEP/"PraetorianLightingSweep.aoe2scenario"
MOD=SWEEP/"ROME2AOE2_LIGHTING_SWEEP"; GRAPHICS=MOD/"resources"/"_common"/"drs"/"graphics"
MOD_DAT=MOD/"resources"/"_common"/"dat"/"empires2_x2_p1.dat"
IDS=list(range(2701,2715)); FACETS=16

def percentile(values,p):
    values=sorted(values); k=(len(values)-1)*p; lo=int(k); hi=min(len(values)-1,lo+1)
    return values[lo] if lo==hi else values[lo]*(hi-k)+values[hi]*(k-lo)
def luminance(rgb): return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]
def bbox(image):
    pixels=list(image.getdata()); w=image.width; points=[(i%w,i//w) for i,p in enumerate(pixels) if p[3]>8]
    return (min(x for x,_ in points),min(y for _,y in points),max(x for x,_ in points)+1,max(y for _,y in points)+1)
def pixels_in_region(image,bounds,fractions):
    x0,y0,x1,y1=bounds; w=x1-x0; h=y1-y0; a,b,c,d=fractions
    crop=image.crop((x0+int(a*w),y0+int(b*h),x0+int(c*w),y0+int(d*h)))
    return [p[:3] for p in crop.getdata() if p[3]>8]
def mean_lum(pixels): return round(sum(luminance(p) for p in pixels)/max(1,len(pixels)),1)
def metrics(image):
    image=image.convert("RGBA"); unit=[p[:3] for p in image.getdata() if p[3]>8]; lum=[luminance(p) for p in unit]; bounds=bbox(image)
    regions={"metal":(.20,.00,.90,.22),"shield":(.00,.45,.40,1.00),"cloth":(.30,.35,.70,.80),"skin":(.35,.18,.70,.40)}
    rp={name:pixels_in_region(image,bounds,f) for name,f in regions.items()}; metal_l=[luminance(p) for p in rp["metal"]]
    saturation=sum((max(p)-min(p))/max(1,max(p)) for p in unit)/len(unit)
    lo=percentile(metal_l,.10); hi=percentile(metal_l,.90)
    return {"whole_unit_mean_luminance":round(sum(lum)/len(lum),1),"p10":round(percentile(lum,.10),1),
            "p50":round(percentile(lum,.50),1),"p90":round(percentile(lum,.90),1),"saturation":round(saturation,4),
            "metal_region_luminance":mean_lum(rp["metal"]),"shield_region_luminance":mean_lum(rp["shield"]),
            "cloth_region_luminance":mean_lum(rp["cloth"]),"skin_region_luminance":mean_lum(rp["skin"]),
            "highlight_clipping_percent":round(100*sum(max(p)>=250 for p in unit)/len(unit),3),
            "metal_highlight_shadow_ratio":round(hi/max(lo,.01),2),"opaque_bbox":list(bounds)}

def contact_sheet(candidates):
    thumb=360; label=42; sheet=Image.new("RGB",(thumb*4,(thumb+label)*4),(40,40,40)); draw=ImageDraw.Draw(sheet); font=ImageFont.load_default(size=24)
    for index,c in enumerate(candidates):
        image=Image.open(SWEEP/f'{c["id"]}.png').convert("RGBA")
        x0,y0,x1,y1=bbox(image); pad=12; image=image.crop((max(0,x0-pad),max(0,y0-pad),min(image.width,x1+pad),min(image.height,y1+pad)))
        image.thumbnail((thumb-24,thumb-16),Image.Resampling.LANCZOS)
        cell=Image.new("RGBA",(thumb,thumb),(65,65,65,255)); cell.alpha_composite(image,((thumb-image.width)//2,(thumb-image.height)//2))
        x=(index%4)*thumb; y=(index//4)*(thumb+label); sheet.paste(cell.convert("RGB"),(x,y)); draw.text((x+8,y+thumb+7),f'{c["id"]}  {c["name"]}',fill="white",font=font)
    sheet.save(SWEEP/"contact-sheet-highres.png")

def sld_for(candidate,zoom,canvas,logical,hotspot):
    source=Image.open(SWEEP/f'{candidate["id"]}.png').convert("RGBA")
    main=downsample_about_feet(source,canvas,logical,hotspot); shadow=make_shadow(main)
    one=author_identical_facets(main,shadow,FACETS,hotspot,encoder=DirectXTexBC1Encoder(TEXCONV))
    path=GRAPHICS/f'{candidate["stem"]}_{zoom}.sld'; path.write_bytes(serialize_sld(one)); return path

def build_dat(candidates):
    workspace=GenieWorkspace.load(SOURCE_DAT)
    for unit_id in IDS:
        if workspace.unit_manager.exists(unit_id): raise ValueError(f"unit {unit_id} occupied")
    for candidate,unit_id in zip(candidates,IDS):
        graphic=workspace.graphic_manager.add_graphic(candidate["stem"],name=candidate["display_name"],frame_count=1,angle_count=FACETS,frame_duration=1.0)
        unit=workspace.unit_manager.clone_into(unit_id,74,on_conflict="error",fill_gaps="placeholder")
        unit.name=candidate["display_name"]; unit.standing_sprite_id1=graphic.id; unit.standing_sprite_id2=graphic.id
        candidate.update({"unit_id":unit_id,"graphic_id":graphic.id})
    workspace.save(BUILD_DAT); MOD_DAT.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(BUILD_DAT,MOD_DAT)

def build_scenario(candidates):
    from AoE2ScenarioParser.scenarios.aoe2_de_scenario import AoE2DEScenario
    scenario=AoE2DEScenario.from_file(str(TEMPLATE)); placements=[]
    for col,(unit_id,label) in enumerate(((74,"Stock Militia"),(75,"Stock Man-at-Arms"),(1793,"Stock Legionary"))):
        x=9+col*5; y=32; scenario.unit_manager.add_unit(player=1,unit_const=unit_id,x=x,y=y,rotation=0.0); placements.append((label,unit_id,x,y))
    for index,c in enumerate(candidates):
        row=1+index//4; col=index%4; x=9+col*5; y=32-row*5
        scenario.unit_manager.add_unit(player=1,unit_const=c["unit_id"],x=x,y=y,rotation=0.0)
        c.update({"row":row,"column":col,"x":x,"y":y}); placements.append((c["id"],c["unit_id"],x,y))
    scenario.write_to_file(str(SCENARIO)); return placements

def legend(candidates,placements):
    lines=["Praetorian Lighting Sweep","All units: Player 1, rotation 0.0","", "STOCK REFERENCES"]
    lines += [f"{label}: unit {uid}, coordinate ({x}, {y})" for label,uid,x,y in placements[:3]]
    lines += ["","CANDIDATES"]
    for c in candidates: lines.append(f'{c["id"]} | row {c["row"]}, column {c["column"]} | unit {c["unit_id"]} | graphic {c["graphic_id"]} | coordinate ({c["x"]}, {c["y"]}) | {c["description"]}')
    (SWEEP/"LEGEND.txt").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    definitions=json.loads(DEFINITIONS.read_text(encoding="utf-8")); candidates=definitions["candidates"]
    for c in candidates:
        c["stem"]=f'rome2_praetorian_{c["id"].lower()}'; c["display_name"]=f'Praetorian {c["id"]} {c["name"]}'; c["metrics"]=metrics(Image.open(SWEEP/f'{c["id"]}.png'))
    contact_sheet(candidates); GRAPHICS.mkdir(parents=True,exist_ok=True); build_dat(candidates)
    for c in candidates: sld_for(c,"x1",200,50,(100,100)); sld_for(c,"x2",400,100,(200,200))
    placements=build_scenario(candidates); legend(candidates,placements)
    (MOD/"info.json").write_text(json.dumps({"Author":"Rome2AoE2","CacheStatus":0,"Description":"Controlled L00-L13 lighting comparison.","Title":"Rome2AoE2 Lighting Sweep"},indent=2)+"\n",encoding="utf-8")
    report={"format":"rome2aoe2.lighting-sweep","version":1,"fixed":{"unit":"3c_rom_roman_praetorian_guard","animation":"stand","sample":0,"camera":[45,30,8.5,12],"source_canvas":[800,800],"logical_height":50,"exposure":definitions["exposure"],"material":"V4 unchanged","chainmail":"C","player_color":False},"candidates":candidates,"scenario":str(SCENARIO),"mod_root":str(MOD),"legend":str(SWEEP/"LEGEND.txt"),"contact_sheet":str(SWEEP/"contact-sheet-highres.png")}
    (SWEEP/"lighting-sweep.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(report,indent=2,sort_keys=True)); return 0
if __name__=="__main__": raise SystemExit(main())
