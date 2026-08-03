# AoE2 DE native SLD authoring

## Selected route

The generated-PSD/DESpriteTool route is discontinued. DESpriteTool 4.20.1
accepts Adobe RGB16 documents with its required `Lr16` structures, but the
maintained Python PSD writers tested by the project do not emit that structure.
Those findings remain useful reference evidence, not a production dependency.

Rome2AoE2 now constructs native SLDX v4 files directly. The container and block
code adapts the minimum required parts of
`justinas-kazanavicius/aoe2-transparent-buildings` at commit
`bce7f2f795483ae1c91afb915cc014a520dc0a30`. The upstream copyright is
2026 Justinas Kazanavicius and its MIT notice is preserved in
`third_party/licenses/aoe2-transparent-buildings-MIT.txt`. No GUI or
building-shortening code was copied.

The project-owned boundary is:

```
calibrated main PNG + calibrated shadow PNG
    -> sld_authoring.py
    -> SLDFile / SLDFrame / SLDLayer
    -> strict serialization and parsing
    -> native _x1.sld
```

`sld.py` owns the strict SLDX v4 model, reader, and writer. `sld_blocks.py`
owns BC1/BC4 blocks and an injectable BC1 interface. `sld_authoring.py` owns
PNG loading, alpha classification, RGB bleed, trimming, block alignment,
skip/draw commands, and the deterministic manifest. `analyze_sld.py` performs
strict inspection and project-owned decoding.

## Alpha and compression

Alpha-test coverage uses one threshold everywhere: an 8-bit alpha value is
visible when it is at least 128. The previous upstream path included blocks at
`alpha > 0`, then treated their texels as opaque only above 127; an all-low-alpha
block became eight zero bytes, which BC1 decodes as opaque black. The adapter
omits such a block. If an explicit transparent block is needed it uses BC1
three-colour mode with all sixteen indices set to transparent index 3.

Before compression, visible RGB is propagated into below-threshold neighbours
for four deterministic 8-neighbour passes. Ties use row-major source order.
Alpha is never changed and the canonical PNG is never overwritten. This avoids
black colour endpoints at antialiased boundaries while limiting bleed to four
pixels around the sprite.

The basic adapted compressor remains a reproducible fallback. The selected
proof encoder is Microsoft DirectXTex `texconv` 2026.5.8.1 (May 2026 release,
SHA-256 `DCFDEC10244E02CF5037FBA089C55FB7E1326B1C8181742D77D15FA5CB5EEF06`),
invoked as BC1_UNORM with one mip and alpha threshold `128/255`. On the calibrated
direction-zero image both encoders preserve the thresholded silhouette exactly:

| encoder | opaque RGB PSNR | false opaque | false transparent | dark fringe |
|---|---:|---:|---:|---:|
| fixed basic | 28.48 dB | 0 | 0 | 0 |
| DirectXTex | 30.25 dB | 0 | 0 | 0 |

Both produce the same 39 main blocks and the same final file size because the
container structure is identical. DirectXTex is therefore selected; its DDS is
only a temporary compression transport and remains under ignored `build/`.

The shadow alpha is encoded directly as BC4. The real proof has source maximum
148 (about 0.58 opacity), decoded PSNR 60.74 dB, maximum absolute error 9, and
no inversion. Main and shadow bounds are independently thresholded, expanded
outward to the four-pixel grid, and clamped to the 200x200 canvas.

## Spatial and structural invariants

Trimming never recentres a layer. Pixel coordinates satisfy:

```
source_position - source_hotspot
  == stored_local_position + layer_offset - encoded_hotspot
```

The diagnostic is SLDX v4 with exactly one frame and one DAT facet, a 200x200
canvas, hotspot `(100,100)`, and main plus shadow layers only. Its layer mask is
`0x03`. The SLD header's `0x0010` field is a format marker, not facet count:
DESpriteTool emits it even for its one-frame template. Facet count exists in the
DAT graphic record and the deterministic authoring manifest. Player colour,
damage, normals, and height are intentionally absent.
The strict parser rejects invalid signatures and versions, inconsistent frame
or facet counts, invalid layer order/masks/bounds, mismatched command and block
counts, truncation, and trailing bytes. Supported data round-trips semantically;
the generated diagnostic also round-trips byte-for-byte.

