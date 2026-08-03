# AoE2 DE infantry render calibration

## Scope and status

This milestone establishes a reproducible **candidate** render profile for an
in-game comparison. It does not claim to recover Forgotten Empires' production
scene. The versioned profile is
`config/render_profiles/aoe2_de_infantry_v1.json`; all reference extraction,
sweeps, PNGs, and reports remain below ignored `build/local-integration/`.

## Community and tool evidence

| Source | Availability / version | Useful evidence | Limits |
|---|---|---|---|
| Protomace, *Isometric rendering setup for Blender* | Downloadable CC0 `.blend`, 2017 | AoE2-inspired orthographic scene and a simple light | Uses the removed Blender Internal engine; no DE measurements, canvas, anchor, or team-color pipeline. Starting evidence only. |
| Croomfolk, *Blender Sprite Studio* | Downloadable Blender 3.6 scene | Orthographic true-isometric and 2:1 dimetric cameras, Cycles, compositor edge-AA controls, shadow catcher | General sprite production, not AoE2; its page does not establish AoE-compatible scale, light, or anchors. Not copied. |
| AoE2 DE `Tools_Builds` | Locally installed AGE 2025.4.23, DESpriteTool, ArtDesk, and licensed AGE/genieutils source archive | Official unit authoring settings specify `FacetCount: 16`, bicubic downsampling, player-color palette, outlines, and distinct unit PSD layers (`Blood`, AO, Diffuse, Decal, Background, Height, Normals). AGE can inspect DE angles and SMX. | DESpriteTool is an encoder, not an SLD extractor; settings do not disclose the production camera or lights. |
| openage | Open source; current repository and September 2022 development report | DE changed its default loose graphics from SMX to SLD; openage/SLX Studio collaborators reverse-engineered main, shadow, and player-color layers. | Several SLD fields/layers remained unknown in the published report; it is graphics-format evidence, not render-scene evidence. |
| SLX Studio community workflow | Tool/binaries are available from the AoE modding community | Loads/exports SMX and assembles PNG/BMP frames into an SMX accepted by DE. Community guidance confirms the 3D-to-PNG-to-SMX workflow. | No authoritative public camera/light preset was found. Current stock DE files are SLD, so SMX support is mainly useful for the next custom-graphics milestone. |
| Alan Cortez AoE2 DE visual-mod guide | Published guide with SLD Extractor, SLX Studio, and AGE workflow | Confirms loose SLD location and that extracted frames carry anchors which must be preserved on reassembly. | Workflow guide, not production camera documentation. |

No external `.blend` or other third-party asset was copied into this repository.

## Original DE reference measurements

The locally installed standard-resolution (`_x1`) idle SLDs were parsed without
copying them. The measurement script used the SLDX frame/layer metadata and
decoded BC1 main alpha and BC4 shadow alpha so the boxes below are nonzero-pixel
bounds, not merely allocation rectangles. Byte consumption matched every file.
The full deterministic record is
`build/local-integration/aoe2-reference/infantry-idle-measurements.json`.

| Reference idle | Canvas | Hotspot | Stored frames | Facets | Main bounds at stored frame 0 | Main W/H across sampled facets | Shadow bounds at frame 0 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Militia | 200×200 | 100,100 | 481 | 16 | `[91,64,109,104]` | W 15–26, H 38–41 | `[78,64,113,106]` |
| Man-at-Arms | 200×200 | 100,100 | 481 | 16 | `[91,61,115,103]` | W 21–25, H 38–51 | `[82,59,116,106]` |
| Long Swordsman | 200×200 | 100,100 | 960 | 16 | `[93,65,128,103]` | W 16–35, H 38–51 | `[83,64,128,106]` |
| Champion | 200×200 | 100,100 | 960 | 16 | `[91,58,109,103]` | W 14–24, H 45–60 | `[78,57,111,106]` |
| Legionary | 100×100 | 50,50 | 721 | 16 | `[39,14,63,54]` | W 23–26, H 39–44 | `[30,13,64,56]` |

Every sampled frame has separate main, shadow, normals, and player-color layers.
Thus team color is an authored mask/layer, not a diffuse hue to guess in Blender.
The source SLDs contain 16 independently stored facets. This pipeline's first
output policy intentionally emits eight directions for the existing AoE2
scenario path; it samples every other 22.5-degree source orientation and does
not mirror opposite directions. The candidate order is south, southwest, west,
northwest, north, northeast, east, southeast. Its exact in-game semantic offset
still needs the next SMX/in-game check.

