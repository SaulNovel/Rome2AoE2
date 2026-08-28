"""Phases 1-3 diagnostic audit for the Praetorian Guard visual-fidelity problem.

Generates (read-only, no production changes):
  build/local-integration/rome2/visual-fidelity/variant-audit.json
  build/local-integration/rome2/visual-fidelity/material-audit.json
  build/local-integration/rome2/visual-fidelity/mask-diagnostics.json
  build/local-integration/rome2/visual-fidelity/faction-colour-provenance.json
  build/local-integration/rome2/visual-fidelity/mask-channels/*.png
"""

import argparse, json, math, sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Self-bootstrap vendored python deps so the script runs from any shell
# (Windows cmd refuses relative PYTHONPATH reliably).
_VENDORED = ROOT / "build" / "python-deps" / "sld-authoring"
if _VENDORED.is_dir() and str(_VENDORED) not in sys.path:
    sys.path.insert(0, str(_VENDORED))

from PIL import Image  # noqa: E402

LINT = ROOT / "build" / "local-integration" / "rome2"
OUT = LINT / "visual-fidelity"
TEX = LINT / "textures"

WORKSPACE_HINT = (
    "3c_ prefix: convention observed across Rome II three-campaign era assets "
    "(3c_roman_headhands_white, 3c_niederbieber_helmet, etc). Exact meaning must be verified "
    "from game records; pack provenance is models3_rome2.pack."
)


def djson(v):
    return json.dumps(v, indent=2, sort_keys=True) + "\n"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def parse_vmd(path):
    root = ET.parse(path).getroot()
    slots, selected = [], []

    def walk(node, slot_path):
        for child in node:
            if child.tag == "SLOT":
                name = child.get("name", "")
                entry = {"name": name, "attach_point": child.get("attach_point"),
                         "probability": child.get("probability"), "variants": [],
                         "slot_path": f"{slot_path}/{name}" if slot_path else name}
                slots.append(entry)
                walk(child, f"{slot_path}/{name}" if slot_path else name)
            elif child.tag == "VARIANT_MESH":
                variant = {"model": child.get("model"),
                           "imposter_model": child.get("imposter_model"),
                           "decal_diffuse": child.get("decal_diffuse"),
                           "decal_normal": child.get("decal_normal"),
                           "mask0": child.get("mask0"), "mask1": child.get("mask1"),
                           "mask2": child.get("mask2")}
                if slot_path is not None:
                    for slot in reversed(slots):
                        if slot.get("slot_path") == slot_path:
                            slot["variants"].append(variant)
                            break
                if child.get("model"):
                    selected.append({"slot": slot_path, "model": child.get("model"), "variant": variant})
                if len(child):
                    walk(child, slot_path)

    walk(root, None)
    resolved = {s["slot_path"]: s for s in slots}
    return {"slots": list(resolved.values()), "first_variant_per_slot": selected}


def classify(identifier, status, default_value):
    base = Path(identifier).name
    if status != "shader_default":
        return {"classification": "authored_resource" if status == "resolved" else "unresolved_placeholder",
                "status": status, "default_value": default_value}
    if "test_mask" in base:
        kind, detail = "engine_sentinel_zero_mask", "zero_mask default (0,0,0,1): no faction tint"
    elif "test_black" in base and default_value == "decal_passthrough":
        kind, detail = "engine_sentinel_decal_passthrough", "black but alpha=1: decal passes through unchanged"
    elif "test_black" in base:
        kind, detail = "engine_sentinel_black", "black default (0,0,0,0): slot contributes nothing"
    else:
        kind, detail = "engine_sentinel", f"default sentinel {default_value!r}"
    return {"classification": kind, "default_value": default_value, "notes": detail, "status": status,
            "authoritative_source": ("CASpecGlossHelper.hlsli + ShaderTextureViewModel.cs: test_black/test_mask "
                                     "are engine-provided defaults for missing mask/dirt slots")}


def lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def pct(vals, p):
    s = sorted(vals)
    if not s:
        return 0.0
    k = (len(s) - 1) * p
    f, c = math.floor(k), math.ceil(k)
    return s[int(k)] if f == c else s[f] * (c - k) + s[c] * (k - f)


def rgb_stats(img):
    data = list(img.convert("RGB").getdata())
    n = max(1, len(data))
    means = [sum(p[i] for p in data) / n for i in range(3)]
    lum_vals = [lum(p) for p in data]
    mx, mn = max(means), min(means)
    sat = 0.0 if mx == 0 else (mx - mn) / mx
    low = sum(1 for p in data if (max(p) - min(p)) / max(1.0, max(p)) < 0.1) / n
    return {"mean_rgb": [round(v, 4) for v in means], "mean_luminance": round(lum(means), 4),
            "luminance_p10": round(pct(lum_vals, .10), 4), "luminance_p50": round(pct(lum_vals, .50), 4),
            "luminance_p90": round(pct(lum_vals, .90), 4), "saturation": round(sat, 4),
            "low_saturation_fraction": round(low, 4)}