## Diagnostic integration

The Python DAT adapter clones Militia 74 to reserved diagnostic unit 2081,
appends graphic 17068, and assigns both clone standing references to
`rome2aoe2_praetorian_sld_diagnostic`. The graphic declares one frame and one
facet. Original Militia fields are verified unchanged after the written DAT is
reloaded. The file is packaged as
`resources/_common/drs/graphics/rome2aoe2_praetorian_sld_diagnostic_x1.sld`.

The ignored scenario places units 74 and 2081 side by side. Because this is a
one-facet format proof, every facing intentionally displays direction zero.
Sixteen-facet direction ordering, player colour, complete clips, and release
or projectile events remain later milestones.

## Local outputs

Generated comparison data, decoded PNGs, native SLD, data mod, and scenario are
under `build/local-integration/sld-direct/`. Proprietary DAT and generated game
assets are excluded from Git.

## First runtime compatibility result

The first manual AoE2 DE test establishes partial native compatibility. With
Enhanced Graphics (UHD) disabled, the game loaded without a crash, original
Militia remained visible/selectable, and the project-generated SLD main layer
was visibly rendered. The Praetorian appeared dark grey and difficult to read;
numeric direction 0 was subsequently confirmed by the 16-direction sheet to be
a rear three-quarter view with the shield dominating the silhouette. The clone
could not be selected at the visible sprite location.

With UHD enabled the diagnostic was invisible because that initial mod supplied
only `_x1.sld`. This proves x1 discovery and native SLD runtime decoding, not
finished selection, colour fidelity, or visual quality. The milestone therefore
remains open.

DAT/scenario inspection ruled out ownership or disabled-unit causes:

| unit | owner | position | enabled | collision radius | selection radius | interaction |
|---|---:|---:|---:|---:|---:|---:|
| Militia 74 | player 1 | 10,10 (first probe) | yes | 0.2,0.2,2.0 | 0.2,0.2,2.0 | 4 |
| clone 2081 | player 1 | 14,10 | yes | 0.2,0.2,2.0 | 0.2,0.2,2.0 | 4 |

Selection effect and editor selection colour also match Militia (`0` and `0`).
The revised scenario puts Militia at 8,10 and clone 2081 at 14,10, with player-1
Scout Cavalry 448 at 14,12 as an obvious logical-position marker. All diagnostic
units belong to player 1. Layer coordinates preserve the hotspot invariant, so
the file predicts zero independent recentering; an actual screen-space offset
still requires measurement from the revised in-game screenshot.

## Runtime diagnostic set

The follow-up compatibility graphic contains 16 frames and the DAT declares 16
facets, but every frame deliberately duplicates numeric direction 0. Its proper
zoom assets are independently authored from retained render data:

- x1: 200x200, hotspot 100,100;
- x2: 400x400, hotspot 200,200, downsampled directly from the retained 800x800
  pass with the calibrated premultiplied-alpha bicubic filter.

The high-resolution shadow is constrained to the doubled calibrated x1 shadow
envelope to discard isolated one-byte Cycles noise; it is not sourced from an
upscaled compressed x1 layer.

A separate 16-facet RGB diagnostic uses a solid-alpha asymmetric 64x64 pattern
containing saturated red, green, blue, yellow, cyan, and magenta. It has no
shadow or player colour. Source, edge-bleed, DirectXTex, and project SLD-decoded
views are collected in `rgb-control-contact-sheet.png`. This awaits the next
manual game observation before engine RGB/sRGB interpretation is accepted.

The direction sheet establishes:

- numeric direction 0 / azimuth 45 degrees: rear three-quarter;
- directions 7--10: front or shield-forward, with substantial shield occlusion;
- direction 4 / azimuth 315 degrees: clearest front-three-quarter diagnostic;
- directions 14--15: rear-side transitions.

Direction 4 is packaged as a separate visual-quality control. A clearly named
debug-only version enlarges the same rendered pixels about the unchanged
hotspot to approximately 60 pixels tall. Neither changes materials, lighting,
the v2 profile, or canonical scene data.

