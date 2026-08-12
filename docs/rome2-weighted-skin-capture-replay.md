# Rome II `WeightedSkinDirtmap` capture replay

## Verdict

**WeightedSkinDirtmap: VALIDATED.**

Captured indexed material draws and the specialized deferred skin-light pass were
replayed numerically. No material, light, environment, tone, faction, camera, or
pose value was fitted. The generic runtime-parity renderer now routes this material
preparation family to the event-1926 skin lighting family rather than the
event-1915 standard lighting family.

## Draw and shader attribution

| Component | Material | Event | Instance | Indices / unique vertices | PS |
|---|---|---:|---:|---:|---:|
| body | `roman_body1` runtime body variant | 1474 | 6 | 9714 / 1977 | 2253 |
| head | `roman_1_head` | 1483 | 6 | 4134 / 730 | 2251 |

PS 2253 is alpha-tested; PS 2251 is the otherwise equivalent opaque permutation.
Indexed PostVS bounds and aligned instance positions identify the same soldier.
Resource 5661 matches the authored `roman_body_2_diffuse.dds` BC payload and 5665
matches `roman_heads_1_diffuse.dds`; this is captured runtime texture variation.

## Material resources and G-buffer

| Slot | Binding | Body | Head | View |
|---:|---|---:|---:|---|
| t0 | `s_diffuse_map` | 5661 | 5665 | BC1 sRGB |
| t1 | `s_normal_map` | 5118 | 5124 | BC3 linear |
| t2 | `s_gloss_map` | 5663 | 5667 | BC1 sRGB |
| t3 | `s_decal_dirt_mask` | 5122 | 6569 | BC3 linear |
| t4 | `s_decal_dirt_map` | 6565 | 6565 | BC3 linear |
| t5 | `s_skin_mask_map` | 5120 | 6567 | BC3 linear |

The material sampler is linear min/mag/mip with wrap addressing. Captured
`g_uv2_tile_interval.xy=(4,4)` and the offset is a no-interpolation per-instance
PostVS value.

```text
dirtUV = uv*4 + instanceOffset
baseTx = 2*(normal.a + .5/255) - 1
baseTy = 2*(normal.g + .5/255) - 1
tz = sqrt(max(0, 1-baseTx^2-baseTy^2))
tx = baseTx + (2*dirt.r-1)*dirtMask.a
ty = baseTy + (2*dirt.g-1)*dirtMask.a
dirtAmount = dirt.a*dirtMask.a
D = lerp(diffuse, (.03,.025,.02), dirtAmount)
```

The selected instances have zero generic brighten/desaturate controls.

```text
RT0.rgb = max-component encoded world normal
RT0.a   = sRGB-decoded gloss.r                 # smoothness
RT1.rgb = D                                    # linear; no sqrt
RT1.a   = sRGB-decoded gloss.g                 # reflectivity
RT2     = (skinMask.r, skinMask.g,
           skinMask.b, skinMask.b)
```

Derivative-driven captured mip selection was the cause of the initially small
matching population. Replaying captured mip levels with perspective-correct UV
derivatives and trilinear LOD increased the within-two-code population:

| Component | Rasterized | Initial <=2 | Corrected <=2 | Exact all targets |
|---|---:|---:|---:|---:|
| body | 4459 | 4 | 174 | 5 |
| head | 1341 | 1 | 562 | 19 |

No threshold or shader value changed.

## Event 1926 state and resources

Event 1926 is a fullscreen triangle-strip draw with VS 698 and PS 705. It writes
resource 3850 (`R11G11B10_FLOAT`). Blending is disabled, so it replaces selected
HDR pixels; before/after subtraction is not the blend equation. Stencil is enabled
with reference 3, compare mask 3, no writes, and the captured comparison selects
the skin-marked pixels. Depth testing is disabled.

| Slot | Resource | Meaning |
|---:|---:|---|
| t0 | 3838 | RT0 normal/smoothness |
| t1 | 3841 | RT1 linear diffuse/reflectivity |
| t2 | 3844 | RT2 skin mask |
| t3 | 3830 | resolved D24 depth |
| t4 | 3696 | neutral white SSAO |
| t5 | 3787 | 4096² cascaded R32 shadow |
| t6 | 3817 | 2048² baked R16 shadow |

There is no environment cubemap, skin LUT, noise texture, or other skin lookup.
The pass uses the captured camera/inverse-view-projection, sun, six-colour ambient
cube, cascade/baked-shadow constants, HDR scale, and refraction-depth alpha state.

