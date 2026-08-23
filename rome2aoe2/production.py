from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .animation import ASSET_ROOTS, AnimationCandidate, _find_asset
from .conversion import DEFAULT_BLENDER, ROOT, convert, load_and_validate_manifest
from .errors import ConverterError, ErrorCode
from .native_assembly import (V1_BLADE_CAPABILITY, assemble_native,
                              static_assembly_identity)
from .visual_scale import (VISUAL_SCALE_MAX, VISUAL_SCALE_MIN,
                           effective_orthographic_scale, validate_visual_scale,
                           visual_scale_from_manifest)

PROFILE = "aoe2-infantry-animation-production-v1"
PROFILE_ROOT = ROOT / "config/render_profiles"
EXPECTED_DIRECTIONS = [(292.5 - 22.5 * index) % 360 for index in range(16)]
ORTHOGRAPHIC_SCALE = 7.27480212108078
CAMERA_TARGET_Z = 0.8503072261810303
OUTPUT_ROOT = ROOT / "build/production/rome2aoe2"


def _raise_render_failure(report: Path, fallback_code: ErrorCode, message: str,
                          **context: Any) -> None:
    if report.is_file():
        try:
            failure = json.loads(report.read_text()).get("failure")
            if isinstance(failure, dict) and failure.get("code") in ErrorCode._value2member_map_:
                raise ConverterError(ErrorCode(failure["code"]), message,
                                     **failure.get("context", {}))
        except (OSError, json.JSONDecodeError):
            pass
    raise ConverterError(fallback_code, message, **context)


def resolve_production_profile(name: str = PROFILE) -> dict[str, Any]:
    if name == PROFILE:
        return {
            "name": PROFILE,
            "identity_version": 1,
            "main_illumination": {
                "captured_environment_yaw_degrees": 0.0,
                "readability_fill_linear": 0.0,
            },
            "attachment_capabilities": {
                "one_handed_blade/weapon_02": "one_handed_blade_v1",
            },
            "shadow": {"profile": "fixed-global-cast-shadow-v1", "modified": False},
        }
    path = PROFILE_ROOT / f"{name.replace('-', '_')}.json"
    if not path.is_file():
        raise ValueError(f"unknown production profile: {name}")
    profile = json.loads(path.read_text(encoding="utf-8"))
    if profile.get("name") != name:
        raise ValueError(f"production profile identity mismatch: {path}")
    return profile


def category_output(unit: str, manifest_hash: str, category: str, record: dict[str, Any],
                    profile_name: str = PROFILE, visual_scale: float = 1.0) -> Path:
    profile = resolve_production_profile(profile_name)
    identity = production_identity(manifest_hash, category, record, profile_name, visual_scale)
    return OUTPUT_ROOT / unit.casefold() / manifest_hash[:16] / category / profile["name"] / identity[:16]


def frozen_candidate(category: str, record: dict[str, Any]) -> AnimationCandidate:
    local = _find_asset(record["resolved_asset"], ASSET_ROOTS)
    if local is None:
        raise ConverterError(ErrorCode.ANIMATION_DEPENDENCY_MISMATCH,
                             "Frozen production animation is unavailable", category=category,
                             asset=record["resolved_asset"])
    return AnimationCandidate(
        category=category, states=tuple(record["source_states"]), resolved_asset=record["resolved_asset"],
        local_asset=str(local), metadata_paths=(), skeleton=record["skeleton"],
        frame_count=record["frame_count"], fps=record["fps"], duration=record["duration"],
        root_displacement=tuple(record["root_displacement"]),
        horizontal_displacement=record["horizontal_displacement"],
        locomotion_speed=record["locomotion_speed"], weapon_bones=tuple(record["weapon_bones"]),
        looping=record["looping"], context_tags=tuple(record["context_tags"]),
        provenance=record["provenance"],
    )


