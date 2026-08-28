"""Extract direct RMV2 texture dependencies for calibration Set A."""
from __future__ import annotations
import json, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
DATA=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data")
HELPER=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe"
PACKS=[DATA/n for n in ("models3_rome2.pack","models_rome2.pack","models2_rome2.pack","models2.pack","models.pack","greeks.pack") if (DATA/n).is_file()]
SET_A=("hastati","principes","triarii","velites","hoplites","celtic-warriors","eastern-spearmen","praetorian")

def call(*args):
    p=subprocess.run([HELPER,*map(str,args)],capture_output=True,text=True)
    if p.returncode: raise RuntimeError(p.stderr.strip())
    return p.stdout

def main():
    indices=[]
    for pack in PACKS:
        paths=json.loads(call("list","--pack",pack))["paths"]
        indices.append((pack,{p.lower():p for p in paths}))
    report={"format":"rome2aoe2.cross-unit-textures","version":1,"units":{}}
    for slug in SET_A:
        unit=BASE/"units"/slug; assets=json.loads((unit/"assets.json").read_text())
        materials={}; unresolved=[]
        for export in assets["exports"]:
            gltf=json.loads(Path(export["gltf"]).read_text())
            for material in gltf.get("materials",[]):
                extra=material.get("extras",{}).get("rome2aoe2",{})
                row=materials.setdefault(material["name"],{"material_name":material["name"],"material_type":extra.get("type"),"textures":[],"source_models":[]})
                row["source_models"].append(export["source_model"])
                for tex in extra.get("textures",[]):
                    key=tex["path"].replace("\\","/").lower(); found=None
                    for pack,index in indices:
                        if key in index: found=(pack,index[key]);break
                    item={"semantic":tex["type"],"source_path":tex["path"],"status":"missing"}
                    if found:
                        pack,path=found; call("extract","--pack",pack,"--path",path,"--output-root",unit/"textures")
                        item.update({"status":"resolved","pack":pack.name,"extracted_path":path})
                    else: unresolved.append({"material":material["name"],**item})
                    if not any(x["semantic"]==item["semantic"] and x["source_path"].lower()==item["source_path"].lower() for x in row["textures"]): row["textures"].append(item)
        doc={"format":"rome2aoe2.texture-manifest","version":1,"unit":slug,"materials":list(materials.values()),"unresolved":unresolved}
        (unit/"texture-manifest.json").write_text(json.dumps(doc,indent=2,sort_keys=True)+"\n")
        report["units"][slug]={"materials":len(materials),"textures":sum(len(x["textures"]) for x in materials.values()),"unresolved":len(unresolved)}
    (BASE/"texture-summary.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps(report,indent=2)); return 0
if __name__=="__main__": raise SystemExit(main())
