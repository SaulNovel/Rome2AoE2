# Rome II battlefield shader recovery

## Result

The D3D11 capture is sufficient to reproduce the **captured Hastati material
response** offline without deriving material or colour behaviour from screenshots.
It is not sufficient for bit-identical reconstruction of the complete battlefield
frame: the selected weather XML identity and the provenance of the runtime-generated
environment cube remain unknown, and an offline renderer must generate its own
geometry depth and self-shadowing.

This distinction is important. The captured frame contains the exact material
shaders, source textures, G-buffer encoding, faction colours, lighting shader and
constants, environment cube pixels, frozen exposure state, S-curve LUT, bloom/tone
map shaders, and display conversion. Those are the inputs responsible for the unit's
bronze, cloth, skin, and leather response. No screenshot fitting is needed for them.

## Evidence boundary and preserved artifacts

The primary evidence is:

```text
build/local-integration/rome2/runtime-shader-recovery/captures/images-frame46753.rdc
```

It is a valid RenderDoc 1.45.0 D3D11 capture at 1920x1080 and contains a close,
visible group of Hastati. Captures `images-frame48305.rdc` and
`images-frame50974.rdc` were retained as secondary visual/pipeline evidence. The
original captures were not modified.

Machine-readable extraction is under the ignored directory:

```text
build/local-integration/rome2/runtime-shader-recovery/capture-analysis/frame46753/
  actions.json
  target-events.json
  pipeline-scan.json
  resources.json
  cb-probe.txt
  postvs.txt
  shaders/                 # captured DXBC and disassembly; proprietary, ignored
  resources-export/        # captured DDS/buffers; proprietary, ignored
```

This report may be tracked. Captured shader binaries, textures, cubemaps, and the
`.rdc` files must remain ignored and must not be committed.

Three sources are kept distinct:

1. `assembly_kit/max_exporter/max_shader/ca_shader.fx`: official CA source for the
   3ds Max preview, useful for naming and intent but not the battlefield authority.
2. shipped `data.pack/fxc` DXBC: exact game code, without proof of a frame binding.
3. the `.rdc`: authoritative shader permutation, resource view, state, and
   per-frame value evidence.

All equations below labelled exact come from (3), not screenshot matching.

## Hastati draw-call attribution

| Part | Material | Event(s) | Indices / instances | Captured PS | Path |
|---|---|---:|---:|---:|---|
| cuirass | `italian_square_muscled_cuirass_` | 1247 | 4200 / 24 | 2139 | `Weighted` |
| helmet | `roman_montefortino` | 1418 | 1698 / 10 | 2168 | `WeightedDirtmap` |
| tunic | `E3_tunic` | 1596, 1602 | 3342 / 22, 44 | 2133 | `Weighted`, faction |
| tunic reverse | `E3_tunic_flipped` | 1609, 1615 | 1932 / 22, 44 | 2133 | `Weighted`, faction |

The corresponding early shadow/depth draws are cuirass 169, helmet 259, tunic 332,
and flipped tunic 337. Attribution does not rely on index counts alone:

- captured shader reflection names the expected material resources;
- exported runtime diffuse/specular/normal/gloss payloads match the extracted
  authored cuirass DDS payloads byte-for-byte (the DDS container headers differ);
- PostVS output is the expected animated skinned geometry for every instance;
- the target geometry and resources contribute to the visible Hastati.

The capture contains multiple soldiers. For the representative faction-channel
identity mapping, events 1602 and 1615 are the relevant tunic permutations.

## Bound material resources

| Draw | Slot | Shader name | Resource | Captured view |
|---|---:|---|---:|---|
| cuirass | t0 | `s_diffuse_map` | 6593 | 512x256 BC1 sRGB |
|  | t1 | `s_specular_colour_map` | 6595 | 512x256 BC1 sRGB |
|  | t2 | `s_normal_map` | 5759 | 512x256 BC3 linear |
|  | t3 | `s_gloss_map` | 6597 | 512x256 BC1 sRGB |
| helmet | t0 | `s_diffuse_map` | 6865 | 256x256 BC1 sRGB |
|  | t1 | `s_specular_colour_map` | 7609 | 128x128 BC1 sRGB |
|  | t2 | `s_normal_map` | 6573 | 256x256 BC3 linear |
|  | t3 | `s_gloss_map` | 7611 | 128x128 BC1 sRGB |
|  | t4 | `s_decal_dirt_mask` | 7925 | 16x16 BC3 linear |
|  | t5 | `s_decal_dirt_map` | 6571 | 256x256 BC3 linear |
| tunic | t0 | `s_diffuse_map` | 5723 | 512x512 BC1 sRGB |
|  | t1 | `s_specular_colour_map` | 5725 | 512x512 BC1 sRGB |
|  | t2 | `s_colour_mask_map` | 5174 | 512x512 BC3 linear |
|  | t3 | `s_normal_map` | 5168 | 512x512 BC3 linear |
|  | t4 | `s_gloss_map` | 5727 | 512x512 BC1 sRGB |

