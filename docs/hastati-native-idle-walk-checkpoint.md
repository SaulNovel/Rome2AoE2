# Approved Hastati native idle/walk checkpoint

This checkpoint freezes the in-game-approved Hastati idle and
`sws_walk_162_cm` walk. The installed reference is the stable
`Rome2AoE2 Hastati Dev Test` mod for unit 2081.

## Authoritative animation route

1. Export the Rome II `.anim` and `rome_man_game.anim` through Asset Editor's
   native `RmvToGltfExporter`.
2. Import the animated glTF with Blender's standard glTF importer.
3. Reuse the imported Action and Action slot unchanged.
4. Animate only `Rome2AoE2_LocomotionCenter` to cancel horizontal locomotion;
   preserve vertical motion and every joint channel.
5. Rotate `Rome2AoE2_FacetRoot` under the fixed production camera, light, and
   environment for the 16 AoE facets.
6. Render separate main and shadow frames, downsample independently to x1 and
   x2, and encode native SLD with DirectXTex.
7. Add a separate walk graphic to the stable Hastati DAT clone without
   changing the approved idle graphic.

`src/blender/import_animation_clip.py` and
`src/blender/apply_hastati_animation.py` are research-only matrix
reconstruction paths and are not production dependencies.

## Frozen production values

- Walk: 23 native samples, 1.10-second cycle, 16 facets.
- Camera: fixed azimuth/elevation; orthographic scale `7.27480212108078`;
  target Z `0.8503072261810303`.
- Facets: fixed camera/light/environment, complete unit rotated through
  `Rome2AoE2_FacetRoot` using the shared AoE facet mapping.
- Equipment: shield `bn_weapon_03`, gladius `bn_weapon_02`, pilum
  `bn_weapon_05`; RMV2 rigid pivots remain inside their rigid children.
- Crest: generalized geometry-contact solver on `bn_head`.
- Colour: accepted Rome II runtime material preparation with the dark-red
  early-scutum slot mapping; no player-colour SLD layer.
- SLD: main + shadow only, x1 200×200 and x2 400×400, hotspot 100/122 and
  200/244 respectively.

## Reproduction commands

Given the Asset Editor animated glTF and approved assembled/materialized blend:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/render_hastati_native_walk.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_hastati_native_walk_test.ps1
powershell -ExecutionPolicy Bypass -File scripts/install_hastati_test.ps1 `
  -GeneratedMod "build/dev-test/hastati/Rome2AoE2 Hastati Dev Test" `
  -GeneratedScenario "build/dev-test/hastati/Rome2AoE2HastatiDevTest.aoe2scenario"
```

The native walk clips 124, 197, 251, and 302 remain source candidates for
future speed matching but are not selected by this checkpoint.
