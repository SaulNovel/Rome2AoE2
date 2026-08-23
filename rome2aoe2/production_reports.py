"""Profile-generic consolidation and resolution of production artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .conversion import ROOT
from .production import (EXPECTED_DIRECTIONS, ORTHOGRAPHIC_SCALE, PROFILE,
                         category_output, resolve_production_profile)
from .visual_scale import effective_orthographic_scale, visual_scale_from_manifest

CATEGORIES = ("idle", "walk", "attack", "death")
CANVASES = {"master": (800, 800), "x1": (200, 200), "x2": (400, 400)}
MATERIAL_BACKEND = "rome2_exact_material_backend/runtime_material_preparation/frozen captured runtime display"


class ProductionReportError(RuntimeError):
    """Structured failure while selecting or validating frozen production."""

    def __init__(self, reason: str, message: str, **context: Any):
        self.reason, self.context = reason, context
        detail = " ".join(f"{key}={value!r}" for key, value in sorted(context.items()))
        super().__init__(f"{reason}: {message}" + (f" ({detail})" if detail else ""))

    def as_dict(self) -> dict[str, Any]:
        return {"reason": self.reason, "message": str(self), "context": self.context}


def production_report_path(unit: str, manifest_hash: str, category: str,
                           record: dict[str, Any], production_profile: str,
                           visual_scale: float) -> Path:
    return category_output(unit, manifest_hash, category, record,
                           production_profile, visual_scale) / "production-report.json"


def sld_category_root(unit: str, manifest_hash: str, category: str,
                      production_profile: str) -> Path:
    base = ROOT / "build/sld/rome2aoe2" / unit.casefold() / manifest_hash[:16]
    return base / category if production_profile == PROFILE else base / production_profile / category


def _load(path: Path, kind: str) -> dict[str, Any]:
    if not path.is_file():
        raise ProductionReportError("PRODUCTION_ARTIFACT_MISSING", f"missing {kind}", path=str(path))
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ProductionReportError("PRODUCTION_ARTIFACT_INVALID", f"invalid {kind}",
                                    path=str(path), detail=str(error)) from error
    if not isinstance(value, dict):
        raise ProductionReportError("PRODUCTION_ARTIFACT_INVALID", f"invalid {kind}", path=str(path))
    return value


def _frame_paths(root: Path, category: str, samples: int, kind: str, scale: str):
    return [root / kind / scale / f"{category}-direction-{direction:02d}-frame-{frame:03d}.png"
            for direction in range(16) for frame in range(samples)]


def _main_reports(root: Path) -> list[dict[str, Any]]:
    canonical = root / "render-report.json"
    if canonical.is_file():
        return [_load(canonical, "main render report")]
    paths = sorted(root.glob("render-report-directions-*.json"))
    if not paths:
        raise ProductionReportError("PRODUCTION_ARTIFACT_MISSING", "missing main render reports", path=str(root))
    return [_load(path, "main direction render report") for path in paths]


def consolidate_category(request, category: str, production_profile: str) -> dict[str, Any]:
    """Validate exact-profile render artifacts and return the canonical category report."""
    if category not in CATEGORIES:
        raise ProductionReportError("PRODUCTION_CATEGORY_INVALID", "unknown category", category=category)
    profile = resolve_production_profile(production_profile)
    record = request.manifest["animations"][category]
    visual_scale = visual_scale_from_manifest(request.manifest)
    canonical = float(profile.get("camera", {}).get("orthographic_scale", ORTHOGRAPHIC_SCALE))
    effective = effective_orthographic_scale(visual_scale, canonical)
    legacy_schema = profile.get("identity_version", 2) == 1
    root = category_output(request.unit.definition.main_unit, request.manifest_hash,
                           category, record, profile["name"], visual_scale)
    main_documents, shadow = _main_reports(root), _load(root / "shadow-report.json", "shadow report")
    main = main_documents[0]
    samples, expected = int(record["frame_count"]), 16 * int(record["frame_count"])
    common = (("manifest_hash", request.manifest_hash), ("category", category),
              ("animation_asset", record["resolved_asset"]), ("native_source_samples", samples),
              ("visual_scale", visual_scale), ("canonical_orthographic_scale", canonical),
              ("effective_orthographic_scale", effective))
    for label, document in [("main", document) for document in main_documents] + [("shadow", shadow)]:
        for key, expected_value in common:
            actual_value = document.get(key, expected_value) if legacy_schema else document.get(key)
            if actual_value != expected_value:
                raise ProductionReportError("PRODUCTION_REPORT_MISMATCH", f"{label} report disagrees",
                                            category=category, field=key, expected=expected_value,
                                            actual=document.get(key), path=str(root))
        if document.get("action_fingerprint_before") != document.get("action_fingerprint_after"):
            raise ProductionReportError("PRODUCTION_ACTION_CHANGED", f"{label} Action fingerprint changed", category=category)
    for document in main_documents:
        illumination = document.get("main_illumination")
        if illumination is None and legacy_schema:
            illumination = profile["main_illumination"]
        if illumination != profile["main_illumination"]:
            raise ProductionReportError("PRODUCTION_PROFILE_MISMATCH", "main illumination policy changed",
                                        category=category, expected=profile["main_illumination"],
                                        actual=document.get("main_illumination"))
    main_records = [item for document in main_documents for item in document.get("records", ())]
    main_keys = {(item.get("direction"), item.get("output_frame")) for item in main_records}
    shadow_keys = {(item.get("direction"), item.get("output_frame")) for item in shadow.get("records", ())}
    expected_keys = {(direction, frame) for direction in range(16) for frame in range(samples)}
    if main_keys != expected_keys or len(main_records) != expected or shadow_keys != expected_keys or len(shadow.get("records", ())) != expected:
        raise ProductionReportError("PRODUCTION_INVENTORY_MISMATCH", "report direction/sample coverage changed", category=category)
    if sorted({item for document in main_documents for item in document.get("direction_order", ())}) != list(range(16)) or shadow.get("direction_order") != list(range(16)) or shadow.get("direction_yaws") != EXPECTED_DIRECTIONS:
        raise ProductionReportError("PRODUCTION_REPORT_MISMATCH", "direction order changed", category=category)
    fingerprints = {document.get("action_fingerprint_before") for document in main_documents}
    if fingerprints != {shadow.get("action_fingerprint_before")}:
        raise ProductionReportError("PRODUCTION_REPORT_MISMATCH", "main/shadow Action fingerprints differ", category=category)
    if main.get("profile") != profile["name"]:
        raise ProductionReportError("PRODUCTION_PROFILE_MISMATCH", "main profile policy changed", category=category)
    if shadow.get("profile") != profile["shadow"]["profile"]:
        raise ProductionReportError("PRODUCTION_PROFILE_MISMATCH", "shadow profile policy changed", category=category)
    if main.get("material_backend") != MATERIAL_BACKEND:
        raise ProductionReportError("PRODUCTION_REPORT_MISMATCH", "material backend changed", category=category,
                                    expected=MATERIAL_BACKEND, actual=main.get("material_backend"))
    expected_hotspot = {"x1": [100, 122], "x2": [200, 244], "ground_anchor": "unchanged"}
    if not legacy_schema:
        if main.get("canvas") != {"master": [800, 800], "x2": [400, 400], "x1": [200, 200]} or shadow.get("canvas") != {"x2": [400, 400], "x1": [200, 200]}:
            raise ProductionReportError("PRODUCTION_REPORT_MISMATCH", "canvas policy changed", category=category)
        if main.get("hotspot_policy") != expected_hotspot or shadow.get("hotspot_policy") != expected_hotspot:
            raise ProductionReportError("PRODUCTION_REPORT_MISMATCH", "hotspot policy changed", category=category)
    validations = [item.get("canvas_validation", {}) for item in main_records + shadow["records"]]
    overflow = sum(bool(item.get("confirmed_overflow")) for item in validations)
    if overflow:
        raise ProductionReportError("PRODUCTION_CANVAS_OVERFLOW", "confirmed production overflow", category=category, count=overflow)
    inventory = {"root": str(root), "main_master": expected}
    for kind in ("main", "shadow"):
        for scale in ("x1", "x2"):
            paths = _frame_paths(root, category, samples, kind, scale)
            missing = [str(path) for path in paths if not path.is_file()]
            if missing:
                raise ProductionReportError("PRODUCTION_INVENTORY_MISMATCH", "missing production frames",
                                            category=category, kind=kind, scale=scale,
                                            missing_count=len(missing), first_missing=missing[0])
            inventory[f"{kind}_{scale}"] = len(paths)
    masters = _frame_paths(root, category, samples, "main", "master")
    if any(not path.is_file() for path in masters):
        raise ProductionReportError("PRODUCTION_INVENTORY_MISMATCH", "missing main master frames", category=category)
    return {
        "format": "rome2aoe2.consolidated-production-category", "version": 2,
        "manifest_hash": request.manifest_hash, "production_profile": profile["name"],
        "production_identity": root.name, "category_root": str(root), "category": category,
        "exact_animation_asset": record["resolved_asset"],
        "action_fingerprint": main["action_fingerprint_before"], "native_frames": samples,
        "native_fps": record["fps"], "rendered_sample_mapping": main["rendered_sample_mapping"],
        "direction_order": list(range(16)), "direction_yaws": EXPECTED_DIRECTIONS,
        "visual_scale": visual_scale, "canonical_orthographic_scale": canonical,
        "effective_orthographic_scale": effective, "camera_profile": profile["name"],
        "production_scale": effective, "master_dimensions": list(CANVASES["master"]),
        "x1_dimensions": list(CANVASES["x1"]), "x2_dimensions": list(CANVASES["x2"]),
        "material_backend": main.get("material_backend"),
        "main_illumination": profile["main_illumination"],
        "attachment_capabilities": profile["attachment_capabilities"],
        "shadow_profile": profile["shadow"]["profile"], "output_inventory": inventory,
        "source_reports": {"main": [str(root / "render-report.json")] if (root / "render-report.json").is_file() else [str(path) for path in sorted(root.glob("render-report-directions-*.json"))], "shadow": str(root / "shadow-report.json")},
        "validation": {"production_identity": True, "main_shadow_parity": True,
                       "x1_x2_parity": True, "confirmed_overflow_count": overflow,
                       "action_preserved": True, "complete_inventory": True,
                       "material_backend": main.get("material_backend") == MATERIAL_BACKEND},
    }


def write_consolidated_category(request, category: str, production_profile: str) -> Path:
    report = consolidate_category(request, category, production_profile)
    path = Path(report["category_root"]) / "production-report.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def resolve_consolidated_category(request, category: str, production_profile: str) -> tuple[Path, dict[str, Any]]:
    record = request.manifest["animations"][category]
    visual_scale = visual_scale_from_manifest(request.manifest)
    path = production_report_path(request.unit.definition.main_unit, request.manifest_hash,
                                  category, record, production_profile, visual_scale)
    report = _load(path, "consolidated production report")
    expected = consolidate_category(request, category, production_profile)
    profile = resolve_production_profile(production_profile)
    if profile.get("identity_version", 2) == 1:
        for key in ("production_profile", "production_identity", "category_root", "visual_scale",
                    "canonical_orthographic_scale", "effective_orthographic_scale", "main_illumination"):
            report.setdefault(key, expected[key])
    keys = ("manifest_hash", "production_profile", "production_identity", "category",
            "exact_animation_asset", "action_fingerprint", "native_frames", "native_fps",
            "visual_scale", "canonical_orthographic_scale", "effective_orthographic_scale",
            "direction_order", "direction_yaws", "main_illumination", "output_inventory")
    for key in keys:
        if report.get(key) != expected.get(key):
            raise ProductionReportError("CONSOLIDATED_REPORT_MISMATCH", "consolidated report is stale or invalid",
                                        category=category, field=key, expected=expected.get(key), actual=report.get(key))
    return path, report