The sRGB view on the gloss texture is an exact and consequential runtime fact. The
current Blender reconstruction commonly marks gloss as non-colour data, so its
smoothness and reflectivity values do not equal the game's sampled values.

Material draws use opaque replacement writes (blending disabled), triangle lists,
back-face culling, and enabled depth test/write. Diffuse alpha is cut out at
`128/255` before G-buffer output.

All bound helmet, cuirass, and tunic texture slots use the same sampler object 107:
linear minification, magnification, and mip filtering; wrap on U/V/W; LOD range
`0..FLT_MAX`; mip bias zero; comparison disabled. The lighting shader also samples
the environment cubemap through sampler s0/object 107, so its explicit LOD is not
clamped away. Other screen-space/postprocess samplers are captured in
`samplers.json`; they are predominantly point-or-linear clamp samplers, with the
cascaded-shadow comparison sampler kept separate.

## Exact material preparation and G-buffer

### Packed normal

For all three captured material paths:

```text
tx = 2 * (normal.a + 0.5/255) - 1
ty = 2 * (normal.g + 0.5/255) - 1
tz = sqrt(max(0, 1 - tx*tx - ty*ty))
```

Normal-map R and B are not read by these pixel shaders. The interpolated tangent,
bitangent, and normal are normalized separately; the reconstructed tangent-space
normal is transformed and normalized. A coordinate-system conversion may require a
basis sign change offline, but it must not change this texture decode.

The world normal is max-component encoded:

```text
m       = max(abs(N.x), abs(N.y), abs(N.z))
RT0.rgb = saturate(0.5 + 0.5*N/m)
RT0.a   = saturate(gloss.r)
```

### Diffuse, reflectivity, and RGB specular

The two generic per-vertex controls emitted in VS `o8.xy` are exactly `(0,0)` for
all inspected target instances. Their generic shader branch can desaturate/boost
diffuse and suppress reflectivity, but it is inactive for these Hastati draws.
Consequently:

```text
reflectivity = gloss.g
specularRGB  = specularTexture.rgb
```

For non-faction materials, `D` is the sampled linear diffuse. For the tunic:

```text
D = lerp(D, D*C0, mask.r)
D = lerp(D, D*C1, mask.g)
D = lerp(D, D*C2, mask.b)
```

There is no `get_adjusted_faction_colour` calculation in this runtime pixel shader.
The four colours arrive already prepared in a constant buffer.

The three bound colour targets are:

| Target | Format | Exact captured semantics |
|---|---|---|
| RT0 resource 3838 | B8G8R8A8_UNORM | RGB max-component encoded world normal; A smoothness |
| RT1 resource 3841 | B8G8R8A8_UNORM | RGB `sqrt(saturate(linear D))`; A reflectivity |
| RT2 resource 3844 | B8G8R8A8_UNORM | RGB linear authored specular colour; A zero |
| depth resource 3834 | D24S8 | material depth/stencil |

The square-root diffuse storage compensates for an UNORM, non-sRGB G-buffer. The
lighting shader squares RT1 RGB to recover linear diffuse.

### Helmet dirt path

`WeightedDirtmap` additionally uses the dirt-map R/G channels as a masked normal
perturbation. With `d = dirtMap.a*dirtMask.a`:

```text
D           = lerp(D, [0.03, 0.025, 0.02], d)
specularRGB = specularRGB * (1 - 0.99*d)
```

This proves that the helmet is not treated as a special conductor. It retains its
authored diffuse and independent RGB specular, smoothness, and reflectivity, with a
localized authored dirt modification.

## Exact captured faction colours

Identity-mapped tunic events 1602/1615 contain:

| Colour | Database value | Captured float3 |
|---|---|---|
| C0 | `#A62416` | (0.388910264, 0.013473397, 0.004559755) |
| C1 | `#FFB504` | (1.000000000, 0.470440269, 0.000107187) |
| C2 | `#993D24` | (0.325036973, 0.042987015, 0.013473397) |
| C3 | repeats C0 | (0.388910264, 0.013473397, 0.004559755) |

These match component-wise normalized sRGB raised to 2.2. Events 1596/1609 swap C0
and C2 because that variant uses a channel permutation. The runtime evidence therefore
rejects applying the Max-preview dark-colour brightness adjustment: CPU preparation
for this battle is a 2.2 linearisation of the database colours.

