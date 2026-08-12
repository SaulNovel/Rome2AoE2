# Rome II runtime-parity facet-03 proof

> Production bridge update: supported production materials and the numerical
> capture replays now call the same implementation in
> `src/rome2/runtime_material_preparation.py`. Blender emits raw sampled maps and
> geometric N/T/B AOVs; it no longer reproduces supported material equations in
> node graphs. See `docs/rome2-production-material-bridge.md`.

## Outcome

The exact indexed event-1247 replay subsequently validated the generic `Weighted`
path against the same captured cuirass geometry and state. See
`docs/rome2-weighted-capture-replay.md`. Its material G-buffer agrees within two
UNORM codes and its surviving midtone/bright pixels agree within 9.0% in isolated
event-1915 HDR and 0.0224 in final display RGB. The independently posed dark cuirass
is therefore a scene/pose/environment-orientation result, not evidence for further
`Weighted` material tuning.

The basis-corrected proof removes the unsupported camera-relative yaw previously
applied to the Rome II light and cube. `WeightedSkinDirtmap` has subsequently been
capture-replay validated against events 1474/1483 and its specialized event-1926
deferred-light pass. See `docs/rome2-weighted-skin-capture-replay.md`. Body/head now
route through that family without changing the frozen scene, light, environment,
tone, camera, or pose. The independently posed dark cuirass remains a scene/pose/
environment-orientation result and was not retuned.

No artistic variants, AoE processing, reduction, or SLD output were generated.

## Architecture

`src/blender/render_hastati_runtime_parity.py` retains the existing effective-unit
assembly, animation frame 1, facet 03 (112.5 degrees), orthographic camera, and
3200x3200 framing. Blender rasterises four unlit float32 EXR/NumPy passes:

- reconstructed world normal plus coverage;
- runtime-prepared linear diffuse plus coverage;
- independent linear RGB specular plus coverage;
- sRGB-view-decoded smoothness R and reflectivity G.

The offline NumPy stage then evaluates directional light, the six-colour ambient
cube, captured HDR cubemap, CA reflectivity distribution, frozen LogYxy/S-curve,
and final display transform. It writes transparent RGBA directly, without a Blender
view transform.

The implementation is material-path driven. `Weighted` uses manifest resources and
faction masks; `WeightedDirtmap` adds the captured dirt resources/equations. There is
no Hastati-bronze conductor branch.

## Implemented recovered behaviour

- alpha cutoff at 128/255;
- normal X from alpha and Y from green, each with 0.5/255 offset;
- reconstructed tangent Z; normal R/B unused;
- authored diffuse retained;
- sequential captured C0/C1/C2 faction multiplication;
- independent RGB specular;
- gloss sampled with an sRGB colour transform;
- smoothness from gloss R and reflectivity from gloss G;
- `WeightedDirtmap` diffuse/specular and normal perturbation;
- captured sun direction/colour and six ambient colours;
- environment LOD `(1-S)*8` from the captured nine-mip HDR cube;
- captured distribution `.02 + .9799*S^2`, CA error-function approximation,
  exponent 60, environment-specular scale 2.5, and diffuse scale .004;
- frozen black/log-black/white/log-white values and captured 256-sample S-curve;
- LogYxy chromaticity-preserving reconstruction;
- brightness 1.2, gamma exponent .5, and final diagonal colour matrix.

The first image exposed and corrected one transcription defect: the S-curve sample
is normalized **log luminance**, not output linear luminance. The exact shader expands
it across the captured log interval, exponentiates it, subtracts black, and divides
by the linear white-black range.

## Intentionally omitted

- SSAO: captured input is neutral white;
- terrain/baked shadows and shroud;
- self-shadowing in this base proof;
- clouds, fog, god rays, and vignette;
- bloom;
- dynamic exposure history, using the captured frozen adapted state instead.

These omissions do not explain the remaining dark directly lit cuirass: omitting
self-shadowing makes illumination less occluded, not more.

## Geometry-space recovery

The exporter/importer conversion is the proper rotation

```text
A = [[1, 0, 0], [0, 0, -1], [0, 1, 0]]
(x,y,z)Rome -> (x,-z,y)Blender
det(A) = +1
```

