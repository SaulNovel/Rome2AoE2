# Selected-unit dependency resolution

The dependency stage promotes supported catalog infantry from `PARTIAL` only
after its authoritative dependency closure validates. It does not render, write
SLD, modify AoE DAT, or install a mod.

```powershell
python -B -m rome2aoe2 inspect Rom_Principes --faction rom_rome --dependencies
python -B -m rome2aoe2 extract Rom_Principes --faction rom_rome
```

The resolver starts with the catalog root VMD, recursively follows every VMD
alternative, preserves slot order/probability/socket provenance, and plans RMV2,
decal-array, skeleton, and animation-fragment dependencies. Extraction uses the
existing `rome2aoe2-pack` helper and requests individual canonical pack paths.
It never unpacks a whole pack.

Extracted assets live in the shared, versioned cache
`build/cache/rome2aoe2/assets-v1/<canonical-pack-path>`. Consequently identical
weapons, shields, skeletons, definitions, and textures are reused across units.
Validated unit plans are derived cache records under
`build/cache/rome2aoe2/validated-units-v1`; they are not authoritative roster
input and can be deleted/rebuilt.

RMV2 inspection supplies material class, texture, and skeleton evidence without
Blender. Required files, supported runtime material classes, skeleton identity,
and attachment sockets are checked before READY promotion. Rome II's absent
`test_mask.dds` and `test_black.dds` material sentinels are recorded explicitly
as shader defaults, not misreported as authored missing textures.

`extract` persists the validated dependency plan and a stable manifest using
source-default component choices. Catalog loading may use that validation record
to promote the indexed unit to READY; the source catalog remains unchanged.
