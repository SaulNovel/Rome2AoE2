# Rome II skin production-integration audit

## Verdict

```text
INTEGRATION BUG FOUND
WeightedSkinDirtmap skinMask was incorrectly dirt-attenuated in the production
specular AOV. RT2 must contain the untouched skinMask.xyzz payload.
```

The correction is structural and limited to the AOV routing condition. No material
equation, event-1926 lighting equation, scene, camera, environment, or display
constant changed.

## Routing

Both visible legs are exposed `roman_body1` geometry from
`variantmeshes/_variantmodels/man/skin/roman_skin1_shape1.rigid_model_v2`. They are
not leggings, clothing, or a different material accidentally classified as skin.

| component | material | family | source model | diffuse | normal | gloss | skin mask | dirt mask | dirt map | visible diagnostic pixels |
|---|---|---|---|---|---|---|---|---|---|---:|
| body, arms, hands, exposed legs/feet | `roman_body1` | WeightedSkinDirtmap | `roman_skin1_shape1.rigid_model_v2` | `roman_body_2_diffuse.dds` | `roman_body_1_normal.dds` | `roman_body_1_gloss_map.dds` | `roman_body_mask.dds` | `roman_body_decaldirtmask.dds` | `default_decaldirtmap.dds` | 19,745 |
| head/neck | `roman_1_head` | WeightedSkinDirtmap | `roman_skin1_shape1.rigid_model_v2` | `roman_heads_1_diffuse.dds` | `roman_heads_1_normal.dds` | `roman_heads_gloss_map.dds` | `roman_heads_mask.dds` | `roman_heads_decaldirtmask.dds` | `default_decaldirtmap.dds` | 2,189 |

The production family AOV contains 23,371 skin-lighting pixels including filtered
edge coverage. `debug-skin-family-routing.png` distinguishes body in red and head
in cyan.

## The integration error

The validated skin material writes:

```text
RT0 = (encoded world N, smoothness)
RT1 = (linear D, reflectivity)
RT2 = skinMask.xyzz
```

Production already passed `D` directly into SkinLighting1926. It did not square or
square-root skin diffuse and therefore did not confuse the Weighted and skin RT1
layouts.

The error was in the shared `specular` AOV builder. It selected the skin mask for a
skin material, then incorrectly applied the standard-material dirt operation:

```text
skinMask *= 1 - .99*dirtAmount
```

That operation belongs to authored standard RGB specular `F`; it is absent from
the captured skin shader. The builder now applies it only when `skin_mask is None`.

## Pixel traces

All coordinates refer to the 3200x3200 frozen facet-03 output. Complete UV,
sampler, G-buffer, lighting, LogYxy, and display data are in ignored
`skin-integration-audit/report.json`.

| probe | pixel | linear source D after dirt | required mask | old mask | raw NdotL | before display | corrected display |
|---|---|---|---|---|---:|---|---|
| strongly grey/blue leg | 1554,1454 | (.545,.366,.274) | (.819,1,0) | (.632,.771,0) | -.450 | (.353,.396,.416) | (.455,.443,.439) |
| darker grey leg | 1705,1566 | (.404,.176,.082) | (.522,.882,0) | (.452,.762,0) | -.282 | (.071,.051,.039) | (.278,.090,.039) |
| warm leg/arm | 1534,1457 | (.401,.162,.114) | (.471,.642,0) | (.452,.616,0) | +.295 | (.631,.439,.357) | (.635,.439,.361) |
| warm arm/hand | 1714,1314 | (.597,.242,.109) | (.260,.320,0) | (.257,.316,0) | +.849 | (.957,.600,.361) | (.957,.600,.361) |

For the strongly grey pixel, corrected reconstructed contributions are:

```text
ambient diffuse          (.317,.261,.275)
grazing ambient scatter  (.512,.619,.848)
wrapped direct diffuse   (.475,.140,.009)
backscatter              (0,0,0)
direct specular          (1.370,1.252,.962)
exact production HDR     (1.352,1.197,1.167)
LogYxy input Y           1.228 (from the exact production HDR)
final display            (.455,.442,.438), before 8-bit quantization
```

The source is already warm. The old first divergence occurs at material output
RT2, before SkinLighting1926. After correction this probe remains relatively neutral
because direct sun is behind the normal (`NdotL=-.450`) while its grazing ambient
scatter is blue-heavy. That remaining effect is produced by the frozen scene
orientation and validated skin lighting.

## Sampling and colour space

The deterministic texture top-mip payloads were matched byte-for-byte to captured
resources 5661/5118/5663/5122/6565/5120. The production views are:

```text
diffuse:   sRGB sampled, one decode to linear
gloss:     sRGB sampled, one decode to linear values
normal:    linear; AG channels used
skin mask: linear
dirt mask: linear
dirt map:  linear
AOV view:  Raw, exposure 0, gamma 1
```

Explicit Rome-style trilinear sampling used evaluated-triangle UV derivatives, not
screen-neighbour derivatives across UV seams. Across the selected probes, maximum
absolute per-resource differences ranged from .071 to .168. The largest outlier is
a thin/high-derivative leg triangle and is concentrated in diffuse/dirt-mask
filtering; normal/gloss differences are much smaller. Both Blender and explicit
samples remain warm at the grey probes. Sampling differences therefore do not
create the blue cast, although exact Rome derivative filtering remains preferable
for future production raster infrastructure.

## Dirt-offset test

Seven legitimate offsets from body/head events 1474/1483 were evaluated without
selection:

```text
(.2797,.1778) (.6585,.3570) (.1350,.1481) (.8636,.6047)
(.4799,.7002) (.2100,.7738) (.1772,.8325)
```

Across the four probes, changing from zero to those offsets produced a maximum
linear-D channel delta of .08354 and maximum luminance delta of .05469. It moves
local dirt/value and normal detail but does not turn the warm authored diffuse into
a systematic blue-grey material. The dirt-offset branch is therefore closed as the
cause of the observed cast.

## Diagnostic outputs

Ignored local outputs:

```text
build/local-integration/rome2/runtime-parity-proof/
  debug-skin-family-routing.png
  skin-light-contribution-sheet.png
  skin-mask-fix-before-after.png
  runtime-parity-f03-pre-skin-mask-fix.png
  runtime-parity-f03.png
  skin-integration-audit/report.json
```
