import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"build/python-deps/sld-authoring"),str(ROOT/"src")]
from aoe2.sld import parse_sld
BASE=ROOT/"build/local-integration/rome2/hastati-rome2-daylight-bronze"
def main():
 p=json.loads((BASE/"hastati-rome2-daylight-bronze-report.json").read_text());assert len(p["measurements"])==7 and len(p["finalists"])==5
 assert p["facings"]["bronze_exposure"]["facet"]==3 and p["facings"]["current"]["facet"]==0
 required={"L10","L50","L90","L95","hue","chroma","saturation","local_contrast","highlight_coverage","near_white_coverage","clipped_coverage"}
 for x in p["measurements"].values():
  assert x["bronze"]["master_before_reduction"] is not None
  for stage in ("master_before_reduction","x2_pre_sld","decoded_x2"):assert required<=set(x["bronze"][stage])
 for x in p["finalists"]:
  for z in ("x1","x2"):
   q=BASE/"ROME2AOE2_HASTATI_ROME2_DAYLIGHT_BRONZE/resources/_common/drs/graphics"/f"{x['stem']}_{z}.sld";s=parse_sld(q.read_bytes());assert len(s.frames)==16
 for n in ("facing-sheet.png","high-res-bronze-study.png","decoded-x2-comparison.png","Rome2HastatiRome2DaylightBronze.aoe2scenario"):assert (BASE/n).is_file()
if __name__=="__main__":main()
