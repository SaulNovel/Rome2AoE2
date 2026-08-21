# Manifest-driven static conversion checkpoint

This checkpoint makes `python -B -m rome2aoe2 convert <manifest.json>` execute
the first production conversion stage. It validates a frozen manifest and its
READY dependency closure, exports only the selected Rome II models through the
existing pack helper, assembles those models in Blender, applies the recovered
Rome II material backend, validates attachments, renders four static views, and
writes a machine-readable receipt.

## Deterministic VMD selection

Rome II VMD alternative groups preserve ordered, repeated references used by
the runtime's weighted/random selection. They do not expose an authoritative
default marker. The configurator therefore presents `[A] Auto (deterministic
source-first)`: it resolves to the first distinct source asset in source order
and freezes that exact canonical path in the manifest. The manifest records
`mode: deterministic_source_first`, `resolution_policy:
first_distinct_source`, and the exact `resolved_asset`; conversion never
chooses an alternative at random.

## Principes acceptance

The Auto `Rom_Principes` manifest resolves concrete armour, body, crest,
helmet, gladius, pilum, and shield assets. There is no independent tunic slot.
Rigid equipment uses the source sockets `weapon_02`, `weapon_03`, and
`weapon_05`. The helmet/crest pair is seated by the existing asset-pair crest
solver and source `crest_centre` socket, without unit-specific transforms.

Material validation preserves `DefaultMaterial`, `Weighted`,
`WeightedDirtmap`, `WeightedSkinDirtmap`, and `DecalDirtmap`. Faction colours
are resolved from authoritative unit-variant/faction-uniform DB relationships;
skin-mask semantics are not treated as faction tint.

Outputs live under `build/conversions/<stable-unit-key>/<manifest-sha256>/`.
The receipt records exact selections, dependency identity and pack provenance,
cache use, export results, material and attachment validation, output paths,
converter version, and Git commit. Generated manifests, exports, previews, and
receipts remain build artifacts rather than source checkpoint files.
