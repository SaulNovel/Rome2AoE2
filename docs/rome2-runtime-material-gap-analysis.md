# Rome II runtime material-gap analysis

Date: 2026-08-09

## Reference set and limits

Six 1920x1080 Steam JPEG screenshots from a dry daytime Rome II battle were
visually inspected against the preserved P5 master and the BR0-BR6 daylight
masters. The screenshots show multiple runtime-randomized Hastati rather than the
exact deterministic Blender representative, so they are authoritative for
material response, not pixel correspondence or exact texture marks.

The closest useful frames are `20260809202340_1.jpg` (many rear/3/4 cuirasses)
and `20260809202533_1.jpg` (close front/3/4 helmets, tunics, skin and shields).

Approximate HSV selections from soldier-heavy crops quantify the visible runtime
response but include some background/JPEG contamination:

| Frame | Region | L10 | L50 | L90 | L95 | median hue | mean HSV saturation | near-white |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 202340 | red-like | .105 | .272 | .369 | .392 | 7.6° | .704 | .02% |
| 202340 | bronze-like | .175 | .369 | .650 | .745 | 32.3° | .482 | 1.64% |
| 202533 | red-like | .080 | .116 | .330 | .380 | 7.3° | .635 | .29% |
| 202533 | bronze-like | .165 | .240 | .495 | .620 | 32.7° | .494 | .67% |

The important pattern is not absolute luminance: cloth remains dark and highly
saturated while bronze spans a much broader dark-to-bright warm range. In the
rear/3/4 frame bronze L90 is about .65 versus P5 decoded-x2's reported ~.48,
without widespread clipping.

## Proven shader-structure mismatch

The installed official `assembly_kit/max_exporter/max_shader/ca_shader.fx`
samples sRGB diffuse and RGB specular separately. Its updated lighting material
contains distinct `Diffuse_Colour`, `Specular_Colour`, `Smoothness`, and
`Reflectivity`. Lighting sums:

- directional diffuse;
- hemisphere/environment diffuse;
- directional RGB specular;
- environment-cubemap RGB specular.

The current Blender reconstruction instead classifies bronze as a conductor,
sets Principled Metallic to 1, and feeds the RGB specular map into Base Color.
That discards the authored bronze diffuse contribution. This is not equivalent to
the CA shader and explains the narrow/dark brown bronze body with insufficient
broad warm response.

For non-metals, RGB specular is reduced to scalar luminance for Principled's
`Specular IOR Level`; its color is lost. That makes cloth/skin response another
approximation, although less damaging than the bronze conductor conversion.

The CA shader also treats smoothness and reflectivity as independent inputs. The
current manifest/reconstruction exposes one `GlossMap` and maps it to
`roughness = 1 - gloss.r^2`, while the later P5/BR studies disconnect that map and
set constant roughness per semantic class. This removes within-material variation
and cannot reproduce the runtime's compact bright helmet spots over broad bronze
midtones.

## Faction colour

The current faction-tint path correctly linearizes the supplied faction colour
before applying it. The official shader does that too, so gamma conversion itself
is not the bug. However, when faction colouring is enabled, CA additionally calls
`get_adjusted_faction_colour`: dark faction colours receive a luminance-dependent
boost (approximately 1.5 at the darkest end, falling toward .5 for bright
colours). Our equation is only `lerp(D, D * linear(Ci), mask_i)` and omits this
adjustment.

That omission makes Rome's dark C0 red weaker before lighting. P5 compensates with
base multipliers, emission, and later chroma protection, but those do not recreate
the original diffuse behavior. The runtime screenshots show the desired result:
red remains dark, clean, and chromatic in both shadow and light, rather than
turning into either brown-black shadow or pink/white highlights.

## Tonemapping mismatch

The CA shader builds an HDR linear result, tone-maps luminance in CIE Log-Y/xy,
converts back while retaining chromaticity, then applies gamma. Its curve has
explicit black/white points and S-curve biases.

P5/BR currently render with Blender `Standard`, exposure +0.65, gamma 1, to an
8-bit PNG. `Standard` plus positive exposure is not chromaticity-preserving HDR
compression: the first RGB channel to approach the display limit loses relative
color. This contributes to pale/pink cloth highlights and weakly colored bright
metal response. It also explains why increasing light energy has repeatedly
failed to create Rome II's combination of intensity and retained color.

This is a source-render problem, not an SLD or palette problem.

## Lighting/environment mismatch

P5 A9 is a studio rig: neutral world, sun, three large white area lights, and a
warm rim. Rome II uses a directional light plus hemisphere/environment diffuse
and a sampled environment cubemap in the specular term. Large Blender area lights
produce broad white reflection bands; the runtime instead shows view-dependent,
warm environment response and compact highlights embedded in a broad warm bronze
body.

R2DAY changed light direction and the world gradient, but it retained the
Principled metallic conversion, constant semantic roughness, incomplete
reflectivity model, and Blender Standard transform. It therefore tested a new rig
on top of the wrong response model. Its failure does not establish that daylight
is unimportant; it establishes that lighting alone cannot repair the shader.

## Reduction/downsampling

Reduction remains a secondary loss stage. Narrow red/bronze features mix with
skin, leather, shadow, and alpha during 3200-to-400 reduction. P5's previous
measurements already show meaningful chroma loss before BC1 and little extra loss
from BC1 itself.

However, the Blender masters are visibly missing the runtime separation before
reduction. A different resampler cannot create absent broad bronze energy or
restore RGB specular color. After shader parity improves, reduction should be
retested with material masks and premultiplied alpha, but it is not the next lever.

## Attribution

| Cause | Confidence | Relative importance | Evidence |
|---|---|---:|---|
| Shader/material interpretation | Very high | Primary | CA separate diffuse/spec/smoothness/reflectivity versus current metallic Principled collapse |
| Spec/gloss/environment handling | Very high | Primary subset | RGB spec reduced/discarded; gloss overridden; no equivalent environment-specular term |
| Tonemapping/color management | High | Secondary | CA chromaticity-preserving CIE HDR curve versus Standard +0.65 |
| Lighting rig | High | Secondary | Studio softboxes versus sun + hemisphere + cubemap; R2DAY retained wrong shader |
| Faction-colour adjustment | High | Important for cloth | Official dark-colour boost omitted |
| Downsample policy | High | Amplifier only | Loss exists after master, but master is already wrong |

## Smallest next experiment

Do not run another parameter sweep. Build one structural A/B render at the same
pose, facet 03, scale, textures, and daylight:

1. frozen P5 source control;
2. a CA-structured material prototype that preserves diffuse and adds RGB
   directional/environment specular separately, retains map-driven smoothness,
   implements the official faction-colour adjustment, and applies a bounded
   chromaticity-preserving tone curve.

Render only the high-resolution master first. Do not add AoE finishing or SLD.
If that one prototype moves bronze and cloth materially toward the runtime
screenshots, then isolate contributions with at most four ablations: material
structure, faction adjustment, tonemap, and environment specular. If it does not,
stop and reassess texture-channel/reflectivity extraction rather than tuning
lights.
