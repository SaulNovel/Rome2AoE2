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

### Source material identity

The upstream exporter creates one glTF material per mesh but leaves its `name`
unset. Rome2AoE2 therefore performs a narrow post-processing pass over the
written glTF JSON; it does not copy or modify RPFM exporter code. The pass maps
each selected-Lod RMV2 mesh material to the corresponding glTF material,
assigning the source material name and adding deterministic metadata under
`extras.rome2aoe2`.

The metadata records the source material name and type, texture directory,
texture records (path and type only), attachment count, and all decoded
string/float/integer/vector shader parameters. It does not resolve, load, add,
or transform texture files. Buffers, accessors, meshes, and geometry are left
unchanged.

For the helmet, the glTF material is named `3c_niederbieber_helmet` and its
extras identify type `WeightedDirtmap`, texture directory
`variantmeshes/_variantmodels/man/helmets/tex/`, seven raw texture records, and
two float plus three integer parameters. Blender now imports its material slot
with the same source name instead of `Material_0`.

### Blender validation

Blender 5.2.0 LTS imported the exported highest-detail helmet successfully in
background mode. The import created one object and one mesh, with 1,037
vertices, 2,462 edges, and 1,446 triangular polygons—the same triangle and
vertex counts reported by the helper. It has two UV layers (`UVMap` and
`UVMap.001`), custom/split normals, one source-named material slot
(`3c_niederbieber_helmet`), identity world orientation, scale `[1, 1, 1]`, and world-space
dimensions approximately `[0.291992, 0.309692, 0.324219]`.

The exporter declares a tangent attribute, but Blender did not retain a named
tangent attribute after import; tangents should be generated by Blender when
needed. The exported helmet has no armature and no vertex groups after import.
Although the glTF contains joint/weight attributes, the upstream exporter does
not construct a glTF skin or skeleton, so those attributes are not usable for
skinned-body or animation work. The post-processing pass preserves source
material identity and metadata, but textures are deliberately absent.
No geometric corruption or missing helmet geometry was observed in the
non-interactive import validation.

The next RMV2 milestone should assess whether the upstream exporter can be
extended or wrapped to preserve usable skins, joint hierarchies, material names,
and tangents for skinned body and cloak assets. It must remain separate from
texture/decal resolution and animation import.

## Rome II skeleton inspection

The RMV2 `skeleton_id` value `rome_man_game` was resolved by enumerating the
installed game's pack contents. Its resources are in `data.pack` at:

- `animations/skeletons/rome_man_game.anim`
- `animations/skeletons/rome_man_game.bone_inv_trans_mats`

They can be inspected without copying game-derived data into the repository:

```powershell
rome2aoe2-pack inspect-skeleton `
  --anim path\to\rome_man_game.anim `
  --inverse-bind path\to\rome_man_game.bone_inv_trans_mats
```

The command emits deterministic `rome2aoe2.skeleton-inspection` version 1 JSON
and never includes its input paths. It supports only the verified Rome II
formats: skeleton `.anim` version 5 and inverse-bind version 1.

### Hierarchy and bone indices

The version-5 `.anim` header contains the skeleton identifier and serialized
bone count. It is followed by an ordered sequence of length-prefixed UTF-8 bone
names and signed 32-bit parent indices. Parent `-1` denotes a root; non-negative
values index the same ordered bone array. Empty and duplicate names, invalid
parents, and hierarchy cycles are rejected.

The inspected file has 50 bones and six roots: indices 0 through 5. They are
`bn_hips` and `bn_weapon_01` through `bn_weapon_05`. Bone 23 is `bn_head`.
RMV2 weighted vertex bone indices and material attachment `bone_id` values use
these same zero-based serialized array indices. Consequently attachment IDs
1--5 resolve to the five weapon bones and attachment ID 23 resolves to the head.

The `.anim` contains 2,412 bytes after the hierarchy. This is reported as
additional pose data, but remains deliberately opaque: its compact pose sample
encoding has not been established and this milestone does not decode it.

### Inverse bind matrices and convention

The version-1 `.bone_inv_trans_mats` file contains a version, a matrix count,
and exactly 48 bytes per matrix. Rome II stores each transform as a row-major
affine 4x3 using row vectors: three basis rows followed by a fourth translation
row. The inspector transposes this into a normalized row-major 4x4 JSON matrix
using column vectors (`p' = M * p`), translation in the fourth column, and
composition `world = parent_world * local`.

For each bone the normalized stored matrix is the inverse world-bind matrix.
The inspector calculates:

```text
world_bind = inverse(inverse_world_bind)
local_bind(root) = world_bind
local_bind(child) = inverse(parent_world_bind) * child_world_bind
```

Matrix inversion uses a singular-pivot tolerance of `1e-12`. Reconstruction
and composition checks use a relative/absolute scaled tolerance of `1e-8`.
Every source and derived value must be finite. When these matrices are later
written to a glTF `MAT4` accessor, their entries must be flattened column-major;
the mathematical convention itself already matches glTF.

### Real `rome_man_game` validation

The local resources decode as `.anim` version 5 and inverse-bind version 1 with
50 matching bones/matrices. The hierarchy is acyclic and all parents are valid.
All 50 inverse-bind matrices invert successfully, and all reconstructed world
and local bind matrices are finite. No unexpected hierarchy or transform issue
was found.

Using the helmet's decoded `crest_centre` attachment and the normalized
column-vector convention, `world_bind[23] * crest_centre_local` is approximately:

```text
[-0.999999881, -0.000002595,  0.000002901, -0.000068934]
[-0.000002938,  0.970109645, -0.242665963,  1.811605057]
[-0.000002188, -0.242665945, -0.970109534, -0.022783698]
[ 0,             0,             0,             1]
```