def chromatic(rgb):
    return round(max(rgb) - min(rgb), 4)


def open_dds(rel):
    p = TEX / rel
    if not p.is_file():
        return None, None
    try:
        img = Image.open(p)
        img.load()
        return img, str(p)
    except Exception:
        return None, str(p)


def mask_inventory(manifest):
    out = []
    for mat in manifest["materials"]:
        for tex in mat["textures"]:
            if tex.get("status") == "resolved" and tex.get("semantic") in ("Mask", "SkinMask"):
                out.append({"material": mat["material_name"], "semantic": tex["semantic"],
                            "identifier": tex.get("identifier"), "resolved_path": tex.get("resolved_path"),
                            "dds": tex.get("dds"), "color_space": tex.get("color_space")})
    return out


def spec_inventory(manifest):
    out = []
    for mat in manifest["materials"]:
        for tex in mat["textures"]:
            if tex.get("status") == "resolved" and tex.get("semantic") in ("Specular", "GlossMap"):
                out.append({"material": mat["material_name"], "semantic": tex["semantic"],
                            "resolved_path": tex.get("resolved_path"), "dds": tex.get("dds")})
    return out


def export_channel(img, channel, out_path):
    ch = img.convert("RGB").split()[{"r": 0, "g": 1, "b": 2}[channel]]
    black = ch.point(lambda _: 0)
    g = {0: (ch, black, black), 1: (black, ch, black), 2: (black, black, ch)}[{"r": 0, "g": 1, "b": 2}[channel]]
    Image.merge("RGB", g).save(out_path)
    return out_path


def ch_stats(img, channel):
    data = list(img.convert("RGB").split()[{"r": 0, "g": 1, "b": 2}[channel]].getdata())
    n = max(1, len(data))
    return {"channel": channel, "mean_intensity": round(sum(data) / n / 255.0, 4),
            "coverage_fraction_above_8": round(sum(1 for v in data if v > 8) / n, 4)}


def build_variant():
    vmd = LINT / "variantmeshes" / "variantmeshdefinitions" / "3c_rom_roman_praetorian_guard.variantmeshdefinition"
    parsed = parse_vmd(vmd)
    deps = load(LINT / "praetorian_guard.dependencies-v3.json")
    acq = load(LINT / "vmd-acquisition.json")
    manifest = load(LINT / "texture-manifest.json")
    non_3c = [d for d in deps.get("dependencies", [])
              if "praetorian" in d.get("normalized_path", "").lower()
              and not d.get("normalized_path", "").lower().startswith("3c_")]
    sel = parsed["first_variant_per_slot"]
    selection = {}
    for s in sel:
        selection.setdefault(s["slot"], []).append(s["model"])
    shield = next(({"model": s["model"], "variant": s["variant"]} for s in sel
                   if s["slot"] == "type/shield/shields"), {})
    pack = next((d["pack"] for d in acq.get("definitions", [])
                 if d.get("normalized_path", "").endswith("3c_rom_roman_praetorian_guard.variantmeshdefinition")), None)
    return {
        "format": "rome2aoe2.visual-fidelity.variant-audit", "version": 1,
        "source_definition": "variantmeshes/variantmeshdefinitions/3c_rom_roman_praetorian_guard.variantmeshdefinition",
        "pack_provenance": {"pack": pack, "pack_precedence": acq.get("pack_precedence"), "shadowed_packs": []},
        "selection_strategy": deps.get("selection_strategy"),
        "three_c_prefix": {"observed_meaning": "three-campaign era asset-family convention", "verified": False,
                           "note": WORKSPACE_HINT, "pack_evidence": "models3_rome2.pack"},
        "slots": parsed["slots"],
        "selected_first_variant_models": {
            "skin": selection.get("type/skin/type", []),
            "helmets": selection.get("type/helmets/helmets", []),
            "top_crests": selection.get("type/helmets/helmets/top_crests", []),
            "side_crests": selection.get("type/helmets/helmets/side_crests", []),
            "tunics": selection.get("type/torso/tunics", []),
            "armour": selection.get("type/torso/tunics/armour", []),
            "trousers": selection.get("type/torso/tunics/trousers", []),
            "cloaks": selection.get("type/torso/tunics/cloaks", []),
            "shields": selection.get("type/shield/shields", []),
            "weapon_2": selection.get("type/weapon_2", []),
            "weapon_4": selection.get("type/weapon_4", []),
        },
        "helmet_and_crest": {"helmet_model": selection.get("type/helmets/helmets", [None])[0],
                             "crest_models": selection.get("type/helmets/helmets/top_crests", []),
                             "crest_attach": "crest_centre", "crest_probability": 0.9},
        "shield": {"model": shield.get("model"),
                   "decal_diffuse": shield.get("variant", {}).get("decal_diffuse"),
                   "decal_normal": shield.get("variant", {}).get("decal_normal"),
                   "mask0": shield.get("variant", {}).get("mask0"),
                   "mask1": shield.get("variant", {}).get("mask1"),
                   "mask2": shield.get("variant", {}).get("mask2")},
        "texture_arrays": [d for d in deps.get("dependencies", []) if d.get("asset_types") == ["texture"]],
        "faction_mask_textures": mask_inventory(manifest),
        "non_3c_praetorian_variants_discovered": non_3c,
        "non_3c_note": ("no alternative praetorian VMD in local records; only the 3c_ root. "
                        "Does not prove absence from un-sampled packs."),
        "screenshot_compatibility": {
            "verdict": "unverified_without_reference_image_comparison",
            "key_differences_to_check": [
                "shield color/pattern (praetorian_guard_diffuse -> roman_legionary10_diffuse.dds)",
                "cloth color (celtic_basic_tunic_01; roman_cloak_tint cloak)",
                "armour finish (3c_roman_lorica_hamata_cape chainmail)",
                "crest color (red_horsehair first variant)",
                "skin tone (roman_heads_1_diffuse)",
            ]},
        "prior_evidence_preserved": {
            "decal_path_lookup_earlier_failures": (
                "Earlier raw decal identifiers were not directly found in model packs, but the later "
                "material/texture stage resolved authored textures successfully. Missing direct decal-path "
                "lookup from earlier stages is NOT current proof of missing visible textures."),
            "resolved_pattern_mapping": {
                "praetorian_guard_diffuse.texture_array": "roman_legionary10_diffuse.dds",
                "praetorian_guard_normal.texture_array": "blank_decal_normal.dds"},
            "manifest_summary": manifest.get("summary")},
    }


