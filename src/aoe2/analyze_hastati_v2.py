"""Finalize decoded x2 player-shade diagnostics for the Hastati V2 proof."""
from pathlib import Path
import json,statistics,sys
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/"src"))
from aoe2.analyze_aoe_style_uhd import decode
BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration-v2";G=BASE/"ROME2AOE2_AOE_STYLE_HASTATI_V2/resources/_common/drs/graphics"
def main():
 p=json.loads((BASE/"hastati-v2-report.json").read_text())
 for c in p["candidates"]:
  d=decode(G/f"{c['stem']}_x2.sld",0);v=[q for q,m,a in zip(d["pc"].getdata(),d["pc_presence"].getdata(),d["main"].getchannel("A").getdata()) if m and a>8]
  if v:
   v.sort();c["player_shade_metrics"]={"palette_index_min":min(v),"palette_index_p10":v[int(.1*(len(v)-1))],"palette_index_p50":statistics.median(v),"palette_index_p90":v[int(.9*(len(v)-1))],"palette_index_max":max(v),"distinct_indices":len(set(v)),"standard_deviation":round(statistics.pstdev(v),4),"strength":c["player_strength"],"support_coverage":c["metrics_x2"]["player_colour_coverage"]}
  else:c["player_shade_metrics"]=None
 (BASE/"hastati-v2-report.json").write_text(json.dumps(p,indent=2,sort_keys=True)+"\n");print("HASTATI V2 METRICS FINALIZED");return 0
if __name__=="__main__":raise SystemExit(main())
