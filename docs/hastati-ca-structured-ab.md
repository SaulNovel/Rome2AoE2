# Hastati CA-structured material A/B

This is a single high-resolution structural test. It does not include AoE finishing,
downsampling, SLD encoding, scale changes, or a parameter sweep.

## Fixed control

- runtime-resolved standard Hastati representative
- facet 03 (112.5 degrees)
- camera `(112.5, 30, 8.5, 12)`
- 3200 x 3200 transparent master
- P5 A9 lighting and P5 B7 material tuning
- unchanged textures, geometry, composition, and pose

## Prototype change

The prototype keeps authored bronze diffuse and combines it with a separate RGB
specular lobe. Gloss-map R controls smoothness (`roughness = 1 - R`) while gloss-map
G controls reflectivity/specular strength independently. It also applies the
luminance-dependent faction-colour adjustment found in Creative Assembly's installed
shader and uses Blender's bounded, colour-preserving Khronos PBR Neutral display
transform. The control remains on P5's Standard transform.

## Display-referred semantic metrics

Metrics use the rendered semantic material masks, Rec.709 luma in sRGB display space,
mean HSV saturation, and saturation-weighted circular HSV hue.

| Region | Render | L10 | L50 | L90 | L95 | Saturation | Hue |
|---|---|---:|---:|---:|---:|---:|---:|
| bronze | P5 | 0.212 | 0.256 | 0.389 | 0.448 | 0.246 | 18.4 degrees |
| bronze | structured | 0.015 | 0.189 | 0.312 | 0.357 | 0.787 | 31.8 degrees |
| cloth | P5 | 0.311 | 0.442 | 0.770 | 0.996 | 0.383 | 6.2 degrees |
| cloth | structured | 0.232 | 0.404 | 0.731 | 0.876 | 0.517 | 7.0 degrees |

Runtime screenshot metrics are intentionally omitted: there is no exact material mask
for the crowded battlefield image, so thresholded scene statistics would not be
comparable to the renderer's semantic masks.

## Conclusion

The structural interpretation materially improves bronze identity and bronze/cloth
separation relative to P5. The helmet gains a dark foundation, gold hue, and compact
highlights instead of P5's soft grey-brown response. The bounded display transform also
reduces cloth highlight clipping and the faction adjustment retains more red chroma.

It does **not** yet close the overall runtime gap. The prototype bronze is too dark and
too orange/saturated, particularly on the cuirass, while the runtime cuirass is smoother,
broader in its midtones, and more restrained. The tunic is also brighter/pinker than the
runtime's dark red. This points to missing energy normalization and environment-response
calibration inside the new material structure, not to sharpening or sprite reduction.

Because the complete runtime match is not a clear improvement yet, no ablation set was
rendered. The next bounded test should retain this separation of diffuse, smoothness,
reflectivity, and RGB specular, but add CA-like specular/diffuse energy attenuation and
derive the environment term from an actual outdoor radiance source rather than tuning
final colours.