Thus normals, tangents, light directions, and positions use `A`; a Blender
row-vector reflection direction is converted back for D3D cube lookup by `R_B @ A`.
The lighting vector is `A * (-capturedSunDirection)`, matching the captured shader's
negation. No camera-derived or Hastati-specific yaw is valid.

The target instance buffer is resource 3750, stride 88, with transform rows at
offsets 0/16/32. Representative central instances at events 1247/1418/1602 all have
identity rotation and uniform scales 0.970217/0.973366/0.968903 respectively. Their
translations differ because they are nearby randomized soldiers. There is no
per-soldier yaw in these rows.

The material pixel shader consumes independently interpolated `N=VS.TEXCOORD2`,
`T=TEXCOORD3`, and `B=TEXCOORD5`, and evaluates
`normalize(tx*normalize(T) + ty*normalize(B) + tz*normalize(N))`. Captured cuirass
probes contain both positive and negative handedness (approximately +0.999986 at one
central probe and -0.9999 elsewhere). Handedness is therefore per vertex/UV island;
a global bitangent inversion is incorrect. The glTF/Blender path preserves tangent
`w`, but a nearest-UV comparison is not a corresponding-vertex proof where UV seams
or different randomized meshes are involved.

Example numeric probes (captured / nearest offline UV) are:

| material | UV distance | handedness | NdotL | reflection |
|---|---:|---:|---:|---|
| cuirass | 0.0153 | +1.000 / -1.000 | -0.612 / -0.350 | (-.183,.967,-.179) / (.273,-.902,.333) |
| helmet | 0.0621 | +.999 / +1.000 | -.141 / +.062 | (-.661,.729,-.177) / (.333,-.637,-.695) |
| tunic | 0.0379 | +.999 / -1.000 | +.614 / -.616 | (-.181,.960,-.214) / (.074,.726,-.684) |

These differing final vectors chiefly reflect non-corresponding geometry/pose and UV
islands, rather than evidence for another global axis change. The captured PostVS
basis itself is internally right/left handed according to the interpolated sign.

The D3D cube convention is explicitly retained: face order +X,-X,+Y,-Y,+Z,-Z, with
the standard D3D face equations and V orientation. The captured DDS is R11G11B10,
six faces, nine mips. No visual cube rotation is applied.

## Remaining structural discrepancy

The base/final-normal AOVs are populated across the cuirass and skin; these regions
are not missing AOV coverage or invalid normals. The NdotL and diffuse-only passes
show that much of the front-facing offline body receives little captured directional
light in the exact no-yaw configuration. This is coherent with that offline pose and
facet, but cannot be compared point-for-point to randomized runtime soldiers.

`Weighted`, `WeightedDirtmap`, `WeightedSkinDirtmap`, and `DecalDirtmap` are now
implemented in this proof. `DecalDirtmap` writes the standard G-buffer and routes
through validated event-1915 lighting; its material replay produced 4,830 pixels
within two UNORM codes across all targets. Feather, sword, and pilum still use
unported `DefaultMaterial` permutations. These remaining fallbacks are explicit and
were not approximated through the validated families.

A production-integration audit subsequently found and corrected one skin AOV routing
error: dirt attenuation intended for authored standard RGB specular had also been
applied to `skinMask`. The skin route now preserves the captured `RT2=skinMask.xyzz`
semantic. The strongest audited grey-leg pixel changed from display
`(.353,.396,.416)` to `(.455,.443,.439)` with all lighting and display state frozen.

The helmet dirt shader also uses captured secondary coordinates
`uv2*2 + per-instance offset`; the current proof uses the active imported UV because
that per-instance value was not yet mapped to the selected offline mesh. This is
localized and is not the cuirass failure.

The next action must therefore be one structural correction: recover the chosen
event-1247/1418/1602 instance transforms and tangent handedness from the captured
VS input/PostVS data, map them through the exporter axis transform, and validate a
small set of corresponding normals/reflection directions. Do not change material
colours, light intensity, gloss, reflectivity, or tone constants.

## Outputs

Ignored local output:

```text
build/local-integration/rome2/runtime-parity-proof/
  runtime-parity-f03.png
  comparison-sheet.png
  material-closeups.png
  debug-aov-sheet.png
  basis-comparison.json
  report.json
  aov/*.exr
  aov/*.npy
  aov/hdr_linear.npy
```

The Rome II reference crop is copied only into ignored comparison output and is not
redistributed as a tracked asset.
