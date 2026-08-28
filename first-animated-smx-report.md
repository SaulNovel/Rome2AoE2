# First animated SMX vertical slice

## Status

The offline pipeline is complete through generated SMX, DAT data mod, and
diagnostic scenario. AoE2 DE itself has **not** been run, so runtime success is
not claimed yet.

## Internal pipeline map

1. Asset Editor exports RMV2, skeleton, and `AnimationClip` data to glTF.
2. `import_animation_clip.py` imports the native clip, consolidates weighted
   meshes, resolves weapon sockets, and evaluates named RMV2 attachments using
   the runtime-derived formula committed at `c9b600b`.
3. The accepted complete textured Hastati scene supplies body, equipment,
   materials, armature, and the native action without changing transforms.
4. `render_animated_hastati_sprites.py` samples every integer action frame with
   the calibrated orthographic camera on a stable transparent canvas.
5. `validate_animated_sprite_frames.py` checks ordering/canvas/non-empty frames
   and creates contact sheets.
6. `smx_staging.py` writes deterministic indexed SLP staging frames.
7. The official AoE2 DE `DESpriteTool` converts SLP to SMP and compresses it to
   SMX. Project code validates the resulting SMPX header.
8. `generate_first_animated_smx_mod.py` clones Militia 74 to unit 2081, creates
   matching graphic metadata, packages the SMX, and generates the scenario.

## Source unit

- VMD: `variantmeshes/variantmeshdefinitions/roman_hastati.variantmeshdefinition`
- body: `roman_skin1_shape1.rigid_model_v2`
- skeleton: `animations/skeletons/rome_man_game.anim` (50 bones)
- tunic: `e3_tunic.rigid_model_v2`
- cuirass: `italian_square_muscled_cuirass_a.rigid_model_v2`
- helmet: `roman_montefortino.rigid_model_v2`
- crest: `black_feather_03.rigid_model_v2`, attached through `crest_centre`
- shield: `roman_early_scutum.rigid_model_v2`, `bn_weapon_03`
- gladius: `roman_gladius.rigid_model_v2`, `bn_weapon_02`
- pilum: `roman_pilum_light.rigid_model_v2`, `bn_weapon_05`

No component was removed for sprite generation. There is no asset-name-specific
or crest-specific correction in the new sprite/SMX code.

## Animation

- mapping: `Rom_Hastati -> rome_man_sword_shield -> STAND`
- clip: `animations/rome2/human/battle/sword_and_shield/stand/sws_stand.anim`
- header duration: 2.8 seconds
- exported last key: 2.7349140644 seconds
- Asset Editor action range: 0.0 to 65.637939453125 at 24 FPS
- source/action samples used: every integer frame 0 through 66 (67 frames)
- output sampling: 24 FPS; no arbitrary frame deletion or resampling
- output duration in DAT: 67 / 24 = 2.7916667 seconds
- looping: native STAND is used as a looping standing action; the first and
  rounded final integer samples are not pixel-identical. No artificial duplicate
  or visual loop correction was introduced.

The existing complete-animation attachment validation reports a maximum local
attachment error of `2.68e-7` and zero rigid-child local pivot drift.

## AoE2 directions

The Militia reference graphic has 16 facets, and stock DE SLD inspection showed
16 independently stored directions. The proof therefore renders all 16 and
does not use mirroring.

| facet | Blender yaw |
|---:|---:|
| 0 | 45.0° |
| 1 | 22.5° |
| 2 | 0.0° |
| 3 | 337.5° |
| 4 | 315.0° |
| 5 | 292.5° |
| 6 | 270.0° |
| 7 | 247.5° |
| 8 | 225.0° |
| 9 | 202.5° |
| 10 | 180.0° |
| 11 | 157.5° |
| 12 | 135.0° |
| 13 | 112.5° |
| 14 | 90.0° |
| 15 | 67.5° |

