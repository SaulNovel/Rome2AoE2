from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .errors import ConverterError, ErrorCode


INFANTRY_VISUAL_SCALE_CAPABILITY = "infantry_visual_scale_v1"
VISUAL_SCALE_MIN = 0.90
VISUAL_SCALE_MAX = 1.10
VISUAL_SCALE_DEFAULT = 1.0
VISUAL_SCALE_REFERENCE = "aoe2_infantry_production_baseline"
CANONICAL_ORTHOGRAPHIC_SCALE = 7.27480212108078
OVERSCAN_REFERENCE_RESOLUTION = 400
OVERSCAN_REFERENCE_MARGIN = 64


def validate_visual_scale(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConverterError(
            ErrorCode.VISUAL_SCALE_OUT_OF_RANGE,
            "Infantry visual scale must be a finite numeric value within the supported range",
            requested=value, minimum=VISUAL_SCALE_MIN, maximum=VISUAL_SCALE_MAX,
        )
    result = float(value)
    if not math.isfinite(result) or not VISUAL_SCALE_MIN <= result <= VISUAL_SCALE_MAX:
        raise ConverterError(
            ErrorCode.VISUAL_SCALE_OUT_OF_RANGE,
            "Infantry visual scale is outside the supported range",
            requested=value, minimum=VISUAL_SCALE_MIN, maximum=VISUAL_SCALE_MAX,
        )
    return result


def appearance_record(value: Any = VISUAL_SCALE_DEFAULT, *, explicit: bool = False) -> dict[str, Any]:
    return {
        "visual_scale": {
            "mode": "explicit" if explicit else "deterministic_default",
            "value": validate_visual_scale(value),
            "reference": VISUAL_SCALE_REFERENCE,
            "capability": INFANTRY_VISUAL_SCALE_CAPABILITY,
        }
    }


def visual_scale_from_manifest(manifest: Mapping[str, Any]) -> float:
    appearance = manifest.get("appearance")
    if appearance is None:
        return VISUAL_SCALE_DEFAULT
    if not isinstance(appearance, Mapping) or set(appearance) != {"visual_scale"}:
        raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED,
                             "Manifest appearance must contain exactly visual_scale")
    record = appearance["visual_scale"]
    if (not isinstance(record, Mapping)
            or record.get("mode") not in {"explicit", "deterministic_default"}
            or record.get("reference") != VISUAL_SCALE_REFERENCE
            or record.get("capability") != INFANTRY_VISUAL_SCALE_CAPABILITY):
        raise ConverterError(ErrorCode.MANIFEST_SCHEMA_UNSUPPORTED,
                             "Manifest visual_scale record is malformed")
    return validate_visual_scale(record.get("value"))


def effective_orthographic_scale(visual_scale: Any,
                                 canonical: float = CANONICAL_ORTHOGRAPHIC_SCALE) -> float:
    return float(canonical) / validate_visual_scale(visual_scale)


def canvas_edge_contact(alpha_bounds: Sequence[int], canvas: Sequence[int]) -> bool:
    width, height = int(canvas[0]), int(canvas[1])
    left, top, right, bottom = (int(value) for value in alpha_bounds)
    return left == 0 or top == 0 or right == width or bottom == height


def overscan_camera(production_resolution: Sequence[int], production_ortho: float) -> dict[str, Any]:
    width, height = (int(value) for value in production_resolution)
    margin = round(OVERSCAN_REFERENCE_MARGIN * height / OVERSCAN_REFERENCE_RESOLUTION)
    overscan_width, overscan_height = width + 2 * margin, height + 2 * margin
    overscan_ortho = float(production_ortho) * overscan_height / height
    return {
        "resolution": [overscan_width, overscan_height],
        "orthographic_scale": overscan_ortho,
        "production_crop": [margin, margin, margin + width, margin + height],
        "margin": margin,
    }


def outside_alpha_metrics(alpha_values: Sequence[float], resolution: Sequence[int],
                          production_crop: Sequence[int]) -> dict[str, Any]:
    width, height = (int(value) for value in resolution)
    left, top, right, bottom = (int(value) for value in production_crop)
    if len(alpha_values) != width * height:
        raise ValueError("overscan alpha length does not match resolution")
    outside = []
    points = []
    for index, value in enumerate(alpha_values):
        x, y = index % width, index // width
        if left <= x < right and top <= y < bottom:
            continue
        alpha = float(value)
        if alpha > 0.0:
            outside.append(alpha)
            points.append((x, y))
    return {
        "outside_alpha_bounds": (None if not points else
                                  [min(x for x, _ in points), min(y for _, y in points),
                                   max(x for x, _ in points) + 1, max(y for _, y in points) + 1]),
        "outside_nonzero_count": len(outside),
        "outside_max_alpha": max(outside, default=0.0),
        "outside_alpha_energy": sum(outside),
        "confirmed_overflow": bool(outside),
    }


def validate_canvas_bounds(visual_scale: Any, category: str, direction: int, sample: int,
                           alpha_bounds: Sequence[int], canvas: Sequence[int]) -> dict[str, Any]:
    width, height = int(canvas[0]), int(canvas[1])
    bounds = [int(value) for value in alpha_bounds]
    return {"alpha_bounds": bounds, "canvas_bounds": [0, 0, width, height],
            "edge_contact": canvas_edge_contact(bounds, [width, height]),
            "overscan_performed": False, "confirmed_overflow": False}


def confirm_canvas_bounds(visual_scale: Any, category: str, direction: int, sample: int,
                          pass_name: str, alpha_bounds: Sequence[int], canvas: Sequence[int],
                          overscan: Mapping[str, Any], outside: Mapping[str, Any]) -> dict[str, Any]:
    result = validate_canvas_bounds(visual_scale, category, direction, sample, alpha_bounds, canvas)
    result.update({"overscan_performed": True,
                   "overscan_resolution": list(overscan["resolution"]),
                   "overscan_orthographic_scale": float(overscan["orthographic_scale"]),
                   "production_crop_in_overscan": list(overscan["production_crop"]),
                   **dict(outside)})
    if result["confirmed_overflow"]:
        raise ConverterError(
            ErrorCode.VISUAL_SCALE_CANVAS_OVERFLOW,
            "Overscan confirms rendered content outside the fixed production canvas",
            requested=validate_visual_scale(visual_scale), category=category,
            direction=int(direction), sample=int(sample), **{"pass": pass_name},
            alpha_bounds=result["alpha_bounds"], canvas_bounds=result["canvas_bounds"],
            edge_contact=result["edge_contact"], confirmed_overflow=True,
            overscan_resolution=result["overscan_resolution"],
            overscan_orthographic_scale=result["overscan_orthographic_scale"],
            production_crop=result["production_crop_in_overscan"],
            outside_alpha_bounds=result["outside_alpha_bounds"],
            outside_nonzero_count=result["outside_nonzero_count"],
            outside_max_alpha=result["outside_max_alpha"],
            outside_alpha_energy=result["outside_alpha_energy"],
        )
    return result