## Skin-mask semantics and exact lighting dataflow

Let `K=RT2.rgb`, `D=RT1.rgb`, `R=RT1.a`, `S=RT0.a`,
`N=normalize(2*RT0.rgb-1)`, `L=-sunDirection`, and `V` point surface-to-camera.

- `K.r`: strength of the grazing ambient reflection/scatter lobe.
- `K.g`: blends ordinary `NdotL` into the three-channel wrapped-skin curve and
  attenuates the backscatter sun colour by `(0.3,1,1)`.
- `K.b`: strength of the view/light-aligned backscatter term.
- `K.a`: duplicates B in the G-buffer and is not sampled by PS 705.

Direct diffuse constructs a three-channel wrapped curve:

```text
n = dot(N,L)
w = saturate(n*(.8,.9,.3) + (.3,.5,.3)) * (.694444,.694444,.444444)
warm = w.g*(.612066,.456263,.05)
remain = saturate(1-(n*w.r+.3))
curve = remain*warm
scatter = w.b*(.32,.05,.006)*(1-n*w.r)
curve = scatter*(1-remain*warm) + curve + n*w.r
skinNdotL = saturate(lerp(n,curve,K.g))
directDiffuse = .9 * D * skinNdotL * sunColour * .004
```

The backscatter-like term is:

```text
back = saturate(dot(N,sunDirection))^2
     * saturate(dot(-V,L))^4 * K.b
backSun = sunColour * (1-K.g*(.3,1,1))
backscatter = .9 * D * back * backSun * .004
```

Smoothness and reflectivity remain independent. Skin has a fixed achromatic direct
specular response rather than RT2-authored RGB specular:

```text
exponent = 1.6 + 127*S^2
sunReflection = normalize(sunDirection + 2*N*n)
directSpecular = 2 * sunColour * .004
               * max(0,dot(sunReflection,V))^exponent * R
```

The same six-colour ambient cube is used twice. Diffuse ambient is
`D*ambientCube(N)*360*.0024`. A second grazing lobe samples the cube directionally
using the reflected view direction, weighted by `(1-dot(N,V))^2*K.r*1.5` and an
upward-lifted-normal factor. There is no environment texture term and no mip
equation.

SSAO multiplies the two ambient terms. The recovered cascade/baked shadow factor
multiplies `directDiffuse + backscatter + directSpecular`. No cloud texture is
bound in this permutation. The selected validation probes are effectively unshadowed;
assuming one leaves a maximum meaningful HDR residual below 7%, with the exact
shadow position still explicit.

## Numeric validation

There are 205 interior, stencil-selected head lighting candidates whose material
G-buffer agrees within two codes and survives to event 1926. Selected probes are:

| Probe | Pixel | G-buffer RT0/RT1/RT2 error | Captured HDR | Offline HDR |
|---|---:|---:|---|---|
| dark | 853,461 | 2/1/0 | (.011353,.004272,.001801) | (.011369,.004284,.001818) |
| midtone | 856,455 | 1/0/0 | (.472656,.087891,.028320) | (.484134,.088728,.028334) |
| bright | 857,450 | 1/1/1 | (4.250000,1.546875,.578125) | (4.542155,1.644839,.613490) |

Maximum meaningful midtone/bright HDR component-relative error is **6.8743%**.
This is below the 9% accepted for the standard pass and is bounded by the captured
shadow path plus R11G11B10 quantization.

The existing frozen tone/display chain produces:

| Probe | Captured display | Offline display |
|---|---|---|
| midtone | (.321569,.141176,.082353) | (.326050,.144122,.081763) |
| bright | (.752941,.470588,.286275) | (.771051,.479085,.293739) |

Maximum meaningful display-channel absolute error is **0.020327**. The dark probe
is excluded from the meaningful display bound for the same low-HDR/background
reason as the `Weighted` validation.

## Integration

The runtime renderer now separates material preparation from deferred-light family:

```text
Weighted / WeightedDirtmap -> event-1915 standard lighting
WeightedSkinDirtmap        -> event-1926 skin lighting
```

Dispatch is by manifest material family, not component name. `roman_body1` and
`roman_1_head` therefore use the validated path automatically. The standalone
facet render keeps the captured UV scale 4 and uses a generic zero dirt-instance
offset until deterministic instance-offset generation is formalized.

Ignored evidence and results remain under
`build/local-integration/rome2/runtime-shader-recovery/` and
`build/local-integration/rome2/runtime-parity-proof/`.
