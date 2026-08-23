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


def validate_canvas_bounds(visual_scale: Any, category: str, direction: int, sample: int,
                           alpha_bounds: Sequence[int], canvas: Sequence[int]) -> None:
    width, height = int(canvas[0]), int(canvas[1])
    left, top, right, bottom = (int(value) for value in alpha_bounds)
    if left <= 0 or top <= 0 or right >= width or bottom >= height:
        raise ConverterError(
            ErrorCode.VISUAL_SCALE_CANVAS_OVERFLOW,
            "Rendered content reaches the fixed production canvas boundary",
            requested=validate_visual_scale(visual_scale), category=category,
            direction=int(direction), sample=int(sample),
            alpha_bounds=[left, top, right, bottom], canvas_bounds=[0, 0, width, height],
        )
