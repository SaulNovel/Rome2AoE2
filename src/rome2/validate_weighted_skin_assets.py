"""Record structural validation of the two real Rome II WeightedSkin assets."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
TARGETS=[("Hoplite","hoplites","greek_full_base_skingre10_shape10"),("Eastern Spearman","eastern-spearmen","eastern_headhands_base_skineas1_shape16")]
def main():
 rows=[]
 for name,slug,needle in TARGETS:
  assets=json.loads((BASE/"units"/slug/"assets.json").read_text());e=next(x for x in assets["exports"] if needle in x["source_model"]);g=json.loads(Path(e["gltf"]).read_text())
  primitives=[p for m in g["meshes"] for p in m["primitives"]];attrs=[p["attributes"] for p in primitives]
  pos=[g["accessors"][a["POSITION"]] for a in attrs]
  rows.append({"unit":name,"source_model":e["source_model"],"skinned":e["skinned"],"skeleton_id":e["metadata"]["skeleton_id"],"mesh_count":e["metadata"]["mesh_count"],"vertex_count":e["metadata"]["vertex_count"],"triangle_count":e["metadata"]["triangle_count"],"material_types":e["metadata"]["material_types"],"all_primitives_have_uv0":all("TEXCOORD_0" in a for a in attrs),"all_primitives_have_joints_weights":all("JOINTS_0" in a and "WEIGHTS_0" in a for a in attrs),"bounds_min":[min(a["min"][i] for a in pos) for i in range(3)],"bounds_max":[max(a["max"][i] for a in pos) for i in range(3)]})
 out={"format":"rome2aoe2.weighted-skin-real-assets","version":1,"reference":"The Asset Editor WeightedMaterial.cs: WeightedSkin uses WeightedMaterialStruct shared by weighted material families","implementation":"in-memory project-side material dispatch overlay 70 -> 82; original metadata remains WeightedSkin/70","assets":rows}
 (BASE/"material-type-70-validation.json").write_text(json.dumps(out,indent=2,sort_keys=True)+"\n");print(json.dumps(out,indent=2))
if __name__=="__main__":main()