def production_identity(manifest_hash: str, category: str, record: dict[str, Any],
                        profile_name: str = PROFILE, visual_scale: float = 1.0) -> str:
    profile = resolve_production_profile(profile_name)
    visual_scale = validate_visual_scale(visual_scale)
    payload = {"unit": "manifest", "manifest_hash": manifest_hash, "category": category,
               "asset": record["resolved_asset"], "asset_sha256": record["asset_sha256"],
               "profile": profile["name"]}
    if profile.get("identity_version", 2) >= 2:
        payload.update({"visual_scale": visual_scale,
                        "attachment_capabilities": profile["attachment_capabilities"]})
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def render_manifest(path: Path, expected_hash: str | None = None,
                    blender: Path = DEFAULT_BLENDER,
                    categories: tuple[str, ...] = ("idle", "walk", "attack", "death"),
                    profile_name: str = PROFILE) -> dict[str, Any]:
    profile = resolve_production_profile(profile_name)
    request = load_and_validate_manifest(path)
    if expected_hash is not None and request.manifest_hash != expected_hash:
        raise ConverterError(ErrorCode.MANIFEST_UNIT_MISMATCH, "Frozen production manifest hash changed",
                             expected=expected_hash, actual=request.manifest_hash)
    blade_capability = profile["attachment_capabilities"]["one_handed_blade/weapon_02"]
    visual_scale = visual_scale_from_manifest(request.manifest)
    canonical_ortho = profile.get("camera", {}).get("orthographic_scale", ORTHOGRAPHIC_SCALE)
    static_identity = static_assembly_identity(request.manifest, blade_capability)
    static_input = ROOT / "build/conversions" / request.unit.definition.main_unit.casefold() / static_identity / "static-assembly-input.json"
    if not static_input.is_file():
        if blade_capability == V1_BLADE_CAPABILITY:
            raise ConverterError(ErrorCode.PREVIEW_GENERATION_FAILED,
                                 "Immutable v1 static assembly is unavailable and will not be rebuilt",
                                 path=str(static_input))
        convert(path, output_root=ROOT / "build/conversions", blender=blender,
                blade_capability=blade_capability)
    summary = {"format": "rome2aoe2.production-render-set", "version": 1,
               "manifest": str(path), "manifest_hash": request.manifest_hash,
               "profile": profile["name"], "visual_scale": visual_scale,
               "visual_scale_min": VISUAL_SCALE_MIN, "visual_scale_max": VISUAL_SCALE_MAX,
               "canonical_orthographic_scale": canonical_ortho,
               "effective_orthographic_scale": effective_orthographic_scale(
                   visual_scale, canonical_ortho),
               "categories": {}}
    if not categories or any(category not in {"idle", "walk", "attack", "death"} for category in categories):
        raise ValueError("production categories must be idle/walk/attack/death")
    for category in categories:
        record = request.manifest["animations"][category]
        candidate = frozen_candidate(category, record)
        blend, assembly = assemble_native(request.manifest, candidate, blender, blade_capability)
        output = category_output(request.unit.definition.main_unit, request.manifest_hash, category, record,
                                 profile["name"], visual_scale)
        report = output / "render-report.json"
        output.mkdir(parents=True, exist_ok=True)
        command = [str(blender), "--background", "--python",
                   str(ROOT / "src/blender/render_manifest_native_production.py"), "--",
                   "--input-blend", str(blend), "--static-input", str(static_input),
                   "--output-root", str(output), "--report", str(report),
                   "--category", category, "--manifest-hash", request.manifest_hash,
                   "--profile-name", profile["name"],
                   "--visual-scale", str(visual_scale),
                   "--animation-asset", record["resolved_asset"], "--source-samples", str(record["frame_count"]),
                   "--source-fps", str(record["fps"]), "--action-fingerprint", assembly["action_fingerprint_before"]]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode or not report.is_file():
            _raise_render_failure(report, ErrorCode.PREVIEW_GENERATION_FAILED,
                                  "Production rendering failed", category=category,
                                  stderr=result.stderr[-4000:], stdout=result.stdout[-4000:])
        shadow_report = output / "shadow-report.json"
        shadow_command = [str(blender), "--background", "--python",
                          str(ROOT / "src/blender/render_manifest_native_shadow.py"), "--",
                          "--input-blend", str(blend), "--output-root", str(output),
                          "--report", str(shadow_report), "--category", category,
                          "--manifest-hash", request.manifest_hash, "--animation-asset", record["resolved_asset"],
                          "--source-samples", str(record["frame_count"]), "--source-fps", str(record["fps"]),
                          "--action-fingerprint", assembly["action_fingerprint_before"]]
        shadow_command.extend(["--visual-scale", str(visual_scale)])
        shadow_command.extend(["--canonical-orthographic-scale", str(canonical_ortho)])
        shadow_result = subprocess.run(shadow_command, capture_output=True, text=True)
        if shadow_result.returncode or not shadow_report.is_file():
            _raise_render_failure(shadow_report, ErrorCode.PREVIEW_GENERATION_FAILED,
                                  "Production shadow rendering failed", category=category,
                                  stderr=shadow_result.stderr[-4000:], stdout=shadow_result.stdout[-4000:])
        summary["categories"][category] = {"main": json.loads(report.read_text()),
                                            "shadow": json.loads(shadow_report.read_text()),
                                            "assembly": assembly}
    base = OUTPUT_ROOT / request.unit.definition.main_unit.casefold() / request.manifest_hash[:16]
    summary_path = (base / "production-summary.json" if profile["name"] == PROFILE else
                    base / profile["name"] / "production-summary.json")
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
