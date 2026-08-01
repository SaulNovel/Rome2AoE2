# RMV2 investigation

## Rome II material compatibility overlay

The pinned RPFM revision at `fdde51aa9e6826afda1832d1b563b5f11125dc75`
recognises several Rome II RMV2 v6 material identifiers but did not dispatch
them to a binary reader or writer. This blocked normal decoder-based inspection
of otherwise valid Praetorian Guard models.

Rome2AoE2 keeps the RPFM submodule pinned to that upstream commit and carries a
small, explicit overlay at
`patches/rpfm/0001-support-rome2-default-layout-materials.patch`. The overlay
adds only these proven DefaultMaterial-compatible types:

| ID | RPFM name | Vertex format observed | Reader/writer |
| --- | --- | --- | --- |
| 72 | `DecalDirtmap` | static | `read_default` / `write_default` |
| 79 | `WeightedDirtmap` | weighted | `read_default` / `write_default` |
| 82 | `WeightedSkinDirtmap` | weighted | `read_default` / `write_default` |

`DecalDirtmap` is also routed through RPFM's existing static Dirtmap vertex
layout. The weighted formats already use the generic weighted vertex path.
There is intentionally no wildcard fallback: unsupported IDs still fail rather
than risking an incorrect cursor position. In particular, `WeightedSkin` (70)
and `Dirtmap` (73) remain unsupported pending independent format evidence.

### Evidence

For every inspected material block, a bounded parse using RPFM's
`DefaultMaterial` serialization consumed exactly the bytes from the material
header to the mesh vertex offset. The fixed header, attachment, texture, and
parameter sections remained aligned. The expanded local survey found this
layout in all 19 type-72 blocks from four shield samples, 15 type-79 blocks
from four model samples, and 16 type-82 blocks from two skin samples, in
addition to the Praetorian Guard parts. The observed types use the vertex
formats listed above.

The patch adds upstream-style synthetic tests for material and complete RMV2 v6
round-trips. They verify attachments, textures, string/float/integer/vector
parameters, vertex and index cursor alignment, and continued rejection of
unrelated types 70 and 73.

### Applying and verifying the overlay

The overlay is a developer/bootstrap step, not a normal pipeline action. It
intentionally makes `third_party/rpfm` dirty while remaining based on the
verified upstream commit.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\apply_rpfm_patches.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\verify_rpfm_patches.ps1
```

The apply script validates the exact submodule `HEAD`, detects already-applied
and incompatible states, and runs `git apply --check` before applying. The
verification script confirms both the expected patch content and that no
unmanaged RPFM edits are present. Re-run the apply command after restoring the
submodule or updating it to the documented base.

To return the submodule to its clean upstream checkout, first ensure that it
contains no work you intend to keep, then run:

```powershell
git -C third_party/rpfm restore .
```

This removes the managed overlay too; apply it again before building the helper.

## Metadata-only RMV2 inspection

After the overlay has been applied and `rome2aoe2-pack` has been rebuilt, use:

```powershell
rome2aoe2-pack inspect-rmv2 --input path\to\model.rigid_model_v2
rome2aoe2-pack inspect-rmv2 --input path\to\model.rigid_model_v2 --decode
```

The default command performs deterministic RMV2 v6 structural metadata
inspection. `--decode` additionally asks the patched `rpfm_lib` decoder to
validate the whole file. Neither mode exports geometry, resolves textures or
decals, or performs Blender work.

With the overlay applied, all ten extracted Praetorian Guard RMV2 models decode
successfully. A separate local control scan still rejects type 70 and type 73,
as intended. The next RMV2 milestone can therefore evaluate geometry export
only after deciding how to handle those remaining, independently unsupported
material layouts.