The 481/721-frame files retain a final stored endpoint after complete facet
groups; it was not discarded during measurement. The stock SLD canvas is not
universal, as the Legionary counterexample demonstrates.

## Camera and scale hypothesis

The profile uses an orthographic camera with azimuth 45°, elevation 30°, and
orthographic scale 8.5. Elevation is a measured candidate, not an asserted
production value. A deterministic 3×3 sweep covered elevations 25/30/35° and
scales 7.5/8.0/8.5. Direction-zero heights were:

| Elevation | scale 7.5 | scale 8.0 | scale 8.5 |
|---:|---:|---:|---:|
| 25° | 52 px | 49 px | 46 px |
| 30° | 50 px | 47 px | **45 px** |
| 35° | 48 px | 46 px | 43 px |

The chosen 45 px result sits within the measured 38–60 px stock-infantry range
and matches the Legionary's 39–44 px closely. The sweep and images are under
`build/local-integration/aoe2-render-calibration/sweep/`; its numerical summary
is `sweep-summary.json`. Foreshortening remains a silhouette hypothesis until
the textured unit and an in-game side-by-side comparison are available.

## Anchor and canvas policy

World origin is the deterministic ground/feet point. It projects to (100,100)
on the fixed 200×200 calibration canvas. The eight final renders project it
within 0.00006 px of that point; visible bottoms are y=102–105, matching the
reference bottoms around y=103–106. Transparent margins are stable and are not
cropped per frame. Future full-action rendering must compute maximum bounds
over the animation/direction group and may select a different stable canvas,
but must keep the same anchor rather than recenter each frame.

## Lighting, shadows, and color

The first hypothesis is a Sun at azimuth 135°, elevation 70°, strength 3.0,
12° angular size, with 0.35 neutral world fill. It was selected to reproduce the
short, soft reference extent rather than the first rejected 50° hypothesis,
whose shadow was far too long. Cycles 32 samples renders deterministic separate
RGBA color and shadow-catcher PNGs. Across the final eight directions the color
bounds are 18–24 px wide and 44–46 px high; shadow boxes are 23–31 px wide and
12–17 px high. The light intensity, contrast, and shadow opacity remain low
confidence because the proof uses neutral/missing Rome II materials.

Blender 5.2 LTS uses Cycles, transparent film, PNG RGBA8 straight alpha,
`Standard` view transform, no look, exposure 0, and gamma 1. Denoising and
viewport-dependent settings are disabled. A headless Blender 5.2 Eevee
(`BLENDER_EEVEE`) comparison produced the same `[91,58,112,103]` alpha bounds
and 45 px height, but does not provide the selected Cycles shadow-catcher path;
its first shader-compilation render also took about 12 seconds versus roughly
0.2 seconds per warmed Cycles proof render on this machine. Both engines remain
accepted for experiments, while Cycles is selected for the version-1 profile.

## Calibration harness

`src/blender/render_aoe2_calibration.py` loads an existing animation `.blend`,
maps the requested source sample to the Blender timeline, creates camera/light
state from the profile, renders one direction or all profile directions, and
emits deterministic filenames and a path-independent report. It records the
camera matrix, visible bounds, projected feet, unit height, and shadow bounds.
Pure parsing, direction, timeline, camera-position, bounds, filename, and JSON
helpers live in `src/blender/aoe2_render_profile.py` and are CTest-covered.

Final proof outputs:

- `build/local-integration/aoe2-render-calibration/one-direction-final/`
- `build/local-integration/aoe2-render-calibration/one-direction-final.report.json`
- `build/local-integration/aoe2-render-calibration/eight-directions-final/`
- `build/local-integration/aoe2-render-calibration/eight-directions-final.report.json`

## Remaining uncertainty and next check

The next milestone should encode the eight calibration frames into a temporary
SMX with the centered hotspot and compare a custom Praetorian beside original
Militia/Legionary in the diagnostic scenario. That check must settle the facet
semantic offset, apparent scale in game, alpha/shadow interpretation, and
whether DE expects eight custom facets or benefits from all 16. Rome II textures
and team-color masks should follow; lighting values must then be revalidated.

## Textured-unit final calibration (v2)

`config/render_profiles/aoe2_de_infantry_v2.json` supersedes v1 for future
rendering while retaining v1 as the historical provisional profile. Camera
geometry is unchanged: 45-degree base azimuth, 30-degree elevation, 8.5
orthographic scale, 200x200 canvas, and ground origin at (100,100). V2 supports
16 independent directions and retains `source_samples` as the default future
animation policy.

