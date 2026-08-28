import json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration";DATA=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data");H=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe";PACKS=[DATA/n for n in ("models3_rome2.pack","models_rome2.pack","models2_rome2.pack") if (DATA/n).is_file()]
def call(a):
 p=subprocess.run([H,*map(str,a)],capture_output=True,text=True);assert p.returncode==0,p.stderr;return json.loads(p.stdout)
def main():
 indices=[(p,{x.lower():x for x in call(["list","--pack",p])["paths"]}) for p in PACKS];assets=json.loads((BASE/"praetorian-slot-assets.json").read_text());materials={}
 for e in assets["assets"]:
  g=json.loads(Path(e["gltf"]).read_text())
  for m in g["materials"]:
   ex=m["extras"]["rome2aoe2"];row=materials.setdefault(m["name"],{"material_name":m["name"],"material_type":ex["type"],"textures":[]})
   for t in ex["textures"]:
    hit=next(((p,i[t["path"].lower()]) for p,i in indices if t["path"].lower() in i),None);item={"semantic":t["type"],"source_path":t["path"],"status":"missing"}
    if hit:
     p,path=hit;call(["extract","--pack",p,"--path",path,"--output-root",BASE/"textures"]);item.update({"status":"resolved","extracted_path":path,"pack":p.name})
    if not any(x["semantic"]==item["semantic"] and x["source_path"].lower()==item["source_path"].lower() for x in row["textures"]):row["textures"].append(item)
 text=json.dumps({"format":"rome2aoe2.slot-textures","version":1,"materials":list(materials.values())},indent=2,sort_keys=True)+"\n";(BASE/"praetorian-slot-textures.json").write_text(text);(BASE/"texture-manifest.json").write_text(text)
if __name__=="__main__":main()
