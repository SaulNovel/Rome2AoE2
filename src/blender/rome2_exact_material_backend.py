"""Generic entry point for the frozen, capture-replay Rome II material oracle.

This module intentionally delegates to the renderer used by the approved
Hastati production frames.  Keeping the adapter free of unit keys lets the
manifest converter and parity harness share the exact implementation without
copying or approximating its equations.
"""

from render_hastati_runtime_parity import render_aov, shade

RAW_AOVS = (
    "basis_normal", "basis_tangent", "basis_bitangent", "diffuse_raw",
    "specular_raw", "gloss_raw", "normal_sample", "normal_alpha",
    "mask_raw", "dirt_raw", "dirt_alpha", "dirt_mask_raw",
    "dirt_mask_alpha", "family",
)


def render_exact(scene, texture_root, output_name):
    """Render one scene through the exact approved material/lighting path."""
    arrays = {name: render_aov(scene, texture_root, name) for name in RAW_AOVS}
    return shade(scene, arrays, output_name=output_name, diagnostics=False)
