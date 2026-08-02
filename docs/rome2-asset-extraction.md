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

## Pack access helper

The pinned RPFM 5.0.5 checkout does not provide the one-shot `rpfm_cli`
assumed by the original extraction plan. Its `rpfm_server` exposes equivalent
operations through a long-running WebSocket/MCP service, which is deliberately
not used by this pipeline because session and protocol management would leak
RPFM implementation details into the C++ orchestration layer.

Instead, Rome2AoE2 owns `tools/rome2_pack`, a small Rust executable named
`rome2aoe2-pack`. It depends on the pinned local `rpfm_lib` crate and exposes a
stable CLI/JSON boundary for the C++ layer. Rust is not part of the normal CMake
build and no Rust/C++ FFI is used.

Build it explicitly with Rust 1.85 or newer:

```powershell
cargo build --release --manifest-path tools/rome2_pack/Cargo.toml
```

The initial commands each operate on exactly one explicitly supplied pack:

```powershell
rome2aoe2-pack list --pack C:\RomeII\data\models.pack
rome2aoe2-pack contains --pack C:\RomeII\data\models.pack --path variantmeshes\variantmeshdefinitions\example.variantmeshdefinition
rome2aoe2-pack extract --pack C:\RomeII\data\models.pack --path variantmeshes\variantmeshdefinitions\example.variantmeshdefinition --output-root build\extracted
```

Successful commands write deterministic JSON to standard output and diagnostics
to standard error. `contains` returns `exists: false` for an absent asset;
`extract` fails if the requested asset is absent or its expected output file is
not produced.

The helper accepts slash or backslash logical paths, preserves the stored pack
path spelling when it is available, and uses a separate lowercase comparison
key for lookup. Empty, absolute, drive-qualified, and traversal paths are
rejected. Extraction validates the archive path before joining it to the output
root and preserves its directory hierarchy.

Multiple-pack lookup and precedence are intentionally not implemented yet.
The next milestone must define explicit configured pack order before using
RPFM's merge support. RPFM handles encrypted and compressed entries internally;
the helper extracts the decoded, logical file bytes rather than reimplementing
pack decoding. No schemas, game installation, or game path are needed for
one-pack binary extraction; the helper selects RPFM's built-in `rome_2`
configuration only to decode the PFH4 archive format.

Run the helper tests without Rome II assets once Cargo is available:

```powershell
cargo test --manifest-path tools/rome2_pack/Cargo.toml
```

They create a temporary synthetic PFH4 pack with `rpfm_lib`; no pack fixture or
extracted game asset is committed. A real-pack integration test remains future,
optional work and should use explicitly configured local inputs.

## Recursive VMD acquisition

`src/rome2/acquire_variant_mesh_definitions.py` coordinates the existing VMD
resolver with the helper. Supply `--pack` repeatedly in explicit priority order:
the first matching pack wins and later matches are recorded as `shadowed_packs`.
It extracts only selected referenced `.variantmeshdefinition` files, then writes
`vmd-acquisition.json` and `dependencies.json` below the supplied output root.

```powershell
python src/rome2/acquire_variant_mesh_definitions.py --helper tools\rome2_pack\target\release\rome2aoe2-pack.exe --pack C:\RomeII\data\models3_rome2.pack --root-path variantmeshes\variantmeshdefinitions\example.variantmeshdefinition --output-root build\extracted
```

Configured order is provisional; it is not an attempt to model Rome II's full
pack-loading rules.

## Direct dependency extraction

Resolver manifest version 3 preserves the effective VMD `attach_point` on
every dependency origin. The value is inherited from the nearest enclosing
slot with a nonempty `attach_point`, including across nested VMD references;
a nearer nonempty declaration overrides it. Origins without one contain
`"attach_point": null`. Extraction accepts both resolver versions 2 and 3.
For version 2, an absent field remains unavailable and is never inferred from
the slot name or `slot_path`.

`extract_dependency_manifest.py` extracts only resolver-listed `.rigid_model_v2`
models and direct `decal_*` texture identifiers. It writes a separate
`rome2aoe2.asset-extraction` manifest with `success`, `success-with-skips`, or
`failed` status; missing raw assets and extraction failures are distinct.
Origin records are copied unchanged into that manifest and subsequently into
the deterministic RMV2 batch-export manifest.

Praetorian Guard validation extracted all ten RMV2 models from
`models3_rome2.pack`. Its raw `decal_diffuse` and `decal_normal` identifiers
were not direct archive paths in the configured model packs and are recorded as
missing without adding extensions or transformations. Logical decal resolution
is a separate future stage: investigate its relation to texture/material
resources, relevant pack types, and model/material metadata.

## RMV2 decoder compatibility

Rome II RMV2 v6 inspection uses a small managed overlay for three
DefaultMaterial-compatible RPFM material IDs. The overlay is applied only during
developer setup and is documented in [RMV2 investigation](RESEARCH/RMV2.md).
It currently enables decoder-based inspection of all ten extracted Praetorian
Guard models; it does not add geometry export, texture resolution, or animation
support.
