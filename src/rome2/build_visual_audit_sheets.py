"""Compose compact review sheets from exact-backend diagnostic renders."""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "build/python-deps/pillow"))
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"build/diagnostics/principes-visual-audit-v1"

def label(im,text,height=22):
    out=Image.new("RGBA",(im.width,im.height+height),(24,24,24,255));out.paste(im,(0,height));ImageDraw.Draw(out).text((4,4),text,fill="white");return out

def grid(items,cols,path):
    w=max(i.width for i in items);h=max(i.height for i in items);rows=(len(items)+cols-1)//cols
    out=Image.new("RGBA",(w*cols,h*rows),(12,12,12,255))
    for n,im in enumerate(items):out.paste(im,((n%cols)*w,(n//cols)*h))
    out.save(path)

def crop_close(path):
    im=Image.open(path).convert("RGBA"); a=im.getchannel("A"); box=a.getbbox()
    if not box:return im
    x0,y0,x1,y1=box;cx=(x0+x1)//2;cy=(y0+y1)//2;span=max(x1-x0,y1-y0);span=int(span*1.15)
    box=(max(0,cx-span//2),max(0,cy-span//2),min(im.width,cx+span//2),min(im.height,cy+span//2))
    return im.crop(box).resize((320,320),Image.Resampling.LANCZOS)

def main():
    lighting=json.loads((BASE/"lighting/lighting-diagnostic.json").read_text())
    for policy in lighting["policies"]:
        rows=sorted((r for r in lighting["records"] if r["policy"]==policy),key=lambda r:r["direction"])
        items=[]
        for r in rows:
            m=r["metrics"]; text=f"D{r['direction']:02d} yaw {r['root_yaw_degrees']:.1f} dark {m['dark_pixel_percentage']:.0f}% shield {m['shield']['mean']:.2f}"
            items.append(label(Image.open(r["output"]).convert("RGBA"),text))
        grid(items,4,BASE/"lighting"/f"{policy}-16-directions.png")
    selected=[]
    for mode in ("source","current","full-frame"):
        for phase in range(3):
            p=BASE/"weapon"/f"sws_sync_atk_005-{mode}-phase-{phase}-direction-00.png"
            selected.append(label(crop_close(p),f"{mode} phase {phase}"))
    grid(selected,3,BASE/"weapon"/"attack005-source-current-full-frame.png")
    candidates=[]
    for clip in range(1,6):
        for phase in range(3):
            p=BASE/"weapon"/f"sws_sync_atk_{clip:03d}-full-frame-phase-{phase}-direction-00.png"
            candidates.append(label(crop_close(p),f"attack {clip:03d} phase {phase}"))
    grid(candidates,3,BASE/"weapon"/"five-attack-candidates-full-frame.png")
    proof=json.loads((BASE/"corrected-proof/corrected-proof.json").read_text());items=[]
    order={"idle":0,"walk":1,"attack":2}
    rows=sorted(proof["records"],key=lambda r:(order[r["category"]],r["phase"],r["direction"]))
    for r in rows:
        items.append(label(Image.open(r["output"]).convert("RGBA"),f"{r['category']} p{r['phase']:.3g} D{r['direction']:02d}"))
    grid(items,4,BASE/"corrected-proof"/"corrected-four-direction-proof.png")
    close=[]
    for r in rows:
        if r["category"] in {"idle","attack"} and r["direction"] in {0,8}:
            close.append(label(crop_close(r["output"]),f"{r['category']} p{r['phase']:.3g} D{r['direction']:02d}"))
    grid(close,4,BASE/"corrected-proof"/"corrected-shield-helmet-weapon-closeups.png")

if __name__=="__main__":main()
