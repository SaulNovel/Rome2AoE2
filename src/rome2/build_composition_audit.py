"""Summarize effective composition and texture resolution for the bounded proof."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CAL=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
OUT=ROOT/"build"/"local-integration"/"rome2"/"composition-calibration"

def slug(name): return name.lower().replace(" ","-")

def main():
 discovery=json.loads((CAL/"unit-discovery.json").read_text())
 wanted={u["name"]:u for u in discovery["units"] if u["name"] in {"Hastati","Eastern Spearmen","Praetorian"}}
 report={"format":"rome2aoe2.composition-audit","version":1,"units":{}}
 lines=["# Composition calibration audit",""]
 for name in ("Hastati","Eastern Spearmen","Praetorian"):
  u=wanted[name]; key=slug(name); tm=json.loads((CAL/"units"/key/"texture-manifest.json").read_text())
  deps=[]
  for d in u["selected_dependencies"]:
   if "model" in d.get("asset_types",[]): deps.append({"model":d["path"],"origins":d.get("origins",[])})
  materials=[];unresolved=[]
  for m in tm["materials"]:
   tex=[]
   for t in m["textures"]:
    q={k:t.get(k) for k in ("semantic","source_path","status","pack","extracted_path") if t.get(k) is not None};tex.append(q)
    if t.get("status")!="resolved":unresolved.append(q)
   materials.append({"name":m["material_name"],"type":m["material_type"],"models":m["source_models"],"textures":tex})
  note={
   "Hastati":"Structurally complete reference. Blank decal arrays and test_mask/test_black entries are engine defaults; H02 maps only source faction R to runtime AoE player colour.",
   "Eastern Spearmen":"Authored diffuse/normal/specular/gloss/mask textures resolve. G mask dominates the tunic/clothing, R affects cap and smaller regions, B affects limited lower regions. The neutral pale result is tint-ready source data, not missing DDS. First root-reference choice is not proven to match every runtime faction composition.",
   "Praetorian":"Repeated trouser/tunic/cloak/shield references carry mask0/mask1/mask2 runtime conditions. Generic first-reference traversal cannot reproduce those visibility rules; full-leg pants remain unresolved and were not manually deleted. P01-P03 vary only plausible armour/helmet/shield slots."
  }[name]
  report["units"][name]={"selected_vmd":u["selected_vmd"],"source_pack":u["source_pack"],"selection_strategy":u["selection_strategy"],"models":deps,"materials":materials,"unresolved":unresolved,"finding":note}
  lines += [f"## {name}","",f"- VMD: `{u['selected_vmd']}` ({u['source_pack']})",f"- Selection: {u['selection_strategy']}",f"- Effective models: {len(deps)}; materials: {len(materials)}; unresolved texture references: {len(unresolved)}",f"- Finding: {note}","","Models:",""]
  lines += [f"- `{d['model']}`" for d in deps]
  lines += ["","Materials:",""]+[f"- `{m['name']}` / {m['type']}: "+", ".join(f"{t['semantic']}={t['status']}" for t in m['textures']) for m in materials]+[""]
 report["praetorian_candidates"]=json.loads((OUT/"composition-candidates.json").read_text())["praetorian"]
 (OUT/"composition-audit.json").write_text(json.dumps(report,indent=2)+"\n")
 (OUT/"REPORT.md").write_text("\n".join(lines)+"\n")
 print(OUT/"REPORT.md")
if __name__=="__main__": main()
