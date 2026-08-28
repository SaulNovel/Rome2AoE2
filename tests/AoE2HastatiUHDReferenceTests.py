from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/"src")]
from aoe2.sld import parse_sld,serialize_sld
BASE=ROOT/"build/local-integration/rome2/aoe-style-calibration";LOCAL=BASE/"ROME2AOE2_AOE_STYLE_HASTATI/resources/_common/drs/graphics";INST=Path(r"C:\Users\sauln\Games\Age of Empires 2 DE\0\mods\local\ROME2AOE2_AOE_STYLE_HASTATI\resources\_common\drs\graphics")
def main():
 r=json.loads((BASE/"aoe-reference-analysis-x2.json").read_text())
 assert r["comparison"]=="final decoded native x2 SLD layers" and r["spatial_filter_scale"]==2
 assert [r["stock"][x]["metrics_x2"]["bbox_height"] for x in ("militia","man-at-arms","legionary")]==[82,82,79]
 assert r["pipeline_verification"]["x2_upscaled_from_x1"] is False
 for name in ("reference-comparison-x2-native.png","reference-comparison-x2-logical-scale.png","hastati-artistic-sweep-uhd.png"):
  assert (BASE/name).is_file()
 for cid,c in r["custom"].items():
  assert c["metrics_x2"]["shadow_area_pixels"]>0 and c["metrics_x2"]["shadow_opacity_mean"]>0
  p=LOCAL/f"{c['stem']}_x2.sld";q=INST/p.name;raw=p.read_bytes();assert raw==q.read_bytes() and hashlib.sha256(raw).hexdigest()==c["installed_sha256_x2"]
  d=parse_sld(raw);assert len(d.frames)==16 and raw==serialize_sld(d) and (d.frames[0].canvas_width,d.frames[0].canvas_height)==(400,400)
 src=(ROOT/"src/aoe2/generate_hastati_style_proof.py").read_text();assert 'downsample_about_feet(hi,canvas,logical,hotspot)' in src and 'resize((400' not in src
 print("HASTATI UHD REFERENCE PASS")
if __name__=="__main__":main()