Ordering is clockwise in 22.5-degree steps. SMX storage is facet-major: 67
consecutive animation frames per facet, 1,072 frames total.

## Rendering

- output: 200x200 RGBA PNG
- complete proof: 1,072 frames, 2x internal render then premultiplied-alpha
  bicubic reduction
- one-direction edge validation: 67 frames at 4x internal render
- camera: orthographic, elevation 30°, scale 8.5, distance 12
- target/world origin: `(0,0,0)`
- fixed anchor/hotspot: `(100,100)`
- background: transparent
- view: Standard, exposure +0.65, gamma 1.0
- proof engine: Blender Eevee; the calibrated profile also supports Cycles
- origin strategy: fixed unit/world origin on one animation-wide canvas; no
  per-frame crop or recenter

All 16 directions contain 67 non-empty frames. Direction-wide alpha bounds stay
well inside the canvas. Visual contact-sheet inspection shows the crest seated
on the crown and continuous helmet, shield, gladius, and pilum placement.

Diagnostics (ignored build evidence):

- `build/local-integration/first-animated-smx/diagnostics/idle-direction-0-contact-sheet.png`
- `build/local-integration/first-animated-smx/all-direction-diagnostics/idle-all-directions-preview.png`
- `build/local-integration/first-animated-smx/all-direction-diagnostics/idle-direction-*-contact-sheet.png`

## SMX

- structural authority: official AoE2 DE `DESpriteTool` 4.20.1 and the locally
  installed licensed genieutils SMX reader source
- version/signature: `SMPX`, version 1
- stored frames: 1,072
- directions: 16 facets, 67 frames per facet
- frame dimensions before encoder trimming: 200x200
- hotspot: `(100,100)`
- compression: official interleaved SMX compression; 3,598 KiB to 1,515 KiB
- transparency: thresholded indexed main-layer transparency
- main palette: official `b_dark.pal` (1024-colour source, 256-colour SLP stage)
- present layers: main sprite
- intentionally deferred: player colour, shadow, and outline
- animation timing: DAT graphic metadata, not the SMX frame header

The repository's checked-in 13-byte `.smx` test stubs were not used as format
references. The resulting file is validated for signature, version, and exact
stored-frame count.

## DAT

- source/template unit: Militia 74
- custom unit: 2081, `Rome II Hastati`
- generated graphic: 17068, `rome2aoe2_hastati_idle`
- standing references 1 and 2: graphic 17068
- frame count: 67
- angle/facet count: 16
- frame duration: `1/24` seconds (`0.0416667`)
- Militia 74 is reloaded and verified unchanged

## Scenario

Generated scenario:

`build/local-integration/first-animated-smx/package/Rome2AoE2FirstAnimatedHastati.aoe2scenario`

Placements for Player 1:

- Militia 74 at `(8,10)`
- converted Hastati 2081 at `(12,10)`

Expected result: the Militia remains the vanilla comparison; unit 2081 displays
the generated Rome II Hastati and cycles the 67-frame standing animation.

## Validation

- complete one-direction render: 67/67 non-empty, visually inspected
- complete 16-direction render: 1,072/1,072 non-empty, previews inspected
- SMX header: `SMPX` v1, 1,072 frames
- focused animated-SMX regressions: 2 passed
- named-attachment regressions: 2 passed
- rigid-pivot regressions: 6 passed
- configured CTest suite: 16/16 passed (unsandboxed rerun was required because
  the managed sandbox denied temporary-directory writes)
- `git diff --check`: passed for the working tree

## Known remaining limitations

- No AoE2 DE runtime evidence exists yet.
- Minimal SMX omits player-colour, shadow, and outline layers.
- Only `_x1.smx` is packaged. Test with Enhanced Graphics/UHD disabled.
- The existing 2.8-second header versus 2.734914-second last-key discrepancy is
  preserved, not reinterpreted.
- The 16-facet semantic yaw offset still requires the in-game facing test.
