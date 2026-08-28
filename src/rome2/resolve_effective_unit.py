"""Resolve Rome II unit identity and all evidence-backed runtime visual inputs.

This deliberately does not collapse stochastic VMD slots or decal arrays to their
first entry.  Unknown per-entity runtime choices remain explicit in the manifest.
"""
from __future__ import annotations
import json,subprocess,xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"build"/"local-integration"/"rome2"/"runtime-resolution"
HELPER=ROOT/"tools"/"rome2_pack"/"target"/"release"/"rome2aoe2-pack.exe"
SCHEMA=ROOT/"build"/"local-integration"/"rpfm-schemas"/"schema_rom2.ron"
DBROOT=OUT/"db"/"db"
UNITS={
 "hastati":{"main":"Rom_Hastati","faction":"rom_rome","vmd":"roman_hastati","root":ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"/"units"/"hastati"},
 "eastern-spearman":{"main":"Eas_Spear","faction":"rom_parthia","vmd":"eas_spear","root":ROOT/"build"/"local-integration"/"rome2"/"cross-unit-calibration"/"units"/"eastern-spearmen"},
 "praetorian":{"main":"Rom_Praetorian_Guard","faction":"rom_rome","vmd":"roman_praetorian_guard","root":OUT/"units"/"praetorian"},
}
TABLES=("main_units","land_units","unit_variants","unit_variants_colours","variants","faction_uniform_colours")
REPRESENTATIVE_POLICY={"name":"stable-first-valid","version":1,"description":"Choose the first structurally valid entry in source order. This deterministic AoE2 calibration choice is not claimed to reproduce Rome II's per-soldier random seed and can later be replaced by a seeded weighted selector."}

def db(table):
 p=DBROOT/f"{table}_tables"/table
 q=subprocess.run([HELPER,"decode-db","--input",p,"--schema",SCHEMA,"--table",f"{table}_tables"],capture_output=True,text=True,check=True)
 return json.loads(q.stdout)["rows"]

def one(rows,field,value):
 matches=[r for r in rows if r.get(field)==value]
 return matches[0] if len(matches)==1 else None

def definitions(root):
 result=[]
 for path in sorted(root.rglob("*.variantmeshdefinition")):
  tree=ET.parse(path)
  def walk(node,slot_path="root"):
   for slot_i,slot in enumerate(node.findall("SLOT")):
    name=slot.get("name") or f"slot-{slot_i}"; here=f"{slot_path}/{name}"
    entries=[]
    for i,child in enumerate(list(slot)):
     if child.tag=="VARIANT_MESH":
      remap={k:int(child.get(k)) for k in ("mask0","mask1","mask2") if child.get(k) is not None}
      entries.append({"index":i,"kind":"model","model":child.get("model"),"imposter":child.get("imposter_model"),"decal_diffuse":child.get("decal_diffuse"),"decal_normal":child.get("decal_normal"),"faction_channel_remap":remap or None})
      walk(child,f"{here}[{i}]")
     elif child.tag=="VARIANT_MESH_REFERENCE": entries.append({"index":i,"kind":"definition","definition":child.get("definition")})
    result.append({"definition":str(path.relative_to(root)).replace("\\","/"),"slot_path":here,"attach_point":slot.get("attach_point"),"probability":slot.get("probability"),"entry_count":len(entries),"selection":{"runtime_status":"deterministic" if len(entries)<=1 else "unresolved-runtime-random","representative_policy":REPRESENTATIVE_POLICY["name"],"representative_index":0 if entries else None,"provenance":"VMD source order; slot probability preserved"},"entries":entries})
  walk(tree.getroot())
 return result

def decal_arrays(root,slots):
 seen=[]
 for slot in slots:
  for entry in slot["entries"]:
   for field in ("decal_diffuse","decal_normal"):
    ref=entry.get(field)
    if not ref: continue
    target=root/Path(ref.replace("VariantMeshes/","variantmeshes/")+".texture_array")
    candidates=[p for p in root.rglob(Path(ref).name+".texture_array")]
    p=target if target.is_file() else (candidates[0] if candidates else None)
    values=[x.strip() for x in p.read_text().splitlines() if x.strip()] if p else []
    key=(field,ref)
    if key not in [(x["field"],x["reference"]) for x in seen]: seen.append({"field":field,"reference":ref,"resolved_path":str(p) if p else None,"entries":values,"selection":{"status":"unresolved-runtime-array-index","selected_index":None}})
 return seen

def main():
 tables={t:db(t) for t in TABLES}; manifests=[]
 for key,cfg in UNITS.items():
  main_row=one(tables["main_units"],"unit",cfg["main"]); land=one(tables["land_units"],"key",main_row["land_unit"]); uv=one(tables["unit_variants"],"unit",main_row["land_unit"])
  overrides=[r for r in tables["unit_variants_colours"] if r["unit_variant"]==uv["name"] and r.get("faction") in (cfg["faction"],"")]
  exact=next((r for r in overrides if r.get("faction")==cfg["faction"]),None); default=next((r for r in overrides if not r.get("faction")),None); uniform=one(tables["faction_uniform_colours"],"faction_name",cfg["faction"]); colour=exact or default or uniform
  colour_source="unit_variants_colours:faction" if exact else ("unit_variants_colours:default" if default else "faction_uniform_colours")
  slots=definitions(cfg["root"]); arrays=decal_arrays(cfg["root"],slots)
  manifest={"format":"rome2aoe2.effective-unit","version":1,"unit":key,"request":{"main_unit":cfg["main"],"faction":cfg["faction"]},"identity":{"main_units":main_row,"land_units":land,"unit_variants":uv,"variant_filename":f"variantmeshes/variantmeshdefinitions/{uv['variant'].lower()}.variantmeshdefinition"},"faction_colours":{"C0":colour["primary_colour_hex"],"C1":colour["secondary_colour_hex"],"C2":colour["tertiary_colour_hex"],"source":colour_source,"equation":"D0=lerp(D,D*C0,R); D1=lerp(D0,D0*C1,G); D2=lerp(D1,D1*C2,B)"},"vmd":{"root":str(cfg["root"]),"slots":slots,"mask_attribute_semantics":"maskN is a faction-colour channel remap for this VMD alternative, not a visibility boolean","stochastic_slots":sum(s["entry_count"]>1 for s in slots)},"decal_arrays":arrays,"attachments":[{"slot":s["slot_path"],"attach_point":s["attach_point"]} for s in slots if s["attach_point"]],"provenance":{"database_pack":"data_rome2.pack","schema":"rpfm-schemas/schema_rom2.ron","decisions":["main_units.unit -> land_units.key","unit_variants.unit -> variants.variant_name -> VMD filename","unit_variants_colours exact faction, then default, then faction_uniform_colours fallback"]},"unresolved":["per-soldier VMD slot random seed/choice" if any(s["entry_count"]>1 for s in slots) else None,"texture-array slice selection" if arrays else None]}
  manifest["unresolved"]=[x for x in manifest["unresolved"] if x]
  d=OUT/"effective"/key;d.mkdir(parents=True,exist_ok=True);(d/"effective-unit.json").write_text(json.dumps(manifest,indent=2)+"\n");manifests.append(manifest)
 (OUT/"effective-units.json").write_text(json.dumps({"format":"rome2aoe2.effective-units","version":1,"units":manifests},indent=2)+"\n")
 print(json.dumps([{"unit":m["unit"],"vmd":m["identity"]["variant_filename"],"colours":m["faction_colours"],"unresolved":m["unresolved"]} for m in manifests],indent=2))
if __name__=="__main__": main()
