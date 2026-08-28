"""Extract and export selected cross-unit RMV2 dependencies with provenance."""
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rome2.extract_dependency_manifest import extract  # noqa: E402
ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
DATA=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data"); HELPER=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe"
PACKS=[DATA/n for n in ("models3_rome2.pack","models_rome2.pack","models2_rome2.pack","models2.pack","models.pack","greeks.pack") if (DATA/n).is_file()]
SKEL=ROOT/"build"/"local-integration"/"rome2"/"animation-v5"/"animations"/"skeletons"/"rome_man_game.anim"
INV=SKEL.with_suffix(".bone_inv_trans_mats")
def helper(args):
    p=subprocess.run([HELPER,*map(str,args)],text=True,capture_output=True)
    if p.returncode: raise RuntimeError(p.stderr.strip())
    return json.loads(p.stdout)
def main():
    discovery=json.loads((BASE/"unit-discovery.json").read_text(encoding="utf-8")); summary=[]
    for unit in discovery["units"]:
        root=Path(unit["output_root"]); extraction=extract(root/"dependencies.json",PACKS,HELPER,root/"extracted")
        (root/"asset-extraction.json").write_text(json.dumps(extraction,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        exports=[]; failures=[]
        for asset in extraction["assets"]:
            if asset["asset_types"]!=["model"]: continue
            rel=Path(asset["normalized_path"].replace("variantmeshes/_variantmodels/man/","")).with_suffix(".gltf"); out=root/"gltf"/rel;out.parent.mkdir(parents=True,exist_ok=True)
            args=["export-rmv2-gltf","--input",asset["output_path"],"--output",out,"--lod","highest"]
            skinned=True
            try: result=helper([*args,"--skeleton-anim",SKEL,"--inverse-bind",INV])
            except RuntimeError as skinned_error:
                try: result=helper(args);skinned=False
                except RuntimeError as static_error:
                    failures.append({"source_model":asset["normalized_path"],"origins":asset["origins"],"skinned_error":str(skinned_error),"static_error":str(static_error)});continue
            exports.append({"source_model":asset["normalized_path"],"origins":asset["origins"],"gltf":str(out),"skinned":skinned,"metadata":result})
        report={"format":"rome2aoe2.cross-unit-assets","version":1,"unit":unit["name"],"extraction":extraction,"exports":exports,"failures":failures}
        (root/"assets.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8");summary.append({"unit":unit["name"],"models":len(exports),"skinned":sum(x["skinned"] for x in exports),"static":sum(not x["skinned"] for x in exports),"failed":len(failures)})
    (BASE/"asset-summary.json").write_text(json.dumps(summary,indent=2,sort_keys=True)+"\n",encoding="utf-8");print(json.dumps(summary,indent=2));return 0
if __name__=="__main__":raise SystemExit(main())