## Deferred daylight and environment pass

The principal deferred directional-light draw is event 1915 (PS resource 703),
writing resource 3850, format R11G11B10_FLOAT. Event 1926 (PS 705) is a secondary
lighting permutation. Event 1915 binds the G-buffer, SSAO, clouds, environment cube,
overlay, shroud, cascaded shadow map, and baked shadow map.

Captured frame constants are:

```text
sun direction = ( 0.752204835, -0.368124515, 0.546509087 )
sun colour    = (4744.829102, 4335.678711, 3330.588623)

ambient LR0 = (0.757388592, 0.619574547, 0.428393602)
ambient LR1 = (0.589906037, 0.479111701, 0.287942886)
ambient TB0 = (0.746249497, 1.065410614, 1.176159620)
ambient TB1 = (0.051749278, 0.068555206, 0.074733950)
ambient FB0 = (0.670795798, 0.542214215, 0.412173957)
ambient FB1 = (0.670795798, 0.826110303, 1.176159620)
HDR enabled = 1
```

The bound environment is resource 3932: a 256x256, six-face, nine-mip
R11G11B10_FLOAT cubemap. Its exact captured pixels were exported locally. It has no
writer in the captured frame and a generic runtime name, so its source weather/sky
resource provenance is unknown. Provenance is unnecessary for a frozen-frame port;
the cubemap itself is authoritative.

The exact captured lighting shader performs these material-relevant operations:

```text
D = RT1.rgb * RT1.rgb
N = normalize(2*RT0.rgb - 1)
S = RT0.a
R = RT1.a
F = RT2.rgb

environment mip = (1-S) * 8
distribution smoothness = 0.02 + 0.9799*S*S
HDR diffuse scale = 0.004
HDR environment scale = 360
```

It keeps `F` (RGB specular) and `R` (scalar reflectivity) independent, uses exponent
60 in its view/light reflectivity term, applies a 2.5 scale within the environment
specular path, and attenuates diffuse energy as reflectivity rises. The environment
is sampled by reflected world-space view direction. The six ambient colours are
selected by the normal signs and blended using squared normalized normal components;
the shader scales the Y component by four before this ambient weighting.

These details are exact captured DXBC behaviour. In particular, the captured
environment LOD multiplier is **8**, not the multiplier 3 found in an earlier
unbound shipped permutation and not the squared `(1-S)^2*5` preview formula.

### Shadows and SSAO

The frame binds a 4096x4096 R32 cascaded shadow resource with split depths
16/51/141/341 and a 2048x2048 R16 baked-shadow resource. Exact matrices and bias
are retained in `target-events.json`; the comparison sample bias is 0.1.

SSAO resource 3696 is a 1x1 B8G8R8A8 texture whose captured value is
`(255,255,255,255)`. It is neutral in this frame. SSAO therefore does not explain
the unit's strong material separation. Clouds/shadows modulate direct illumination,
but a standalone renderer can initially replace terrain/baked shadowing while still
porting the recovered material response exactly.

## Selected weather status

All installed environment resources were inspected. The likely family remains:

```text
weather/rome_med/su/land/day/dry/day_dry_01.environment ... day_dry_05.environment
```

No individual XML exactly equals all captured constants and HDR bounds. The engine
may interpolate weather/time state, but the capture alone does not name that process
or source member. Selecting one by screenshot similarity would violate the evidence
boundary. Therefore the weather filename is **UNKNOWN**, while the bound sun,
ambient cube, HDR environment cube, and frozen tone state are exactly recovered.

## Exact HDR and display chain

The unit is first lit into resource 3850 (R11G11B10_FLOAT). The observed chain is:

| Event | PS | Operation/output |
|---:|---:|---|
| 2177 | 2580 | HDR downsample to 128x128 RGBA16F |
| 2215 | 2581 | RGB to CIE LogYxy/statistics |
| 2228 | 2582 | log-luminance statistics |
| 2239-2274 | 2583 | 32 to 1 reduction chain |
| 2288 | 2584 | determine/adapt black and white points |
| 2302 | 2585 | bloom threshold/downsample |
| 2316 | 2589 | bloom filter pass |
| 2328 | 2590 | bloom filter pass |
| 2341 | 2591 | CIE/S-curve tone map plus bloom to R11G11B10_FLOAT |
| 2399 | 750 | HDR-to-screen to R8G8B8A8_UNORM backbuffer |

The exact frozen adapted-point texture (resource 4005, RGBA16F) is:

```text
log black = -3.0
black     = 0.0009994507
log white = 1.1630859375
white     = 15.5625
```

The environment/static limits captured by the adaptation passes include absolute
black -3, minimum log white 0.90309 (`log10(8)`), absolute log white 1.20412
(`log10(16)`), adaptation speed 0.02, and captured delta time 0.766998. The adapted
texture is per-frame/temporal; freezing its four captured values is the correct
deterministic first prototype.

Event 2341 converts RGB to XYZ/Yxy, clamps luminance to captured white, adds bloom,
floors luminance at 0.011, maps `log10(Y)` between captured black/white, samples the
captured 256x1 R16 S-curve LUT (resource 4028), and reconstructs RGB while preserving
chromaticity. Vignette is disabled. Both the S-curve data and bloom input are
available in the capture.

Event 2399 then applies negligible distortion, god rays at 0.1, no fog-of-war blend,
brightness 1.2, saturation clamp, gamma exponent 0.5, and a diagonal colour matrix
`(0.964706, 0.996078, 1.0)`. The backbuffer is R8G8B8A8_UNORM, not an sRGB target.

## Required subset for standalone unit sprites

| Component | Classification | Reason |
|---|---|---|
| AG normal decode and tangent basis | REQUIRED | large form/highlight effect |
| authored linear diffuse | REQUIRED | bronze and cloth foundation |
| RGB authored specular | REQUIRED | chromatic metal response |
| gloss R smoothness, sampled sRGB | REQUIRED | highlight width and cube mip |
| gloss G reflectivity, sampled sRGB | REQUIRED | independent reflection strength |
| captured faction colour preparation | REQUIRED | correct dark-red tunic |
| directional-light equation/constants | REQUIRED | captured warm key response |
| six-colour ambient cube | REQUIRED | coloured form separation in shadow |
| captured HDR environment cubemap | REQUIRED | bronze/environment reflections |
| frozen LogYxy/S-curve/display chain | REQUIRED | intensity without grey clipping |
| helmet dirt path | REQUIRED for helmet | authored local material variation |
| dynamic auto-exposure | OPTIONAL | freeze captured adapted values |
| self/cast shadow | OPTIONAL but useful | form grounding; not core material decode |
| neutral captured SSAO | UNNECESSARY | exactly white in this frame |
| terrain/baked shadow | UNNECESSARY | standalone transparent unit |
| cloud overlay | OPTIONAL / small | direct-light modulation only |
| bloom | OPTIONAL / small | port after base parity if visible |
| shroud/fog/god rays/vignette | UNNECESSARY | presentation/environment effects |

## Recovery classification

| Component | Status | Capture-derived reason |
|---|---|---|
| helmet draw/material | EXACTLY RECOVERED | event 1418, geometry and texture identity |
| cuirass draw/material | EXACTLY RECOVERED | event 1247, geometry and texture identity |
| tunic draws/material | EXACTLY RECOVERED | events 1596/1602/1609/1615 |
| `Weighted`/`WeightedDirtmap` shaders | EXACTLY RECOVERED | bound DXBC/reflection/disassembly |
| source texture bindings and formats | EXACTLY RECOVERED | captured SRVs and exports |
| normal decode; unused R/B | EXACTLY RECOVERED | bound pixel-shader dataflow |
| diffuse sampling/storage | EXACTLY RECOVERED | shader and G-buffer formats |
| RGB specular | EXACTLY RECOVERED | shader, t1, RT2 |
| smoothness | EXACTLY RECOVERED | sRGB gloss R to RT0.A |
| reflectivity | EXACTLY RECOVERED | sRGB gloss G to RT1.A; vertex controls zero |
| faction mask equation | EXACTLY RECOVERED | tunic shader |
| faction colours/preparation | EXACTLY RECOVERED | captured cbuffer matches sRGB^2.2 |
| helmet dirt equation | EXACTLY RECOVERED | `WeightedDirtmap` disassembly |
| G-buffer layout/formats | EXACTLY RECOVERED | bound targets and lighting decode |
| target lighting shader | EXACTLY RECOVERED | event 1915 bound DXBC |
| material/environment samplers | EXACTLY RECOVERED | captured sampler descriptors |
| sun and six ambient colours | EXACTLY RECOVERED | captured constant buffers |
| environment cubemap pixels/mips | EXACTLY RECOVERED | bound/exported resource 3932 |
| environment cubemap provenance | UNKNOWN | generic persistent runtime resource |
| environment LOD/equation | EXACTLY RECOVERED | captured lighting DXBC |
| cascaded shadow state | EXACTLY RECOVERED | resources, splits, matrices, bias |
| equivalent standalone self-shadow | HIGH-CONFIDENCE EQUIVALENT | must be regenerated for offline pose |
| SSAO | EXACTLY RECOVERED | neutral 1x1 white input |
| selected weather XML identity | UNKNOWN | captured values do not identify one member |
| HDR target and pass chain | EXACTLY RECOVERED | event/resource trace |
| tone-map equation and S-curve | EXACTLY RECOVERED | DXBC plus captured LUT |
| frozen runtime exposure values | EXACTLY RECOVERED | resource 4005 raw half floats |
| dynamic exposure history | PARTIALLY RECOVERED | algorithm/constants known, prior frames absent |
| bloom chain | EXACTLY RECOVERED | bound shaders/resources; contribution not isolated |
| final gamma/display transform | EXACTLY RECOVERED | event 2399 DXBC/constants/target |

