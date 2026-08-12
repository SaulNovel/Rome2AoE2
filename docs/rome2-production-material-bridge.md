# Rome II production material bridge audit

## Result

The production renderer now sends raw Blender-rasterized texture samples and
geometric `N/T/B` AOVs through `src/rome2/runtime_material_preparation.py`.
The Weighted, WeightedSkinDirtmap, and captured-state DecalDirtmap replays import
that same module. Blender nodes no longer contain copies of their diffuse, faction,
dirt, normal-decode, specular, smoothness, reflectivity, or G-buffer equations.

Lighting1915, Lighting1926, and the frozen display constants were not changed.

## Confirmed bridge defects

1. The prior skin normal image node had no explicit vector input and therefore
   sampled Blender's active `UVMap` (glTF `TEXCOORD_0`). The captured skin shader
   samples its normal from the separately preserved `TEXCOORD_1.zw`, exported as
   glTF `TEXCOORD_1` and imported as `UVMap.001`. The raw normal-sample pass now
   selects that layer explicitly for WeightedSkinDirtmap.
2. The deleted node helper added dirt to tangent X/Y and then reconstructed Z.
   Captured WeightedSkinDirtmap reconstructs Z from base X/Y first. The shared
   function preserves that order. The same node helper had affected
   WeightedDirtmap and DecalDirtmap production; both now leave that helper.
3. During the bridge conversion, a diagnostic first render exposed that Blender
   surface alpha is coverage, not texture alpha. Normal A and dirt/dirt-mask A are
   now emitted as explicit scalar AOVs. This avoids silently replacing each sampled
   texture alpha with object coverage.

## Shared API and ownership

`runtime_material_preparation.py` owns `prepare_weighted`,
`prepare_weighted_dirtmap`, `prepare_weighted_skin_dirtmap`,
`prepare_decal_dirtmap`, tangent-normal decoding, faction application, material
controls, and family-specific G-buffer packing.

Blender retains unit assembly, animation/skinning, evaluated geometry, camera,
coverage/alpha testing, texture filtering, and rasterized raw base normal, tangent,
bitangent and texture samples. The custom backend owns material preparation,
deferred lighting, environment evaluation, and tone/display.

Distinct coordinate semantics remain explicit: skin normal sampling uses
`UVMap.001`; current base maps use `UVMap`; skin dirt uses `UVMap*4`; the known
per-instance dirt offset remains zero rather than invented.

## Duplication audit

Removed from production nodes: AG decode, tangent Z reconstruction, dirt normal
perturbation, dirt diffuse lerp, dirt specular attenuation, faction tint, skin-mask
selection/handling, and gloss/reflectivity extraction. Lighting and tone equations
still have scalar capture-replay and vectorized production implementations; they
were frozen and are outside this material-bridge change. A later mechanical
extraction can unify those without reopening their validated constants.

## Visual status

The corrected shared-backend render is `runtime-parity-f03.png`; the frozen bridge
input is `runtime-parity-f03-pre-shared-backend.png`, and enlarged regional crops
are `shared-material-backend-before-after.png` under ignored runtime-parity output.
The bridge removes the two structural normal-path discrepancies but does not make
the independently posed unit broadly brighter. Dark cuirass and neutral/cool
back-facing leg regions remain attributable to their frozen lighting/orientation;
DefaultMaterial crest/weapons remain unsupported and were not investigated here.

WeightedDirtmap remains RECOVERED/IMPLEMENTED rather than promoted to VALIDATED.
DecalDirtmap retains its precise status: captured base/dirt and StandardLighting1915
route VALIDATED; overlay equations RECOVERED; nonzero decal-array alpha not exercised.
