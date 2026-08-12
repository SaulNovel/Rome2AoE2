# Rome II DecalDirtmap capture replay

## Verdict

For the shield state present in frame 46753 the precise status is:

```text
base/dirt material preparation: VALIDATED
StandardLighting1915 route:     VALIDATED
decal-array equations:          RECOVERED
nonzero decal-array overlay:    NOT NUMERICALLY EXERCISED
```

The exact prominent foreground shield draw is event 1099, instance 0. It uses VS
resource 1084 and PS resource 1086, with 2,082 indexed elements and 448 unique
PostVS vertices. Its indexed NDC bounds are approximately
`(-.6348,-.6344)..(-.3669,.1030)`, which place it on the large foreground scutum.
The material payload is `roman_early_scutum_lod1`; every authored top mip was
matched byte-for-byte to its captured binding rather than inferred from index count.

An event-1093 instance is spatially attached to the previously replayed central
body, but its shield is subsequently occluded. It was therefore unsuitable for the
deferred-light validation population.

## Shader and resources

PS 1086 is the captured `DecalDirtmap` permutation. Relevant bindings are:

| slot | shader name | resource | view |
|---:|---|---:|---|
| t0 | `s_diffuse_map` | 5767 | sRGB |
| t1 | `s_dissolve_map` | 3710 | linear; disabled |
| t2 | `s_specular_colour_map` | 5769 | sRGB |
| t3 | `s_gloss_map` | 5771 | sRGB |
| t4 | `s_colour_mask_map` | 5192 | linear |
| t5 | `s_normal_map` | 5190 | linear |
| t6 | `s_decal_mask` | 7495 | linear |
| t7 | `s_decal_dirt_mask` | 7925 | linear |
| t8 | `s_decal_dirt_map` | 5148 | linear |
| t9 | `s_fire_map` | 5056 | linear; weather branch disabled |
| t10 | `t_decal_diffuse_array` | 7603 | sRGB |
| t11 | `t_decal_normal_array` | 7606 | linear |

All active samplers are captured linear min/mag/mip filters with mip bias zero.
The replay uses perspective-correct interpolation, derivative-selected mip levels,
and trilinear filtering. Per-vertex tangent handedness is retained.

Captured constants for this draw include:

```text
g_weather_type          = 0
g_dissolve_enable       = 0
g_untextured            = 0
g_uv2_tile_interval     = (1,1)
g_decal_uv_rect_coords  = (.537956834,.083942451,.933669150,.863280594)
faction_colours[0..2]   = 0
decal array slice       = PostVS TEXCOORD6.x = 0
dirt offset             = PostVS TEXCOORD6.yz
instance boost/desat    = PostVS TEXCOORD7.yz = (0,0)
```

The captured slice-zero decal diffuse alpha is zero over the visible replayed
shield. Consequently the array-overlay branch is exactly inactive in this frame.
The branch equations below are recovered from PS 1086, but a nonzero array decal
is not claimed as numerically exercised by this capture.

## Material equations

The base normal uses the validated AG decode:

```text
tx = 2*(normal.a + .5/255) - 1
ty = 2*(normal.g + .5/255) - 1
tz = sqrt(max(0,1-tx*tx-ty*ty))
```

For base UV `uv`, the optional decal coordinates and alpha are:

```text
duv = (uv - rect.xy) / (rect.zw - rect.xy)
a   = decalDiffuse.a * decalMask.a
```

Inside the rectangle PS 1086 applies:

```text
R  = R - .5*R*a
F  = F + a*(decalDiffuse.rgb*decalMask.a - F)
D  = (1-a)*D + decalDiffuse.rgb*decalMask.a
Nt = Nt + a*(decalNormalDecoded - Nt)
```

The dirt coordinates and operations are:

```text
dirtUV     = uv*g_uv2_tile_interval + perInstanceOffset
dirtAmount = dirt.a*dirtMask.a
D          = lerp(D,(.03,.025,.02),dirtAmount)
Nt.xy     += (2*dirt.rg-1)*dirtMask.a
F         *= 1-.99*dirtAmount
```

The world normal is the normalized `Nt.x*T + Nt.y*B + Nt.z*N` result. With the
captured neutral weather and per-instance controls, the G-buffer is the standard
layout:

```text
RT0.rgb = max-component encoded world normal
RT0.a   = gloss.r
RT1.rgb = sqrt(saturate(D))
RT1.a   = gloss.g                 # decal alpha is zero in this state
RT2.rgb = F
RT2.a   = 0
```

Thus DecalDirtmap routes to the already validated event-1915 standard deferred
lighting family, not event 1926 or another specialized pass. Event 1915 has blending
disabled; the isolated contribution is `after-before` from its HDR target.

## Numeric replay

The selected draw rasterized 87,484 pixels. Cumulative maximum error across all
three four-channel UNORM targets was:

| threshold | population |
|---:|---:|
| exact | 78 |
| <= 1 code | 3,018 |
| <= 2 codes | 4,830 |
| <= 3 codes | 5,883 |
| <= 4 codes | 6,537 |
| <= 8 codes | 7,597 |

There are 3,402 interior `<=2`-code pixels that survive later G-buffer writes and
receive a nonzero event-1915 contribution. Representative probes and all decoded
intermediates are recorded in ignored
`decal-dirtmap-capture-replay/report.json`.

The standalone event-1915 result, before its captured spatial shadow factor, has a
maximum selected midtone/bright relative difference of 34.15%; that maximum is a
low-HDR midtone where an approximately `.03` absolute residual dominates the ratio.
At the already recovered direct-light shadow multiplication point, the meaningful
HDR residual for captured channels >= `.25` is 1.81%. The maximum selected final
display absolute difference is 0.02562. No material, light, environment, or display
constant was tuned for the shield.

## Integration limitation

The deterministic offline shield uses the recovered UV scale one and a generic
zero dirt offset. The capture proves the per-instance offset exists, but it has not
yet been mapped to deterministic offline instance variation. The active captured
decal alpha is zero, so no invented shield-specific decal selection is introduced.
