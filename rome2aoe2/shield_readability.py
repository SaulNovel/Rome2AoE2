from __future__ import annotations

SHIELD_READABILITY_CAPABILITY = "shield_readability_v1"
DIFFUSE_DOMINANT_CALIBRATION = {"floor": 2.70, "transition_width": 0.15}


def classify_material_response(response: dict[str, float]) -> str:
    """Classify prepared Rome II response values without physical-name inference."""
    specular = float(response["specular_luminance"])
    reflectivity = float(response["reflectivity"])
    if specular <= 0.13 and (reflectivity <= 0.13 or specular <= 0.08):
        return "diffuse_dominant"
    if specular >= 0.14 and reflectivity >= 0.15:
        return "strongly_specular_reflective"
    return "mixed"


def resolve_shield_readability(
    role: str,
    response: dict[str, float],
    dark_tail_cause: str | None = None,
) -> dict[str, object]:
    response_class = classify_material_response(response)
    enabled = (
        role == "shield"
        and response_class == "diffuse_dominant"
        and dark_tail_cause == "direct_diffuse_collapse"
    )
    return {
        "capability": SHIELD_READABILITY_CAPABILITY,
        "role": role,
        "response_class": response_class,
        "dark_tail_cause": dark_tail_cause,
        "treatment": "smooth_pre_albedo_diffuse_irradiance_floor" if enabled else "none",
        "enabled": enabled,
        **(DIFFUSE_DOMINANT_CALIBRATION if enabled else {}),
    }
