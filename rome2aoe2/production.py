from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from .animation import ASSET_ROOTS, AnimationCandidate, _find_asset
from .conversion import DEFAULT_BLENDER, ROOT, load_and_validate_manifest, manifest_digest
from .errors import ConverterError, ErrorCode
from .native_assembly import assemble_native, static_visual_manifest

PROFILE = "aoe2-infantry-animation-production-v1"
EXPECTED_DIRECTIONS = [(292.5 - 22.5 * index) % 360 for index in range(16)]
ORTHOGRAPHIC_SCALE = 7.27480212108078
CAMERA_TARGET_Z = 0.8503072261810303
OUTPUT_ROOT = ROOT / "build/production/rome2aoe2"


def category_output(unit: str, manifest_hash: str, category: str, record: dict[str, Any]) -> Path:
    identity = production_identity(manifest_hash, category, record)
    return OUTPUT_ROOT / unit.casefold() / manifest_hash[:16] / category / PROFILE / identity[:16]


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


def production_identity(manifest_hash: str, category: str, record: dict[str, Any]) -> str:
    payload = {"unit": "manifest", "manifest_hash": manifest_hash, "category": category,
               "asset": record["resolved_asset"], "asset_sha256": record["asset_sha256"],
               "profile": PROFILE}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def render_manifest(path: Path, expected_hash: str | None = None,
                    blender: Path = DEFAULT_BLENDER,
                    categories: tuple[str, ...] = ("idle", "walk", "attack", "death")) -> dict[str, Any]:
    request = load_and_validate_manifest(path)
    if expected_hash is not None and request.manifest_hash != expected_hash:
        raise ConverterError(ErrorCode.MANIFEST_UNIT_MISMATCH, "Frozen production manifest hash changed",
                             expected=expected_hash, actual=request.manifest_hash)
    visual = static_visual_manifest(request.manifest)
    # output_directory uses the animated hash; static appearance uses its animation-free identity.
    static_input = ROOT / "build/conversions" / request.unit.definition.main_unit.casefold() / manifest_digest(visual) / "static-assembly-input.json"
    if not static_input.is_file():
        raise ConverterError(ErrorCode.PREVIEW_GENERATION_FAILED, "Approved static exact-material input is unavailable",
                             path=str(static_input))
    summary = {"format": "rome2aoe2.production-render-set", "version": 1,
               "manifest": str(path), "manifest_hash": request.manifest_hash,
               "profile": PROFILE, "categories": {}}
    if not categories or any(category not in {"idle", "walk", "attack", "death"} for category in categories):
        raise ValueError("production categories must be idle/walk/attack/death")
    for category in categories:
        record = request.manifest["animations"][category]
        candidate = frozen_candidate(category, record)
        blend, assembly = assemble_native(request.manifest, candidate, blender)
        output = category_output(request.unit.definition.main_unit, request.manifest_hash, category, record)
        report = output / "render-report.json"
        output.mkdir(parents=True, exist_ok=True)
        command = [str(blender), "--background", "--python",
                   str(ROOT / "src/blender/render_manifest_native_production.py"), "--",
                   "--input-blend", str(blend), "--static-input", str(static_input),
                   "--output-root", str(output), "--report", str(report),
                   "--category", category, "--manifest-hash", request.manifest_hash,
                   "--animation-asset", record["resolved_asset"], "--source-samples", str(record["frame_count"]),
                   "--source-fps", str(record["fps"]), "--action-fingerprint", assembly["action_fingerprint_before"]]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode or not report.is_file():
            raise ConverterError(ErrorCode.PREVIEW_GENERATION_FAILED, "Production rendering failed",
                                 category=category, stderr=result.stderr[-4000:], stdout=result.stdout[-4000:])
        shadow_report = output / "shadow-report.json"
        shadow_command = [str(blender), "--background", "--python",
                          str(ROOT / "src/blender/render_manifest_native_shadow.py"), "--",
                          "--input-blend", str(blend), "--output-root", str(output),
                          "--report", str(shadow_report), "--category", category,
                          "--manifest-hash", request.manifest_hash, "--animation-asset", record["resolved_asset"],
                          "--source-samples", str(record["frame_count"]), "--source-fps", str(record["fps"]),
                          "--action-fingerprint", assembly["action_fingerprint_before"]]
        shadow_result = subprocess.run(shadow_command, capture_output=True, text=True)
        if shadow_result.returncode or not shadow_report.is_file():
            raise ConverterError(ErrorCode.PREVIEW_GENERATION_FAILED, "Production shadow rendering failed",
                                 category=category, stderr=shadow_result.stderr[-4000:], stdout=shadow_result.stdout[-4000:])
        summary["categories"][category] = {"main": json.loads(report.read_text()),
                                            "shadow": json.loads(shadow_report.read_text()),
                                            "assembly": assembly}
    summary_path = OUTPUT_ROOT / request.unit.definition.main_unit.casefold() / request.manifest_hash[:16] / "production-summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary
