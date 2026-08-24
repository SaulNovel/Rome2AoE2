from __future__ import annotations

WEAPON_READABILITY_CAPABILITY = "weapon_readability_v1"
MIXED_RESPONSE_CALIBRATION = {
    "diffuse_floor": 1.80,
    "transition_width": 0.15,
    "environment_reflection_floor": 0.04,
}


def classify_weapon_response(response: dict[str, float]) -> str:
    """Classify prepared Rome II response values, never asset-name metadata."""
    specular = float(response["specular_luminance"])
    smoothness = float(response["smoothness"])
    reflectivity = float(response["reflectivity"])
    if specular >= 0.25 and 0.05 <= smoothness <= 0.25 and 0.08 <= reflectivity <= 0.35:
        return "mixed_diffuse_reflective"
    return "unresolved_or_dissimilar"


def resolve_weapon_readability(
    role: str,
    response: dict[str, float],
    lower_tail_failures: tuple[str, ...] = (),
) -> dict[str, object]:
    response_class = classify_weapon_response(response)
    failures = frozenset(lower_tail_failures)
    eligible = role == "melee_weapon" and response_class == "mixed_diffuse_reflective"
    diffuse = eligible and "direct_diffuse_collapse" in failures
    reflection = diffuse and "reflective_specular_lobe_collapse" in failures
    treatment = "none"
    if reflection:
        treatment = "mixed_diffuse_and_reflection_dark_tail"
    elif diffuse:
        treatment = "diffuse_dark_tail"
    return {
        "capability": WEAPON_READABILITY_CAPABILITY,
        "role": role,
        "response_class": response_class,
        "lower_tail_failures": sorted(failures),
        "treatment": treatment,
        "enabled": diffuse,
        **({"diffuse_floor": MIXED_RESPONSE_CALIBRATION["diffuse_floor"],
            "transition_width": MIXED_RESPONSE_CALIBRATION["transition_width"]} if diffuse else {}),
        **({"environment_reflection_floor": MIXED_RESPONSE_CALIBRATION["environment_reflection_floor"]} if reflection else {}),
    }


def reflection_tail_delta(environment_luminance: float, floor: float = 0.04) -> float:
    """Missing lower tail only: bright authored reflection receives zero."""
    return max(0.0, float(floor) - float(environment_luminance))