The controlled textured sweep is recorded beneath
`build/local-integration/aoe2-final-calibration/sweep/`. Its v1-like low
candidate measured mean/p10/p90 visible luminance 0.203/0.060/0.343. The
selected Standard candidate measured 0.250/0.072/0.431, improving midtone
separation without clipping metal highlights. AgX compressed tiny highlight
structures and produced a 0.052 p10. Khronos PBR Neutral reduced the mean to
0.151 and p10 to 0.017. Standard was selected for gameplay-scale readability,
not cinematic appearance.

Selected settings are a Sun at azimuth 135 degrees, elevation 60 degrees,
strength 2.6 and angular size 12 degrees; white world fill 0.65; Standard view
transform; no look; exposure +0.65; gamma 1; and straight-alpha RGBA8 PNG.
Cycles uses 48 samples without denoising.

Direct, 2x, and 4x rendering were compared. V2 renders internally at 800x800
and reduces to 200x200 with a project-owned premultiplied-alpha bicubic filter.
Direct output contained 241 fractional-alpha edge pixels, 2x bicubic 201, and
4x bicubic 183. Lanczos3 expanded the visible box from 20x44 to 23x48 and
created 319 fractional edge pixels, showing ringing around the crest and thin
weapons. Bicubic was selected; no final sharpening is applied. High-resolution
intermediates remain available locally.

Across all 16 stand directions, output height is 43-45 pixels and the projected
foot origin remains (100,100). Chainmail, cloth folds, and skin separate more
clearly than v1 without metallic glare or crushed cloth. Crest and tunic edges
remain clean. Sword visibility is direction-dependent but stable, and the
pilum remains a thin readable line in the representative throw pose.

The authored shield pattern remains in the canonical material. In the standing
pose the shield is mostly oblique, and the emblem is not reliably identifiable
after reduction. Lighting cannot restore a sub-pixel motif, so no material or
decal change was made. A later in-game facing check must establish whether a
more shield-forward animation provides enough projected area.

The shadow remains a separate black-alpha layer. V2 applies opacity 0.58 after
alpha-correct reduction. At the operational 0.02-alpha threshold, stand shadow
bounds remain attached to the foot region and rotate consistently with the
fixed key direction. Very-low-alpha resampling fringe is excluded from those
bounds.

Final proofs and deterministic reports are under
`build/local-integration/aoe2-final-calibration/final/`. They cover stand sample
0 in all 16 directions, stand sample 21, combat-ready sample 22, and pilum-throw
sample 30. No geometry, texture, material, rig, equipment transform, or source
animation sample was changed.

Team-color interpretation and layered SLD packaging remain future milestones.
The researched DESpriteTool/PSD bridge should consume this profile without
mutating the canonical scene or source samples.

## In-game visual candidate (v3)

`aoe2_de_infantry_v3_candidate.json` is an explicit diagnostic candidate; v2
remains the calibrated baseline. V3 preserves the 30-degree elevation, 8.5
orthographic scale, 200x200 canvas, material graph, and every source asset. It
tests exposure +0.95 (a +0.3 change from v2), world fill 0.85, broad shadow
opacity 0.68, and a five-pixel contact region capped at 0.78.

The controlled front-three-quarter source sweep measured:

| Candidate | Mean luminance | p10 | p50 | p90 | clipped highlights |
|---|---:|---:|---:|---:|---:|
| v2 | 51.86 | 10.00 | 40.49 | 105.00 | 0.33% |
| exposure +0.3 | 57.66 | 12.14 | 45.35 | 115.28 | 0.78% |
| exposure +0.6 | 63.88 | 14.41 | 50.78 | 127.00 | 1.44% |
| +0.3 and fill 0.85 | 64.89 | 15.00 | 51.91 | 129.83 | 1.01% |

This proves the dark result originates in the Blender source profile rather
than BC1 or native SLD colour transport. The fill candidate gives comparable
midtone recovery with less highlight clipping than exposure +0.6, so both are
retained for the game test. No saturation adjustment is proposed: saturation
slightly decreases as expected with exposure, and the RGB control already
proved native channel fidelity.

The enlarged labeled orientation sheet records the inspected numeric subset:
0/45 degrees rear three-quarter, 4/315 front three-quarter, 5/292.5 front,
and 8/225 shield-forward side. These names remain diagnostic until the
four-view in-game rotation row confirms the semantic mapping.

The provisional recommendation entering that test is 50 logical pixels,
exposure +0.3 plus fill 0.85, restrained R-channel player colour, shadow 0.68
with the contact enhancement, and the four numeric mappings above. None of
these values supersedes v2 until the comparison scenario is observed.
