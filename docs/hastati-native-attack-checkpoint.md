# Approved Hastati native attack checkpoint

This checkpoint freezes the in-game-approved `sws_sync_atk_005` attack for
Hastati unit 2081. It extends the approved idle/walk dev-test package without
changing idle graphic 17068 or walk graphic 17069; attack graphic 17070 is the
new production mapping.

## Authoritative animation route

1. Export the Rome II `.anim` through Asset Editor's
   `AssetEditorAnimationRunner` and real `RmvToGltfExporter` route.
2. Import the resulting animated glTF with Blender's standard glTF importer.
3. Reuse the imported native Action and Action slot unchanged. Do not use the
   decoded-JSON/custom Action reconstruction path.
4. Assemble the approved production unit while preserving materials, scale,
   crest seating, and rigid equipment carriers/pivots.
5. Rotate only `Rome2AoE2_FacetRoot` under the fixed production camera, light,
   and environment to generate the 16 AoE facets.
6. Render separate main and shadow frames, downsample independently to x1 and
   x2/UHD, and encode native SLD with DirectXTex.
7. Package attack graphic 17070 and map unit 2081 to idle 17068, walk 17069,
   and attack 17070.

## Frozen production values

- Clip: `sws_sync_atk_005`.
- Samples: 27 native frames over a 1.30-second cycle.
- SLD frame duration: `1.3 / 27` seconds.
- Facets: 16, using the shared production facet ordering.
- Layers: main + shadow only; no player-colour layer.
- Zooms: x1 200x200 and x2/UHD 400x400.
- Hotspots: x1 100/122 and x2 200/244.
- Impact reference: native sample 10, approximately 0.50 seconds, aligned
  with the native maximum thrust. Existing working DAT combat timing remains
  inherited rather than rebalanced.

## Production workflow

Given the Asset Editor animated glTF and approved assembled/materialized blend:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/render_hastati_native_attack.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_hastati_native_attack_test.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_and_install_hastati_native_attack_test.ps1
```

The installer targets the stable `Rome2AoE2 Hastati Dev Test` mod and scenario
locations configured by `scripts/install_hastati_test.ps1`.
