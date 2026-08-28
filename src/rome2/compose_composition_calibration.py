from pathlib import Path
import sys,json
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"build"/"python-deps"/"pillow"));from PIL import Image,ImageDraw,ImageFont
B=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration";R=B/"renders";F=ImageFont.load_default()
def make(ids,title,name,cols):
 cell=(340,330);rows=(len(ids)+cols-1)//cols;o=Image.new("RGBA",(cols*cell[0],28+rows*cell[1]),(24,27,30,255));d=ImageDraw.Draw(o);d.text((8,8),title,font=F,fill="white")
 for i,(k,label) in enumerate(ids):
  im=Image.open(R/f"{k}.png").convert("RGBA");b=im.getchannel("A").getbbox();im=im.crop(b);im.thumbnail((260,270),Image.Resampling.LANCZOS);x=(i%cols)*cell[0];y=28+(i//cols)*cell[1];o.alpha_composite(im,(x+(cell[0]-im.width)//2,y+35));d.text((x+6,y+7),f"{k} — {label}",font=F,fill="white")
 o.convert("RGB").save(B/name)
def main():
 make([("H01","neutral source reconstruction"),("H02","R-channel test tint"),("H03","independent RGB test tint")],"Hastati fixed-L11 candidates","hastati-final-candidates.png",3)
 make([("E01","neutral"),("E02","R only"),("E03","G only"),("E04","B only"),("E05","independent RGB")],"Eastern Spearmen channel diagnostics","eastern-spearmen-diagnostics.png",3)
 make([("P01","hamata / Niederbieber / scutum A"),("P02","segmentata / gold Niederbieber / scutum B"),("P03","hamata / Italic H / scutum C")],"Praetorian controlled slot candidates","praetorian-slot-variants.png",3)
if __name__=="__main__":main()
