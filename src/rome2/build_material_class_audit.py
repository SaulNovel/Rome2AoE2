"""Build a readable report/contact sheet from the reusable Blender class audit."""
from __future__ import annotations
import json
from pathlib import Path
from xml.etree import ElementTree
import sys
ROOT=Path(__file__).resolve().parents[2]; V=ROOT/"build"/"python-deps"/"sld-authoring"
if V.is_dir(): sys.path.insert(0,str(V))
from PIL import Image,ImageDraw,ImageFont  # noqa: E402
OUT=ROOT/"build"/"local-integration"/"rome2"/"material-class-audit"
VMD=ROOT/"build"/"local-integration"/"rome2"/"variantmeshes"/"variantmeshdefinitions"/"3c_rom_roman_praetorian_guard.variantmeshdefinition"

REGIONS=[
 {"region":"face","model":"3c_roman_headhands_skin1_shape1","mesh":"Mesh_1","material":"roman_1_head","current":"dielectric","expected":"skin","result":"pass"},
 {"region":"neck","model":"3c_roman_headhands_skin1_shape1","mesh":"Mesh_1","material":"roman_1_head","current":"dielectric","expected":"skin","result":"pass"},
 {"region":"upper arms","model":"celtic_basic_tunic_01_cut + 3c_roman_lorica_hamata_cape","mesh":"Mesh_0/Mesh_0.005","material":"lorica_hamata_A + celtic_basic_tunic_cut_01","current":"mixed conductor/dielectric","expected":"iron/steel protection + cloth","result":"pass"},
 {"region":"forearms below elbow","model":"3c_roman_headhands_skin1_shape1","mesh":"Mesh_0.004","material":"roman_body1","current":"dielectric","expected":"skin","result":"pass"},
 {"region":"hands","model":"3c_roman_headhands_skin1_shape1","mesh":"Mesh_0.004","material":"roman_body1","current":"dielectric","expected":"skin","result":"pass"},
 {"region":"thighs","model":"3c_aurelian_pants","mesh":"Mesh_0.003","material":"3c_aurelian_pants","current":"dielectric classified as trousers","expected":"cloth","result":"pass"},
 {"region":"lower legs","model":"3c_aurelian_pants","mesh":"Mesh_0.003","material":"3c_aurelian_pants","current":"dielectric classified as trousers","expected":"skin","result":"fail"},
 {"region":"feet/sandals","model":"3c_aurelian_pants","mesh":"Mesh_0.003","material":"3c_aurelian_pants","current":"dielectric classified as trousers","expected":"leather + skin","result":"fail"},
 {"region":"torso chainmail","model":"3c_roman_lorica_hamata_cape","mesh":"Mesh_0","material":"lorica_hamata_A","current":"mixed mask conductor/dielectric","expected":"iron/steel rings + backing","result":"pass"},
 {"region":"shoulder/arm protection","model":"3c_roman_lorica_hamata_cape","mesh":"Mesh_0","material":"lorica_hamata_A","current":"mixed mask conductor/dielectric","expected":"iron/steel","result":"pass"},
]

def variants():
    root=ElementTree.parse(VMD).getroot(); result=[]
    for slot in root.iter("SLOT"):
        if slot.get("name")!="trousers": continue
        for index,node in enumerate([child for child in slot if child.tag=="VARIANT_MESH"]):
            result.append({"index":index,"model":node.get("model"),"mask0":node.get("mask0"),"mask1":node.get("mask1"),"mask2":node.get("mask2")})
        if result: break
    return result
def contact():
    views=[]
    for az in (45,135,225,315):
        image=Image.open(OUT/f"material-classes-{az:03d}.png").convert("RGB"); bg=image.getpixel((0,0)); px=image.load(); pts=[(x,y) for y in range(image.height) for x in range(image.width) if sum(abs(px[x,y][i]-bg[i]) for i in range(3))>24]
        x0=min(x for x,_ in pts);y0=min(y for _,y in pts);x1=max(x for x,_ in pts)+1;y1=max(y for _,y in pts)+1
        crop=image.crop((max(0,x0-20),max(0,y0-20),min(image.width,x1+20),min(image.height,y1+20))); crop.thumbnail((500,620),Image.Resampling.LANCZOS); views.append((az,crop))
    sheet=Image.new("RGB",(1000,1380),(42,42,42)); draw=ImageDraw.Draw(sheet); font=ImageFont.load_default(size=22)
    for i,(az,image) in enumerate(views):
        x=(i%2)*500+(500-image.width)//2;y=(i//2)*670;sheet.paste(image,(x,y+35));draw.text(((i%2)*500+12,y+6),f"azimuth {az}°",fill="white",font=font)
    legend="pink skin | yellow bronze | blue iron/steel | green cloth | brown leather | purple other"
    draw.text((15,1350),legend,fill="white",font=ImageFont.load_default(size=18)); sheet.save(OUT/"material-class-contact-sheet.png")
def main():
    source=json.loads((OUT/"material-class-audit.json").read_text(encoding="utf-8")); vs=variants(); contact()
    report={"format":"rome2aoe2.anatomical-material-audit","version":1,"unit":"3c_rom_roman_praetorian_guard","regions":REGIONS,
      "hard_constraint_pass":False,"blocking_findings":["Selected 3c_aurelian_pants geometry/material covers lower legs and feet; its diffuse depicts trousers/footwear rather than exposed calf skin.","Gladius is one whole conductor-class material, so blade classification also reaches grip/scabbard geometry.","Pilum is one whole conductor-class material, so its wooden shaft would become metallic when visible."],
      "verified":["roman_1_head and roman_body1 are dielectric and absent from conductor lists.","Forearms and hands are roman_body1 skin geometry; chainmail/helmet are separate meshes.","Shield body and boss are separate objects/materials; only the boss material is conductor-class."],
      "trouser_slot_variants":vs,"variant_conclusion":"All four variants use the same 3c_aurelian_pants model. First-variant policy selects index 0 because it is first; later entries only add mask attributes and none supplies bare-leg geometry.",
      "blender_object_audit":source,"contact_sheet":str(OUT/"material-class-contact-sheet.png"),"pants_diffuse":str(OUT/"3c_aurelian_pants_diffuse.png")}
    (OUT/"anatomical-material-audit.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8")
if __name__=="__main__": main()
