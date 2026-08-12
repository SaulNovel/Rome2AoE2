# Asset Editor native Hastati checkpoint

This document freezes the accepted single-frame and full-animation Hastati
pipeline. It is a reproduction record, not permission to change any accepted
geometry, skeleton, animation, attachment, material, camera, lighting, or colour
setting.

## Accepted reference

- Frame: `33`
- Resolution: `1600x1600`
- SHA-256: `13b5db4259e51e8966697d60c5d337f996512389d3ed7e721171ca6612391b70`
- Local reference: `build/community_tool_investigation/asset-editor-runtime-integration/integration-material-render.png`

The reference is produced with Blender's Raw view transform and transparent
film. Blender rasterises raw geometry/material AOVs; the recovered runtime
backend performs material preparation, lighting, environment evaluation, and
display conversion. Generic Principled metalness is not part of this pipeline.

## Vanilla composition and conversion

The source VMD is
`variantmeshes/variantmeshdefinitions/roman_hastati.variantmeshdefinition`.
The resolved standard composition is:

| Part | Vanilla RMV2 | Material family | Attachment |
|---|---|---|---|
| body, head, eyes/teeth, sandals | `variantmeshes/_variantmodels/man/skin/roman_skin1_shape1.rigid_model_v2` | `WeightedSkinDirtmap` / `Weighted` | skinned |
| tunic | `variantmeshes/_variantmodels/man/tunics/e3_tunic.rigid_model_v2` | `Weighted` | skinned |
| cuirass | `variantmeshes/_variantmodels/man/armour/italian_square_muscled_cuirass_a.rigid_model_v2` | `Weighted` | skinned |
| helmet | `variantmeshes/_variantmodels/man/helmets/roman_montefortino.rigid_model_v2` | `WeightedDirtmap` | skinned |
| crest | `variantmeshes/_variantmodels/man/crests/black_feather_03.rigid_model_v2` | `DefaultMaterial` | `crest_centre` |
| shield | `variantmeshes/_variantmodels/man/shield/roman_early_scutum.rigid_model_v2` | `DecalDirtmap` | `weapon_03` |
| gladius | `variantmeshes/_variantmodels/man/weapons/roman_gladius.rigid_model_v2` | `DefaultMaterial` | `weapon_02` |
| light pilum | `variantmeshes/_variantmodels/man/weapons/roman_pilum_light.rigid_model_v2` | `DefaultMaterial` | `weapon_05` |

Asset Editor is canonical for RMV2 geometry and UV conversion, skeleton and
inverse-bind matrices, vertex weights, animation decoding/export, and texture
dependency resolution. Export the body with `RmvToGltfExporter`, using the
original PackFiles directly:

- skeleton: `animations/skeletons/rome_man_game.anim`
- animation: `animations/rome2/human/battle/sword_and_shield/stand/sws_stand.anim`
- animation objects: Asset Editor `AnimationFile` / `AnimationClip`
- exporter input: `RmvToGltfExporter.InputAnimationFiles`

Import the animated glTF with Blender's standard glTF importer. The body export's
50-bone `rome_man_game` armature is canonical. Repoint the tunic, cuirass, and
helmet's existing Armature modifiers and parenting to it without modifying vertex
groups, weights, inverse binds, or geometry; delete their duplicate imported
armatures only after evaluated-vertex equality is verified. The accepted scene
has one armature and 12 mesh objects.

Rigid parts use their resolved VMD attachment name and source-local transform.
They are constrained to the identically named pose bone on the canonical armature;
the object-to-bone local matrix remains constant while the bone animates. No visual
placement, custom pose JSON, `apply_static_pose()`, decoded animation matrices, or
replacement keyframes are used. Stability of this local matrix is a following
check only and is not proof that the selected initial attachment transform is
semantically correct.

## Textures and material routing

Resolve texture dependencies by their original vanilla pack paths through Asset
Editor and retain path, pack, byte length, and SHA-256 in the local texture
manifest. RPFM-extracted DDS files may be used only as byte-identical provenance
checks and runtime samples. Do not commit DDS, RMV2, animation, pack, converted
texture, glTF, Blend, or Asset Editor binary files.

