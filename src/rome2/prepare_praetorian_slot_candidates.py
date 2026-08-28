"""Extract/export the deliberately small Praetorian armour/helmet/shield set."""
import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration";UNIT=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"/"units"/"praetorian";DATA=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data");PACK=DATA/"models3_rome2.pack";H=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe";SK=ROOT/"build"/"local-integration"/"rome2"/"animation-v5"/"animations"/"skeletons"/"rome_man_game.anim";INV=SK.with_suffix(".bone_inv_trans_mats")
SLOTS={"armour":["3c_roman_lorica_hamata_cape","lorica_segmentata_a"],"helmet":["3c_niederbieber_helmet","3c_niederbieber_helmet_gold","3c_italic_h_helmet"],"shield":["roman_augustan_scutuma","roman_augustan_scutumb","roman_augustan_scutumc"]}
DIR={"armour":"armour","helmet":"helmets","shield":"shield"}
def call(a,jsonout=True):
 p=subprocess.run([H,*map(str,a)],text=True,capture_output=True);assert p.returncode==0,p.stderr;return json.loads(p.stdout) if jsonout else p.stdout
def main():
 BASE.mkdir(parents=True,exist_ok=True);rows=[]
 for slot,names in SLOTS.items():
  for name in names:
   rel=f"variantmeshes/_variantmodels/man/{DIR[slot]}/{name}.rigid_model_v2";ex=call(["extract","--pack",PACK,"--path",rel,"--output-root",BASE/"extracted"]);out=BASE/"gltf"/slot/f"{name}.gltf";out.parent.mkdir(parents=True,exist_ok=True);args=["export-rmv2-gltf","--input",ex["output_path"],"--output",out,"--lod","highest"]
   if slot!="shield":args += ["--skeleton-anim",SK,"--inverse-bind",INV]
   meta=call(args);rows.append({"slot":slot,"name":name,"source_model":rel,"gltf":str(out),"metadata":meta})
 (BASE/"praetorian-slot-assets.json").write_text(json.dumps({"format":"rome2aoe2.praetorian-slot-assets","version":1,"assets":rows},indent=2,sort_keys=True)+"\n");print(json.dumps([{"slot":x['slot'],"name":x['name'],"meshes":x['metadata']['mesh_count']} for x in rows],indent=2))
if __name__=="__main__":main()
