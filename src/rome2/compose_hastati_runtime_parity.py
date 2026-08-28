"""Compose the single runtime-parity proof; no colour or material processing."""
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/"build/python-deps/pillow"))
from PIL import Image,ImageDraw,ImageFont

OUT=ROOT/"build/local-integration/rome2/runtime-parity-proof"
P5=ROOT/"build/local-integration/rome2/hastati-ca-structured-ab/masters/P5_CONTROL_F03.png"
PARITY=OUT/"runtime-parity-f03.png"
PREVIOUS=OUT/"runtime-parity-f03-camera-yaw-control.png"
RUNTIME=Path(r"C:\Program Files (x86)\Steam\userdata\128135655\760\remote\214950\screenshots\20260809202533_1.jpg")

def alpha_crop(im,pad=12):
    box=im.getchannel("A").getbbox(); x0,y0,x1,y1=box
    return im.crop((max(0,x0-pad),max(0,y0-pad),min(im.width,x1+pad),min(im.height,y1+pad)))

def contain(im,size,bg=(35,38,40,255)):
    result=Image.new("RGBA",size,bg); copy=im.copy(); copy.thumbnail((size[0]-24,size[1]-24),Image.Resampling.LANCZOS)
    result.alpha_composite(copy,((size[0]-copy.width)//2,(size[1]-copy.height)//2)); return result

def label(draw,x,text): draw.text((x+12,10),text,fill="white",font=ImageFont.load_default(20))

def main():
    p5=Image.open(P5).convert("RGBA"); previous=Image.open(PREVIOUS).convert("RGBA")
    parity=Image.open(PARITY).convert("RGBA"); runtime=Image.open(RUNTIME).convert("RGBA")
    pre_skin=Image.open(OUT/"runtime-parity-f03-pre-skin.png").convert("RGBA")
    # One unobscured central runtime soldier, retained with its untouched battlefield background.
    runtime_unit=runtime.crop((900,365,1245,930))
    panels=[contain(alpha_crop(p5),(500,820)),contain(alpha_crop(previous),(500,820)),contain(alpha_crop(parity),(500,820)),contain(runtime_unit,(500,820))]
    sheet=Image.new("RGBA",(2000,870),(22,24,26,255)); draw=ImageDraw.Draw(sheet)
    for i,p in enumerate(panels): sheet.alpha_composite(p,(i*500,50))
    for i,t in enumerate(("P5 CONTROL","PREVIOUS CAMERA-YAW","CORRECTED GLOBAL BASIS","ROME II RUNTIME")): label(draw,i*500,t)
    sheet.convert("RGB").save(OUT/"comparison-sheet.png",quality=95)

    pc=alpha_crop(p5,0); qc=alpha_crop(parity,0)
    # Normalised regions are identical for the two offline renders.
    regions={"HELMET":(.20,0,.80,.28),"CUIRASS":(.12,.20,.88,.50),"TUNIC":(.10,.42,.90,.72),"BRONZE / TUNIC":(.08,.25,.92,.65),"SKIN":(0,.25,1,.72)}
    runtime_regions={"HELMET":(80,20,255,190),"CUIRASS":(65,125,285,350),"TUNIC":(50,150,310,470),"BRONZE / TUNIC":(45,100,315,470),"SKIN":(35,90,330,470)}
    close=Image.new("RGBA",(1800,len(regions)*380),(22,24,26,255)); draw=ImageDraw.Draw(close)
    for row,(name,r) in enumerate(regions.items()):
        y=row*380; draw.text((12,y+8),name,fill="white",font=ImageFont.load_default(20))
        for col,im in enumerate((pc,qc)):
            x0=int(r[0]*im.width); y0=int(r[1]*im.height); x1=int(r[2]*im.width); y1=int(r[3]*im.height)
            close.alpha_composite(contain(im.crop((x0,y0,x1,y1)),(600,340)),(col*600,y+40))
        close.alpha_composite(contain(runtime_unit.crop(runtime_regions[name]),(600,340)),(1200,y+40))
    close.convert("RGB").save(OUT/"material-closeups.png",quality=95)

    before_crop=alpha_crop(pre_skin,0); after_crop=alpha_crop(parity,0); region=(0,.22,1,.76)
    skin_sheet=Image.new("RGBA",(1200,650),(22,24,26,255)); sd=ImageDraw.Draw(skin_sheet)
    for col,(label_text,im) in enumerate((("BEFORE: FALLBACK SKIN",before_crop),("AFTER: VALIDATED EVENT-1926 SKIN",after_crop))):
        x0=int(region[0]*im.width); y0=int(region[1]*im.height); x1=int(region[2]*im.width); y1=int(region[3]*im.height)
        skin_sheet.alpha_composite(contain(im.crop((x0,y0,x1,y1)),(600,600)),(col*600,50)); label(sd,col*600,label_text)
    skin_sheet.convert("RGB").save(OUT/"skin-before-after.png",quality=95)

    pre_shield=alpha_crop(Image.open(OUT/"runtime-parity-f03-pre-shield.png").convert("RGBA"),0)
    # The deterministic facet-03 unit carries the scutum on image-right.
    shield_region=(.52,.28,1,.98)
    shield_sheet=Image.new("RGBA",(1400,760),(22,24,26,255)); sh=ImageDraw.Draw(shield_sheet)
    for col,(label_text,im) in enumerate((("BEFORE: SHIELD FALLBACK",pre_shield),("AFTER: VALIDATED DECALDIRTMAP",after_crop))):
        x0=int(shield_region[0]*im.width); y0=int(shield_region[1]*im.height); x1=int(shield_region[2]*im.width); y1=int(shield_region[3]*im.height)
        shield_sheet.alpha_composite(contain(im.crop((x0,y0,x1,y1)),(700,700)),(col*700,50)); label(sh,col*700,label_text)
    shield_sheet.convert("RGB").save(OUT/"shield-before-after.png",quality=95)

    debug_names=("debug-a-base-normal.png","debug-b-final-normal.png","debug-c-ndotl.png",
                 "debug-d-reflection.png","debug-e-diffuse-only.png","debug-f-environment-specular-only.png")
    debug_labels=("A BASE WORLD NORMAL","B FINAL WORLD NORMAL","C NdotL","D REFLECTION DIRECTION","E DIFFUSE ONLY","F ENV SPECULAR ONLY")
    debug=Image.new("RGBA",(1800,1240),(22,24,26,255)); dd=ImageDraw.Draw(debug)
    for i,(name,text) in enumerate(zip(debug_names,debug_labels)):
        x=(i%3)*600; y=(i//3)*620
        dd.text((x+12,y+10),text,fill="white",font=ImageFont.load_default(20))
        im=alpha_crop(Image.open(OUT/name).convert("RGBA"))
        debug.alpha_composite(contain(im,(600,570)),(x,y+50))
    debug.convert("RGB").save(OUT/"debug-aov-sheet.png",quality=95)

if __name__=="__main__": main()