## Current Blender mismatch

| Rome II runtime | Current Blender path | Visual consequence | Required fix |
|---|---|---|---|
| normal X=A, Y=G, reconstruct Z | older path uses `R*A` and green inversion | incorrect surface directions/highlights | implement AG decode in the converted tangent basis |
| authored diffuse retained for bronze | semantic bronze/conductor tuning can replace or strongly reshape it | loses texture-authored bronze foundation | keep sampled authored diffuse through G-buffer prep |
| RGB specular remains RGB | often reduced to luminance/Principled scalar | weak/desaturated warm reflection | preserve three-channel specular through lighting |
| smoothness=decoded gloss R | semantic roughness or `1-gloss^2` | wrong highlight size | sample gloss through sRGB view; use runtime S directly |
| reflectivity=decoded gloss G | folded into roughness/metallic/specular | wrong energy and dark-to-light range | carry an independent scalar channel |
| no special conductor branch | Principled metallic/conductor classification | material model differs before lighting | port common CA deferred equation |
| faction colours are DB sRGB^2.2 | prototype uses preview dark-colour adjustment | tunic hue/value is altered twice | use captured linear cbuffer values |
| directional + six-colour ambient cube | area lights/procedural world | flattened or studio-like form | use captured directional/cube equation/constants |
| captured HDR cubemap, mip `(1-S)*8` | procedural reflections/roughness blur | missing warm bronze reflections | sample captured cube with runtime LOD |
| LogYxy + captured S-curve/exposure | Standard view transform plus exposure 0.65 | grey/milky cast or clipping | apply exact frozen HDR chain after linear shading |
| gamma 0.5 and final colour matrix | Blender display transform | final chroma/value mismatch | reproduce event 2399 output transform explicitly |

P5 remains a preserved control and was not changed by this investigation.

## Minimum implementation and host decision

The smallest faithful implementation is **Blender for assembly, skinning, pose,
camera, and deterministic raster/AOV generation, followed by an offline custom
shading/compositing stage**. That stage should:

1. rasterize/export UVs, tangent basis, world position/depth, material ID, and alpha;
2. run the exact captured material preparation into floating G-buffer equivalents;
3. run the event-1915 directional/ambient/environment equations with captured
   constants and cubemap;
4. initially generate only deterministic self-shadowing and omit neutral SSAO,
   terrain shadow, fog, shroud, and cloud presentation;
5. apply the frozen event-2341 S-curve and event-2399 display conversion;
6. output transparent high-resolution RGBA before any AoE finishing.

This host preserves the working effective-unit, animation, and 16-camera pipeline
while avoiding an approximate Principled translation. Ordinary Blender material
nodes are not the preferred host because they cannot express the captured deferred
BRDF and tone chain exactly. A 3ds Max HLSL path adds a new assembly/animation host;
an Asset Editor helper still needs deterministic input assembly and capture API work.
Both are larger changes for the now-known equations.

No runtime-parity image prototype was made in this milestone. Implementing it inside
the existing Principled renderer would reintroduce approximation; the appropriate
next proof is one facet-03 custom-shaded high-resolution frame using the captured
resources and constants.

## Precise remaining unknowns and next experiment

No additional capture is required to begin the material-response prototype. The two
capture unknowns are not material blockers:

- selected weather XML/procedural sky provenance: use the exact captured cube and
  constants for the frozen reference;
- prior-frame exposure history: use the exact adapted 1x1 value for determinism.

For full-frame pixel parity, the smallest later experiment is a two-frame capture of
the same paused camera with resource history enabled, plus a RenderDoc pixel-history
probe on one helmet highlight and one shadow pixel. That would isolate the bloom,
cloud, shadow, and temporal-exposure contributions. It is not necessary for the
first exact material-response port.
