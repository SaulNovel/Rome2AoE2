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
as intended.

## Highest-detail glTF proof of concept

`rpfm_extensions::gltf::gltf_from_rigid` and
`rpfm_extensions::gltf::save_gltf_to_disk` are public, reusable APIs. The
project helper uses them directly; no exporter code is copied from RPFM. The
upstream exporter normally emits one glTF scene per decoded LOD, so
`rome2aoe2-pack` clones the decoded model and passes a one-LOD filtered copy to
the exporter. The original decoded model remains unchanged.

```powershell
rome2aoe2-pack export-rmv2-gltf \
  --input build\local-integration\rome2\variantmeshes\_variantmodels\man\helmets\3c_niederbieber_helmet.rigid_model_v2 \
  --output build\local-integration\rome2\rmv2\praetorian-helmet.gltf \
  --lod highest
```

`highest` deterministically selects decoded LOD index 0. This is supported by
RPFM's `RigidModel` documentation, which orders `lods` highest-to-lowest
quality. An explicit non-negative LOD index is also accepted and bounds checked.
The command requires a `.gltf` output path, creates its parent directory, and
returns deterministic JSON containing file names rather than absolute paths.

The exporter writes textual glTF with base64-embedded buffers. The Praetorian
helmet proof of concept produced only
`build/local-integration/rome2/rmv2/praetorian-helmet.gltf` (180,183 bytes):
no `.bin`, image, or other sidecar files were written. Texture lookup is not
attempted because the exporter receives an empty RPFM dependency cache.

### Blender validation

Blender 5.2.0 LTS imported the exported highest-detail helmet successfully in
background mode. The import created one object and one mesh, with 1,037
vertices, 2,462 edges, and 1,446 triangular polygons—the same triangle and
vertex counts reported by the helper. It has two UV layers (`UVMap` and
`UVMap.001`), custom/split normals, one placeholder material slot
(`Material_0`), identity world orientation, scale `[1, 1, 1]`, and world-space
dimensions approximately `[0.291992, 0.309692, 0.324219]`.

The exporter declares a tangent attribute, but Blender did not retain a named
tangent attribute after import; tangents should be generated by Blender when
needed. The exported helmet has no armature and no vertex groups after import.
Although the glTF contains joint/weight attributes, the upstream exporter does
not construct a glTF skin or skeleton, so those attributes are not usable for
skinned-body or animation work. Material identity is also not preserved as the
RPFM material name in Blender (`Material_0`); textures are deliberately absent.
No geometric corruption or missing helmet geometry was observed in the
non-interactive import validation.

The next RMV2 milestone should assess whether the upstream exporter can be
extended or wrapped to preserve usable skins, joint hierarchies, material names,
and tangents for skinned body and cloak assets. It must remain separate from
texture/decal resolution and animation import.
