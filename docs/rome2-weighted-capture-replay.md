# Rome II `Weighted` capture replay validation

## Verdict

**Weighted: VALIDATED.**

Event 1247 (`italian_square_muscled_cuirass_`) was replayed from captured indexed
PostVS output rather than Blender geometry. The replay uses the captured diffuse,
RGB specular, AG normal, gloss, HDR cube, light constants, tone LUT, and display
constants without artistic adjustment.

The earlier basis probe's instance 11 selection was invalid: it treated 4,200
indices as sequential vertices and read beyond the 858 unique PostVS vertices.
Index-aware selection identifies instance 3 as the central visible cuirass.

## Raster and G-buffer result

The selected draw contains 4,200 indices and 858 unique PostVS vertices. Offline
rasterization covered 8,877 pixels. Sixty-four interior pixels match all three
captured event-1247 G-buffer targets within two UNORM codes; 37 of those pixels
remain unchanged through the final material pass and can be followed into deferred
lighting.

Representative comparisons are:

| Probe | Pixel | RT0 max code error | RT1 | RT2 |
|---|---:|---:|---:|---:|
| dark | 947,503 | 1 | 1 | 0 |
| midtone | 1036,521 | 1 | 2 | 2 |
| bright | 1033,507 | 1 | 2 | 1 |

This validates capture-space raster interpolation, AG normal preparation, authored
linear diffuse, RGB specular, sRGB-view gloss sampling, smoothness, reflectivity,
max-component normal encoding, square-root diffuse storage, and G-buffer channel
order for `Weighted`.

## Lighting and display result

Event 1915 is additively blended, so its exact contribution was recovered by
subtracting resource 3850 immediately before the draw from the post-draw target.

| Probe | Offline HDR | Captured event-1915 contribution |
|---|---|---|
| dark | (0.002607, 0.001938, 0.001829) | (0.000694, 0.000557, 0.000202) |
| midtone | (1.831317, 0.914257, 0.400733) | (1.703125, 0.867188, 0.390625) |
| bright | (17.984324, 8.218095, 3.323292) | (16.500000, 7.625000, 3.125000) |

For the meaningful midtone and bright probes, maximum component-relative HDR error
is 8.996%. Exact cascaded/baked shadow and cloud modulation are not replayed, which
accounts for a bounded difference in direct illumination. The very dark probe is
dominated by these omitted terms and low-value target quantization.

After the frozen tone/display chain, the corresponding comparisons are:

| Probe | Offline display RGB | Captured display RGB |
|---|---|---|
| dark | (0.05082, 0.04525, 0.04413) | (0.04314, 0.04706, 0.04706) |
| midtone | (0.53823, 0.39266, 0.26099) | (0.52549, 0.38431, 0.25882) |
| bright | (0.96471, 0.84583, 0.53999) | (0.96471, 0.82353, 0.52941) |

Maximum midtone/bright display-channel absolute error is 0.02231. Event 2341 bloom
and event 2399 god rays/background are not reproduced by the standalone unit path.

## First divergences and corrections

1. The first attempted replay used the invalid sequential-vertex instance choice.
   Correct indexed PostVS traversal fixed geometry selection globally.
2. The event-1915 output initially appeared unrelated because the selected pixels
   had been overwritten by later G-buffer draws. Comparing the event-1247 and final
   G-buffers isolates only surviving cuirass pixels.
3. The final target is `R8G8B8A8_UNORM`; interpreting its raw bytes as BGRA swapped
   red and blue. Direct RGBA interpretation produces the display agreement above.
4. Remaining bounded HDR differences first occur in unreplayed shadow/cloud
   modulation, not in `Weighted` material preparation.

No light, material, faction, gloss, reflectivity, environment, exposure, or tone
values were changed.

## Next shader-family status

No additional family was implemented during this milestone.

1. `WeightedSkinDirtmap`: next priority for `roman_body1` and `roman_1_head`.
   Recover its exact captured material PS, bindings, skin mask, dirt path, and
   G-buffer outputs before implementation.
2. `DecalDirtmap`: recover the shield draw and its decal/dirt channel semantics.
3. Relevant `DefaultMaterial` permutations: recover the feather, sword, and pilum
   draws independently; do not route them through `Weighted`.

Ignored evidence and results are under:

```text
build/local-integration/rome2/runtime-shader-recovery/
  capture-analysis/frame46753/weighted-replay/
  weighted-capture-replay/report.json
```