For direction 4, source mean luminance is 51.89/255 and mean channel values are
R 57.07, G 50.91, B 46.37. DirectXTex changes luminance by only -0.59 and the
project-decoded SLD matches the DirectXTex decode exactly (29.64 dB versus the
source, zero silhouette errors). Thus serialization is not the cause of the
grey appearance. The source render itself is dark and low-saturation at this
scale, while the rear-facing first probe further reduced readability. Whether
the engine or map lighting adds another change remains gated on the RGB control
and a captured in-game crop.

## UHD runtime result and control correction

The revised scenario was tested with Enhanced Graphics enabled. AoE2 DE loaded
without crashing and reported population 6/0, confirming all six scenario
objects existed. Militia 74, Praetorian 2081, and marker 448 were visible.
Praetorian 2081 resolved its native 400x400 `_x2.sld`; main and shadow rendered
without obvious black blocks or alpha rectangles, and its logical scale was
broadly comparable to stock Militia. Together with the earlier non-UHD test,
this proves both direct native routes: x1 works without UHD and x2 works with
UHD.

RGB 2113, front-three-quarter 2114, and debug 2115 were invisible for a simple,
fully reconciled reason. Their DAT stems were correct and contained no zoom
suffix, but the installed mod contained only each `<stem>_x1.sld`. UHD therefore
requested nonexistent `<stem>_x2.sld` files. Their DAT records already declared
one frame per facet and sixteen facets correctly.

All three now have independently authored x2 counterparts:

- RGB: a native 400x400, hotspot 200,200 main-only reconstruction of the
  doubled vector-like control geometry—not renamed or block-upscaled x1 data;
- front three-quarter: direction 4 reduced directly from retained 800x800 main
  and shadow renders to 400x400;
- debug: direction 4 at approximately 120 raster pixels high on the x2 canvas,
  corresponding to the labeled 60-logical-pixel x1 control.

Every installed x1/x2 pair has 16 SLD frames, passes the strict parser with
exact byte consumption, and round-trips byte-for-byte. The installed audit,
including SHA-256 hashes, is stored under ignored output as
`build/local-integration/sld-runtime-diagnostic/installed-uhd-audit.json`.
The successful 2081 files were not changed as part of the control diagnosis.

## Native infrastructure acceptance versus visual acceptance

The UHD follow-up established that project-authored native SLDX v4 is a viable
production transport. The x2 Praetorian rendered without a crash, corrupt BC1
blocks, or alpha rectangles. The synthetic RGB/CMY control rendered with the
expected channel order and saturated colours. This accepts the direct writer,
BC1 interpretation, SLD serialization, x1/x2 filename convention, and native
colour transport independently of the unresolved art profile.

The current sprite itself is not visually accepted. Direction 0 is dark and
shield-dominated, the 45-pixel candidate loses detail, the 60-pixel diagnostic
is oversized beside Militia, the contact shadow is weak, repeated identical
facets look like a cardboard cutout, and no player-colour layer was present.

The next diagnostic therefore uses native x1/x2 pairs for four 45/50/54/60 px
scale controls, four source-rendered brightness/fill controls, two shaded BC4
player-colour mappings, three shadow controls, and one 16-facet asset populated
from four genuinely rendered views. The latter deliberately uses nearest-view
fills between the four measured facets; it is a calibration control, not a
claim of complete 16-direction authoring.

Player colour is encoded as the format's dependent BC4 layer on the main
layer's trimmed block grid. Zero blocks are skipped, while nonzero grayscale
coverage preserves lighting variation. The selected unit's ordinary faction
masks show a strong R channel on clothing/armour regions; G and B contribute
little in the inspected pose. The restrained proof uses only high-confidence R
coverage (cutoff 128), while the stronger proof includes low R coverage (cutoff
24). Skin, weapons, and unmasked metal remain outside both mappings.

Generated comparison assets, strict reports, and the scenario are kept below
`build/local-integration/sld-visual-calibration/`. The comparison DAT uses
diagnostic IDs 2701--2719; original Militia 74 remains unchanged. This stage
still requires the planned manual UHD/non-UHD comparison before candidate
values can replace v2.