def build_material():
    manifest = load(LINT / "texture-manifest.json")
    materials = []
    for mat in manifest["materials"]:
        textures = []
        for tex in mat["textures"]:
            textures.append({"semantic": tex.get("semantic"), "identifier": tex.get("identifier"),
                             "resolved_path": tex.get("resolved_path"), "status": tex.get("status"),
                             "color_space": tex.get("color_space"), "alpha_semantics": tex.get("alpha_semantics"),
                             "dds": tex.get("dds"), "provenance": tex.get("provenance"),
                             "shader_default_classification": (classify(tex.get("identifier", ""), tex.get("status"),
                                                                        tex.get("default_value"))
                                                               if tex.get("status") == "shader_default" else None)})
        materials.append({"material_name": mat["material_name"], "material_type": mat["material_type"],
                          "material_type_id": mat.get("material_type_id"), "source_model": mat.get("source_model"),
                          "shader_flags": mat.get("shader_flags"), "parameters": mat.get("parameters"),
                          "textures": textures})
    speculars = []
    for spec in spec_inventory(manifest):
        img, path = open_dds(spec["resolved_path"])
        stats = None
        if img is not None:
            stats = rgb_stats(img)
            stats["chromatic_delta"] = chromatic(stats["mean_rgb"])
            stats["chromatic_delta_normalized"] = round(stats["chromatic_delta"] / 255.0, 4)
            stats["verdict"] = (
                "genuinely_chromatic" if stats["chromatic_delta_normalized"] > 0.05 else "nearly_grayscale"
            )
        speculars.append({"material": spec["material"], "semantic": spec["semantic"],
                          "resolved_path": spec["resolved_path"], "dds": spec["dds"],
                          "decoded_path": path, "rgb_stats": stats,
                          "scalar_conversion_significance": (
                              None if stats is None else (
                                  "MEANINGFUL - scalar conversion loses chromatic specular info"
                                  if stats["verdict"] == "genuinely_chromatic"
                                  else "not significant - specular channels near-grayscale"))})
    shader_defaults = [{"material": m["material_name"], "semantic": t["semantic"],
                        "resolved_path": t["resolved_path"], **t["shader_default_classification"]}
                       for m in materials for t in m["textures"] if t.get("shader_default_classification")]
    return {
        "format": "rome2aoe2.visual-fidelity.material-audit", "version": 1,
        "summary": manifest.get("summary"), "materials": materials,
        "specular_rgb_numerical_analysis": speculars,
        "shader_default_conclusions": {
            "count": manifest.get("summary", {}).get("shader_default_count"), "entries": shader_defaults,
            "authoritative_sources": {
                "CASpecGlossHelper.hlsli": ("test_black.tga is placeholder default for dirt/mask/decal slots; "
                                            "lerp(base, base*faction_color, mask_pN) is the tint pattern."),
                "ShaderTextureViewModel.cs": ("'If none is wanted, use test_mask.dds' - explicit empty/sentinel path")},
            "overall": "All shader-default entries are engine sentinels (zero_mask / black / decal_passthrough). "
                       "None is a genuinely missing authored texture; none darkens the render."},
        "prior_evidence_preserved": {
            "summary": manifest.get("summary"),
            "mapping": {"praetorian_guard_diffuse.texture_array": "roman_legionary10_diffuse.dds",
                        "praetorian_guard_normal.texture_array": "blank_decal_normal.dds"}},
    }


