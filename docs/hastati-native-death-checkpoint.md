# Approved Hastati native death checkpoint

This checkpoint freezes the death installed and visually approved in Age of
Empires II: Definitive Edition for Hastati unit 2081. It extends the approved
idle/walk/attack checkpoint without changing idle graphic 17068, walk graphic
17069, or attack graphic 17070.

## Authoritative animation route

1. Use the Asset Editor export of `sws_cr_death_missile_004.anim`.
2. Import the animated glTF with Blender's standard glTF importer and reuse its
   native Action and Action slot unchanged.
3. Preserve the native horizontal and vertical fall motion. Do not create or
   animate `Rome2AoE2_LocomotionCenter` for death.
4. Rotate only `Rome2AoE2_FacetRoot` to render the 16 AoE directions.
5. Render main and shadow only, then author paired x1 and x2/UHD SLDs.
6. Package death graphic 17071 and map both dying/death states of unit 2081 to
   it. Keep the corpse unit inherited from Militia (unit 152).

## Frozen production values

- Clip: `sws_cr_death_missile_004.anim`.
- Samples: 33 native samples at 15 FPS.
- Frame duration: `1 / 15 = 0.0666667` seconds.
- Native Action: unchanged.
- Motion: native horizontal and vertical fall preserved; no
  `LocomotionCenter`.
- Facets: 16.
- Zooms: x1 and x2/UHD.
- Layers: main and shadow only.
- Graphic: 17071.
- Unit mapping: unit 2081 dying/death to graphic 17071.
- Corpse unit: inherited from Militia, unit 152.
- Runtime metadata: sequence type 11, mirroring mode 6, layer 20, replay delay
  0, and speed multiplier 0.
- Existing mappings unchanged: idle 17068, walk 17069, attack 17070.

## Production workflow

```powershell
powershell -ExecutionPolicy Bypass -File scripts/render_hastati_native_death.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_hastati_native_death_test.ps1
powershell -ExecutionPolicy Bypass -File scripts/build_and_install_hastati_native_death_test.ps1
```

The installer requires both death zoom assets and targets the stable
`Rome2AoE2 Hastati Dev Test` mod and scenario locations.
