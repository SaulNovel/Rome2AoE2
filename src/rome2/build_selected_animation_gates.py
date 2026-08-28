from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import rome2aoe2.animation as animation_module
from rome2aoe2.animation import discover, enrich_metadata, preview_cache_identity
from rome2aoe2.catalog import load_default_catalog
from rome2aoe2.conversion import load_and_validate_manifest, manifest_digest
from rome2aoe2.preview import CACHE

MANIFEST = ROOT / "build/manifests/rom_principes-explicit-animations-v2.json"
OUTPUT = ROOT / "build/validation/rome2aoe2/principes-selected-animation-gates"


def main() -> None:
    original_discover = animation_module.discover
    animation_module.discover = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("discovery must not run"))
    try:
        request = load_and_validate_manifest(MANIFEST)
    finally:
        animation_module.discover = original_discover
    groups = enrich_metadata(discover(request.unit))
    attachment = json.loads((ROOT / "build/validation/rome2aoe2/native-basis-proof/attachment-audit.json").read_text())
    phase_notes = {
        "idle": {"assessment": "stable native standing loop; no locomotion container"},
        "walk": {"assessment": "complete stride cycle; external horizontal centering only"},
        "attack": {"anticipation": "0-25%", "strike_contact": "37.5-50%", "recovery": "62.5-100%"},
        "death": {"fall": "0-50%", "grounded_settle": "62.5-75%", "stable_corpse": "75-100%",
                  "final_equipment": "shield released left; sword and pilum follow native carrier result"},
    }
    visual_manifest = {key: value for key, value in request.manifest.items() if key != "animations"}
    visual_manifest["schema_version"] = 1
    static_input = ROOT / "build/conversions" / request.unit.definition.main_unit.casefold() / manifest_digest(visual_manifest) / "static-assembly-input.json"
    static_doc = json.loads(static_input.read_text())
    result = {"format": "rome2aoe2.selected-animation-quality-gates", "version": 1,
              "manifest": str(MANIFEST), "manifest_hash": request.manifest_hash,
              "reload_hash_repeat": manifest_digest(request.manifest), "unit": request.unit.definition.main_unit,
              "animation_family": request.unit.animation.family, "skeleton": request.unit.animation.skeleton,
              "non_interactive_reload": {"passed": True, "discovery_forbidden_during_probe": True,
                                         "component_identity_sha256": manifest_digest({"components": request.manifest["components"]}),
                                         "faction_colours": static_doc["faction_colours"]}, "gates": {}}
    for category, frozen in request.manifest["animations"].items():
        candidate = next(item for item in groups[category].candidates
                         if item.resolved_asset == frozen["resolved_asset"])
        directory = CACHE / preview_cache_identity(request.manifest, candidate)
        preview = json.loads((directory / "preview-report.json").read_text())
        native = preview["native_action"]
        comparisons = native["duplicate_armature_comparisons"]
        result["gates"][category] = {
            "frozen_record": frozen, "contact_sheet": str(directory / "contact-sheet.png"),
            "representative_direction": "single approved preview direction",
            "source_sample_range": [0, candidate.frame_count - 1], "frame_count": candidate.frame_count,
            "canonical_action_frame_range": native["canonical_action_frame_range"],
            "fps": candidate.fps, "duration": candidate.duration,
            "root_displacement": candidate.root_displacement,
            "apparent_source_speed": candidate.locomotion_speed if category == "walk" else None,
            "action_name": native["canonical_action_name"],
            "action_fingerprint_before": native["action_fingerprint_before"],
            "action_fingerprint_after": native["action_fingerprint_after"],
            "action_unchanged": native["action_fingerprint_preserved"],
            "native_rest_basis": {"bone_count": native["bone_count"],
                                  "max_rest_matrix_delta": max(row["rest_matrix_max_delta"] for row in comparisons),
                                  "max_parent_hierarchy_delta": max(row["parent_hierarchy_delta"] for row in comparisons)},
            "motion_policy": native["motion_policy"],
            "attachment_carriers": native["rigid_attachment_carriers"],
            "attachment_local_transform_regression": attachment["comparison"],
            "phase_review": phase_notes[category],
        }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "selected-animation-gates.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(OUTPUT / "selected-animation-gates.json")


if __name__ == "__main__":
    main()