For colour/material PNG export, Asset Editor must use
`ConvertMaterialTextureToBlender = false`; TextureHelper has already corrected DDS
byte order. Normal conversion is independent. The accepted runtime renderer
samples original DDS resources to avoid PNG channel-order ambiguity.

Dispatch by the vanilla material-family identity, never by component name:

- `Weighted` -> `prepare_weighted` -> StandardLighting1915
- `WeightedDirtmap` -> `prepare_weighted_dirtmap` -> StandardLighting1915
- `WeightedSkinDirtmap` -> `prepare_weighted_skin_dirtmap` -> SkinLighting1926
- `DecalDirtmap` -> `prepare_decal_dirtmap` -> StandardLighting1915
- `DefaultMaterial` -> ordinary spec/gloss `prepare_weighted` fallback -> StandardLighting1915; this fallback is explicitly not runtime-validated

The shared preparation implementation is
`src/rome2/runtime_material_preparation.py`. The AOV rasterisation and frozen
StandardLighting1915, SkinLighting1926, ambient/environment, and display backend
are in `src/blender/render_hastati_runtime_parity.py`. Raw passes are coverage,
UV-dependent texture samples, world normal, tangent, bitangent, normal/dirt alpha,
and material family. Skin normals use `UVMap.001` (glTF `TEXCOORD_1`); other
current maps use `UVMap`. The faction colours and sequential mask lerps are the
captured `rom_rome` values in the renderer. Do not replace separate diffuse,
RGB specular, smoothness, and reflectivity with metalness.

## Local reproduction

Required local inputs, all ignored under `build/...`:

- accepted assembled scene:
  `build/community_tool_investigation/complete-hastati-native-textured/complete-hastati-native-textured.blend`
- per-material vanilla dependency manifest and DDS tree:
  `build/local-integration/rome2/cross-unit-calibration/units/hastati/`
- capture-derived environment resources referenced by
  `render_hastati_runtime_parity.py`

The accepted local drivers are retained as reproducible evidence:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\build\community_tool_investigation\asset-editor-runtime-integration\render_integration.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --python .\build\community_tool_investigation\asset-editor-runtime-integration\render_full_animation.py
python -B .\build\community_tool_investigation\asset-editor-runtime-integration\make_full_animation_summary.py
```

`render_integration.py` fixes frame 33, camera construction, 1600-square AOV
rendering, material routing, and the runtime shade call. `render_full_animation.py`
imports that configuration unchanged, evaluates integer frames 0 through 66, and
checks frame 33 against the frozen hash. No setting may be tuned between these
commands.

## Accepted full-animation validation

- rendered frames: `0-66`
- resolution: `1600x1600`
- Blender render FPS: `24`
- native Action range: `0-65.637939`
- armatures: `1`
- bones: `50`
- mesh objects: `12`
- unique output hashes: `67/67`
- maximum rigid-attachment local matrix drift: `2.68e-7`
- all AOVs finite at every frame
- topology invariant at every frame
- every required material family present at every frame
- no geometry explosion, component detachment, or frozen rigid attachment

The known Asset Editor timing boundary remains: the header duration is 2.8 s and
the last exported key is approximately 2.734914 s. Frame 66 is the established
rounded-end Blender evaluation; this checkpoint does not alter timing.

Local validation evidence is written to:

- `build/community_tool_investigation/asset-editor-runtime-integration/full-animation-validation.json`
- `build/community_tool_investigation/asset-editor-runtime-integration/full-animation-summary.json`
- `build/community_tool_investigation/asset-editor-runtime-integration/full-animation-report.md`
- `build/community_tool_investigation/asset-editor-runtime-integration/animation-frames/`

Everything under `build/...` is reproducible local evidence and must not be
committed. This tracked document and the source/test files named above are the
checkpoint; proprietary inputs and generated outputs remain local.
