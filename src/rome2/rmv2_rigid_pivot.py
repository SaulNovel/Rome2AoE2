"""Reference math for RMV2 rigid pivots exported through Asset Editor glTF."""

from __future__ import annotations

from typing import Iterable


def asset_editor_gltf_translation(pivot: Iterable[float], mirror_mesh: bool = True) -> tuple[float, float, float]:
    """Apply the same optional X mirror Asset Editor applies to RMV2 vertices."""
    x, y, z = (float(value) for value in pivot)
    return (-x if mirror_mesh else x, y, z)


def blender_import_translation(gltf_translation: Iterable[float]) -> tuple[float, float, float]:
    """Apply Blender's glTF Y-up to Z-up basis conversion: (x, y, z) -> (x, -z, y)."""
    x, y, z = (float(value) for value in gltf_translation)
    return (x, -z, y)


def compose_translation(parent: Iterable[float], child: Iterable[float]) -> tuple[float, float, float]:
    """Translation-only fixture for attachment * rigid-child-pivot ordering."""
    return tuple(float(a) + float(b) for a, b in zip(parent, child, strict=True))