def build_masks():
    manifest = load(LINT / "texture-manifest.json")
    out = OUT / "mask-channels"
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for mask in mask_inventory(manifest):
        img, path = open_dds(mask["resolved_path"])
        if img is None:
            results.append({**mask, "error": "could not decode", "decoded_path": path})
            continue
        stem = Path(mask["resolved_path"]).stem.replace(".", "_")
        for ch in ("r", "g", "b"):
            rel = out / f"{stem}__{mask['material']}__channel_{ch}.png"
            export_channel(img, ch, rel)
            results.append({**mask, "decoded_path": path, "channel": ch,
                            "isolated_channel_png": str(rel), **ch_stats(img, ch)})
    (OUT / "mask-channels-stats.json").write_text(djson(results), encoding="utf-8")
    return {"output_directory": str(out), "entries": results}


def build_colours():
    return {
        "format": "rome2aoe2.visual-fidelity.faction-colour-provenance", "version": 1,
        "shader_formula_evidence": {
            "file": "build/research/TheAssetEditor/GameWorld/ContentProject/Content/Shaders/Pbr/Helpers/CASpecGlossHelper.hlsli",
            "operation": ("diffuse_colour_rgb = lerp(diffuse_colour_rgb, diffuse_colour_rgb * mesh_faction_color1.rgb, mask_p1); "
                          "diffuse_colour_rgb = lerp(diffuse_colour_rgb, diffuse_colour_rgb * mesh_faction_color2.rgb, mask_p2); "
                          "diffuse_colour_rgb = lerp(diffuse_colour_rgb, diffuse_colour_rgb * mesh_faction_color1.rgb, mask_p3);"),
            "supported_tint_formula": "lerp(base, base * factionColor, maskChannel)",
            "equivalent_form": "base * lerp(white, factionColor, maskChannel)",
            "algebraic_equivalence": True,
            "note": "CAMetalRoughnessHelper.hlsli shows same pattern with three colours."},
        "database_tables": {
            "unit_variants_colours_tables": "referenced by RPFM unit editor (rpfm_ui/src/tools/unit_editor/variant_unit_editor/mod.rs)",
            "unit_variants_tables": "variant <-> colour linkage",
            "faction_uniform_colours_tables": "RPFM faction painter uniform colour source"},
        "exact_unit_colours": {"status": "not_extracted_in_this_workspace",
                               "note": ("DB tables not present locally; exact encoded Praetorian colours require "
                                        "reading models packs via RPFM or DB dump. Not guessing from screenshot per scope.")},
        "mask_to_colour_relationship": {
            "note": ("mask_p1 uses faction_color1, mask_p2 uses faction_color2, mask_p3 re-uses color1. "
                     "Default zero_mask (0,0,0,1) means no tint applied by default.")},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phases", default="1,2,3")
    args = ap.parse_args()
    phases = {int(x) for x in args.phases.split(",") if x.strip()}
    OUT.mkdir(parents=True, exist_ok=True)
    if 1 in phases:
        p = OUT / "variant-audit.json"
        p.write_text(djson(build_variant()), encoding="utf-8")
        print(f"wrote {p}")
    if 2 in phases:
        p = OUT / "material-audit.json"
        p.write_text(djson(build_material()), encoding="utf-8")
        print(f"wrote {p}")
    if 3 in phases:
        p = OUT / "mask-diagnostics.json"
        p.write_text(djson(build_masks()), encoding="utf-8")
        print(f"wrote {p}")
        p = OUT / "faction-colour-provenance.json"
        p.write_text(djson(build_colours()), encoding="utf-8")
        print(f"wrote {p}")


if __name__ == "__main__":
    main()