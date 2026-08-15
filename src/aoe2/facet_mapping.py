"""Canonical AoE2 16-facet mapping for Rome2AoE2 unit renders."""

FACET_COUNT = 16
STEP_DEGREES = 360.0 / FACET_COUNT

# AoE selects facets clockwise starting at east (0=E, 4=S, 8=W, 12=N).
# The accepted render set advances in the opposite rotational direction.  The
# runtime diagnostic plus the approved source-facing audit establish source 10
# as east, hence the required reversal and zero-point adjustment below.
LEGACY_SOURCE_ZERO = 10


def legacy_source_facet(runtime_facet: int) -> int:
    if not 0 <= runtime_facet < FACET_COUNT:
        raise ValueError("facet must be in [0, 15]")
    return (LEGACY_SOURCE_ZERO - runtime_facet) % FACET_COUNT


def soldier_yaw_degrees(runtime_facet: int) -> float:
    """Physical soldier yaw for an AoE runtime facet in Blender world axes."""
    if not 0 <= runtime_facet < FACET_COUNT:
        raise ValueError("facet must be in [0, 15]")
    return (292.5 - runtime_facet * STEP_DEGREES) % 360.0