Its translation is approximately `[-0.000069, 1.811605, -0.022784]`. The basis
is finite and approximately orthonormal. The helmet's measured model-space Y
bounds are `1.490234..1.814453`, so the attachment lies at its top surface. The
crest's untransformed bounds are approximately
`[-0.041687,-0.178955,-0.121887]..[0.041687,0.178955,0.121887]`. This is a
plausible metadata-derived crest anchor; no manual placement or Blender change
was performed.

The next milestone may use this inspection output to construct a static glTF
skin and Blender armature, then validate crest placement. Animation decoding
and shield/weapon slot mapping remain unresolved and are not part of this work.

## glTF skin and Blender armature proof

`export-rmv2-gltf` optionally accepts the two verified skeleton resources:

```powershell
rome2aoe2-pack export-rmv2-gltf `
  --input model.rigid_model_v2 --output model.gltf --lod highest `
  --skeleton-anim rome_man_game.anim `
  --inverse-bind rome_man_game.bone_inv_trans_mats
```

Both options are required together. The skeleton identifier must equal the
RMV2 header identifier, and a rigid model with an empty identifier cannot be
exported with a skin. Omitting both options retains the previous static export.

### Skin architecture and joint attributes

The project-owned post-processing layer appends a named node for every bone in
serialized skeleton-array order. Each node receives its local bind matrix and
children from the decoded hierarchy. `skin.joints` uses exactly that same order,
so RMV2 bone index N remains glTF joint N; no semantic remapping occurs.

The upstream exporter's JOINTS/WEIGHTS accessor offsets assumed Rust source
field order, but the compiled `Vertex` layout places those fields elsewhere.
Once a real skin caused Blender to consume them, values such as joint 224 made
the defect visible. For skinned exports only, the wrapper now serializes the
already-decoded `Vertex::bone_indices` and `Vertex::weights` into tightly packed
buffers and repoints the existing JOINTS_0 and WEIGHTS_0 accessors. Semantic
accessor indices and decoded values are preserved. Position, index, normal,
tangent, UV, material, and original geometry buffers/accessors are unchanged.

The source has six roots. A non-joint node named `rome_man_game_skeleton` owns
the six genuine root nodes and is used for `skin.skeleton`. It does not add a
bone and does not invent parentage between `bn_hips` and the five weapon roots.
The resulting skin has 50 joints and a 50-entry inverse-bind `MAT4` accessor.

Matrices in JSON node properties and binary inverse-bind accessors are flattened
in glTF column-major order from the normalized 4x4 column-vector matrices. The
conversion is covered with a non-symmetric synthetic matrix so row/column
transposition errors cannot pass unnoticed. The hierarchy continues to satisfy
`world = parent_world * local` before serialization.

### Weighted-skin Blender validation

The highest LOD of `3c_roman_headhands_skin1_shape1.rigid_model_v2` imports in
Blender 5.2 without glTF skin or matrix warnings. Blender creates:

- one armature with 50 bones;
- six root bones with the expected names;
- three source mesh objects with armature modifiers;
- 50 distinct vertex groups, all named after skeleton bones;
- no missing or unknown vertex-group names.

Blender also creates an unparented `Icosphere` helper for armature display; it
is not a source RMV2 mesh and is excluded from the source mesh count.

At rest, evaluated versus source mesh positions differ by at most
`6.11e-7`, consistent with floating-point conversion rather than deformation.
A five-degree test rotation of `bn_hips` moves weighted vertices by up to
`0.0660`, proving the groups and armature modifier are usable; the pose is reset
before saving the ignored proof file. After Blender's standard glTF-to-Blender
axis mapping `(X,Y,Z) -> (X,-Z,Y)`, imported rest matrices reproduce the glTF
world bind matrices with maximum component error `6.78e-5`. No exporter-side
axis correction was needed.

### Crest attachment proof

The helmet was exported with the same skin, while the rigid crest retained a
static export. The crest object transform was calculated exclusively as:

```text
world_bind[23] * crest_centre_local
```

The Rome/glTF-space translation is approximately
`[-0.000068934, 1.811605096, -0.022783680]`. After Blender's coordinate-system
conversion, the translation is
`[-0.000068934, 0.022783680, 1.811605096]`.

Blender-space bounds are:

- helmet: `[-0.145996,-0.158081,1.490234]` to
  `[0.145996,0.151611,1.814453]`;
- transformed crest: `[-0.041757,-0.138887,1.608421]` to
  `[0.041619,0.184454,2.014789]`.

The anchor is only `0.002848` below the helmet's maximum Z, the X/Y footprints
overlap, and the crest extends upward from the helmet crown. It therefore aligns
without any manual translation, rotation, scale, or visual correction.

Animations, weapon-slot mapping, shield/gladius/pilum placement, textures,
decals, and final unit assembly remain outside this milestone. The next logical
step is static multi-part skin reuse and attachment-slot evidence gathering,
before any animation decoding is attempted.

The byte-for-byte investigation of the Rome II version-5 transform payload is
documented separately in [ROME2_ANIM_V5.md](ROME2_ANIM_V5.md). It establishes
the discrete pose layout and the narrowly scoped discrete-frame decoder.

Frame 0 of `sws_stand.anim` has now been applied to a single 50-bone Blender
armature. Version-3 VMD provenance places the gladius on `weapon_02` and scutum
on `weapon_03` using their pose-world matrices and identity local transforms.
The fragment, rather than track presence, keeps the `weapon_05` pilum inactive.
Both visible equipment bounds contain their expected hand points without manual
correction, while the crest remains metadata-driven through bone 23 and
`crest_centre`.
