"""Export the DB-resolved base-game Praetorian VMD representative assets."""
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rome2.extract_dependency_manifest import extract
ROOT=Path(__file__).resolve().parents[2];U=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"/"units"/"praetorian"
DATA=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data");H=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe"
PACKS=[DATA/x for x in ("models3_rome2.pack","models_rome2.pack","models2_rome2.pack","models2.pack","models.pack")]
SK=ROOT/"build"/"local-integration"/"rome2"/"animation-v5"/"animations"/"skeletons"/"rome_man_game.anim";INV=SK.with_suffix(".bone_inv_trans_mats")
def call(*a):
 p=subprocess.run([H,*map(str,a)],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stderr)
 return json.loads(p.stdout)
def main():
 ex=extract(U/"dependencies.json",PACKS,H,U/"extracted");exports=[]
 for a in ex["assets"]:
  if a["asset_types"]!=["model"]:continue
  rel=Path(a["normalized_path"].replace("variantmeshes/_variantmodels/man/","")).with_suffix(".gltf");out=U/"gltf"/rel;out.parent.mkdir(parents=True,exist_ok=True)
  args=("export-rmv2-gltf","--input",a["output_path"],"--output",out,"--lod","highest")
  try:meta=call(*args,"--skeleton-anim",SK,"--inverse-bind",INV);skinned=True
  except RuntimeError:meta=call(*args);skinned=False
  exports.append({"source_model":a["normalized_path"],"origins":a["origins"],"gltf":str(out),"skinned":skinned,"metadata":meta})
 assets={"format":"rome2aoe2.effective-unit-assets","version":1,"unit":"praetorian","extraction":ex,"exports":exports,"failures":[]};(U/"assets.json").write_text(json.dumps(assets,indent=2)+"\n")
 indices=[]
 for pack in PACKS:indices.append((pack,{p.lower():p for p in call("list","--pack",pack)["paths"]}))
 mats={};missing=[]
 for e in exports:
  gltf=json.loads(Path(e["gltf"]).read_text())
  for m in gltf.get("materials",[]):
   x=m.get("extras",{}).get("rome2aoe2",{});row=mats.setdefault(m["name"],{"material_name":m["name"],"material_type":x.get("type"),"source_models":[],"textures":[]});row["source_models"].append(e["source_model"])
   for t in x.get("textures",[]):
    found=next(((p,i[t["path"].lower()]) for p,i in indices if t["path"].lower() in i),None);item={"semantic":t["type"],"source_path":t["path"],"status":"missing"}
    if found:
     p,path=found;call("extract","--pack",p,"--path",path,"--output-root",U/"textures");item.update({"status":"resolved","pack":p.name,"extracted_path":path})
    else:missing.append({"material":m["name"],**item})
    if not any(q["semantic"]==item["semantic"] and q["source_path"].lower()==item["source_path"].lower() for q in row["textures"]):row["textures"].append(item)
 doc={"format":"rome2aoe2.texture-manifest","version":1,"unit":"praetorian","materials":list(mats.values()),"unresolved":missing};(U/"texture-manifest.json").write_text(json.dumps(doc,indent=2)+"\n");print(json.dumps({"models":len(exports),"materials":len(mats),"unresolved":len(missing)}))
if __name__=="__main__":main()
