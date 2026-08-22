"""Run a resumable direction batch for one frozen production category."""
import argparse,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from rome2aoe2.conversion import DEFAULT_BLENDER,load_and_validate_manifest,manifest_digest
from rome2aoe2.native_assembly import assemble_native,static_visual_manifest
from rome2aoe2.production import category_output,frozen_candidate
def main():
 p=argparse.ArgumentParser();p.add_argument("manifest",type=Path);p.add_argument("category");p.add_argument("directions");a=p.parse_args();r=load_and_validate_manifest(a.manifest);row=r.manifest["animations"][a.category];candidate=frozen_candidate(a.category,row);blend,assembly=assemble_native(r.manifest,candidate);out=category_output(r.unit.definition.main_unit,r.manifest_hash,a.category,row);static=ROOT/"build/conversions"/r.unit.definition.main_unit.casefold()/manifest_digest(static_visual_manifest(r.manifest))/"static-assembly-input.json";report=out/f"render-report-directions-{a.directions.replace(',','-')}.json";cmd=[str(DEFAULT_BLENDER),"--background","--python",str(ROOT/"src/blender/render_manifest_native_production.py"),"--","--input-blend",str(blend),"--static-input",str(static),"--output-root",str(out),"--report",str(report),"--category",a.category,"--manifest-hash",r.manifest_hash,"--animation-asset",row["resolved_asset"],"--source-samples",str(row["frame_count"]),"--source-fps",str(row["fps"]),"--action-fingerprint",assembly["action_fingerprint_before"],"--directions",a.directions];raise SystemExit(subprocess.run(cmd).returncode)
if __name__=="__main__":main()
