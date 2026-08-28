"""Discover and acquire exact cross-unit calibration VMD manifests from installed packs."""
from __future__ import annotations
import json,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rome2.acquire_variant_mesh_definitions import acquire  # noqa: E402
ROOT=Path(__file__).resolve().parents[2]; OUT=ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"
DATA=Path(r"C:\Program Files (x86)\Steam\steamapps\common\Total War Rome II\data")
HELPER=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe"
PACK_NAMES=["models3_rome2.pack","models_rome2.pack","models2_rome2.pack","models2.pack","models.pack","greeks.pack"]
SELECTED={
 "Hastati":"variantmeshes/variantmeshdefinitions/roman_hastati.variantmeshdefinition",
 "Principes":"variantmeshes/variantmeshdefinitions/roman_principes.variantmeshdefinition",
 "Triarii":"variantmeshes/variantmeshdefinitions/roman_triarii.variantmeshdefinition",
 "Velites":"variantmeshes/variantmeshdefinitions/roman_velites.variantmeshdefinition",
 "Hoplites":"variantmeshes/variantmeshdefinitions/gre_hoplites.variantmeshdefinition",
 "Celtic Warriors":"variantmeshes/variantmeshdefinitions/cel_warriors.variantmeshdefinition",
 "Eastern Spearmen":"variantmeshes/variantmeshdefinitions/eas_spear.variantmeshdefinition",
 "Praetorian":"variantmeshes/variantmeshdefinitions/3c_rom_roman_praetorian_guard.variantmeshdefinition",
}
QUERY_ALIASES={
 "Hastati":["hastat"], "Principes":["princip"], "Triarii":["triari"], "Velites":["velit"],
 "Hoplites":["hoplit"],
 # Rome II commonly encodes culture in a short prefix rather than spelling it out.
 "Celtic Warriors":["cel_warrior", "cel_tribal_warrior", "cel_naked_warrior", "celtic_warrior"],
 "Eastern Spearmen":["eas_spear", "eastern_spear"],
 "Praetorian":["praetorian"],
}
def listing(pack): return json.loads(subprocess.check_output([HELPER,"list","--pack",pack],text=True))["paths"]
def main():
    OUT.mkdir(parents=True,exist_ok=True); packs=[DATA/name for name in PACK_NAMES if (DATA/name).is_file()]
    indices={p.name:listing(p) for p in packs}; candidates={}
    for unit,aliases in QUERY_ALIASES.items():
        candidates[unit]=[{"path":path,"pack":pack} for pack,paths in indices.items() for path in paths
          if path.lower().endswith("variantmeshdefinition") and "/variantmeshdefinitions/" in path.lower()
          and any(alias in Path(path).name.lower() for alias in aliases)]
    units=[]
    for name,path in SELECTED.items():
        root=OUT/"units"/name.lower().replace(" ","-"); acquisition,dependencies=acquire(HELPER,packs,path,root)
        (root/"vmd-acquisition.json").write_text(json.dumps(acquisition,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        (root/"dependencies.json").write_text(json.dumps(dependencies,indent=2,sort_keys=True)+"\n",encoding="utf-8")
        selected=next(row for row in acquisition["definitions"] if row["normalized_path"]==acquisition["root_definition"].lower())
        units.append({"name":name,"selected_vmd":path,"source_pack":selected["pack"],"selection_strategy":dependencies["selection_strategy"],
                      "selected_dependencies":dependencies["dependencies"],"definition_dependencies":acquisition["definitions"],"output_root":str(root)})
    report={"format":"rome2aoe2.cross-unit-discovery","version":1,"pack_precedence":PACK_NAMES,"all_candidates":candidates,"units":units}
    (OUT/"unit-discovery.json").write_text(json.dumps(report,indent=2,sort_keys=True)+"\n",encoding="utf-8"); print(json.dumps(report,indent=2,sort_keys=True));return 0
if __name__=="__main__":raise SystemExit(main())
