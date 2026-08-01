# Rome II asset extraction

`src/rome2/resolve_variant_mesh_definition.py` accepts an already-extracted
`.variantmeshdefinition` XML file and writes a stable JSON manifest. It selects
the first child variant of every `SLOT`, follows selected
`VARIANT_MESH_REFERENCE` files below a configurable definition root, detects
reference cycles, and collects `model` and `decal_*` dependencies.

`path` preserves the original XML spelling for archive extraction and
diagnostics. `normalized_path` is a separate forward-slash, case-folded
comparison key used for deterministic sorting, deduplication, and cycle
detection. Every dependency origin records its definition, slot path, and full
reference chain. Referenced local VMD files must exist; model and texture files
are deliberately not checked until archive extraction exists.

```powershell
python src/rome2/resolve_variant_mesh_definition.py input.variantmeshdefinition manifest.json extracted
```

This tool does not read `.pack` archives. RPFM-backed extraction remains the
next stage and must preserve pack-relative paths in its output.
