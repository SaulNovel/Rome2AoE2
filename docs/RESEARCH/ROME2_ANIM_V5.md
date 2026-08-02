# Rome II `.anim` version 5 transform payload

This note records the byte-for-byte investigation of the Rome II version-5
animation payload needed for discrete static-pose evaluation. It is deliberately
limited to the three `rome_man_game` clips listed below and the matching skeleton
resource. It is not a claim of support for other animation versions.

## Scope and evidence

The proprietary inputs were inspected only under ignored `build/` output:

- `sws_stand.anim` and `.meta`;
- `sws_combat_ready.anim` and `.meta`;
- `sws_charge_javelin_throw_001.anim` and `.meta`;
- `animations/skeletons/rome_man_game.anim`;
- `animations/skeletons/rome_man_game.bone_inv_trans_mats`;
- `rome_man_sword_shield_fragment.txt`.

Three kinds of evidence are distinguished below:

- **Observed:** direct parsing, offsets, values, and exact size checks against
  the local Rome II files.
- **External implementation:** TheAssetEditor `AnimationFile.cs`,
  `AnimationClip.cs`, `AnimationSampler.cs`, and `AnimationPlayer.cs` at local
  research checkout `df28da06e4704c6025f2902873811ae391a64fb7`.
- **Inference:** conclusions supported by both the observed bytes and how that
  implementation evaluates them, but not by a Creative Assembly specification.

The pinned RPFM decoder in
`third_party/rpfm/rpfm_lib/src/files/anim/mod.rs` reads only the common header and
preserves everything after `bone_count` as opaque bytes. Its own module comments
explicitly state that it provides no keyframe access. Repository/history searches
found no deeper decoder in pinned or current upstream RPFM. TheAssetEditor is the
only located open implementation that both consumes this v5 layout and evaluates
the resulting transforms. Searches of public RME/QtRME and Noesis material did not
locate a second source implementation for this specific Rome II payload.

Relevant public sources:

- [TheAssetEditor animation reader](https://github.com/donkeyProgramming/TheAssetEditor/blob/master/Shared/GameFiles/Animation/AnimationFile.cs)
- [TheAssetEditor animation evaluator](https://github.com/donkeyProgramming/TheAssetEditor/blob/master/GameWorld/GameWorldCore/GameWorld.Core/Animation/AnimationSampler.cs)
- [RPFM repository](https://github.com/Frodo45127/rpfm)

## Primitive conventions

All integers and floats are little-endian. Strings are a signed 16-bit byte
length followed by that many UTF-8 bytes; the observed lengths are nonnegative.
Offsets below are absolute and hexadecimal. All four investigated files have the
same skeleton identifier and bone table, so their post-hierarchy offsets match.

## Header and hierarchy

| Offset | Size | Field | Observed value / interpretation | Confidence |
|---:|---:|---|---|---|
| `0x000` | 4 | `version` | `u32`, value 5 | high, observed |
| `0x004` | 4 | unknown | `u32`, value 1 in all inputs | high value; low meaning |
| `0x008` | 4 | sample rate | `f32`, 15 or 20 Hz | high, observed |
| `0x00C` | 2 | skeleton-name length | `i16`, 13 | high, observed |
| `0x00E` | 13 | skeleton name | UTF-8 `rome_man_game` | high, observed |
| `0x01B` | 4 | duration | `f32` seconds | high, observed |
| `0x01F` | 4 | bone count | `u32`, 50 | high, observed |
| `0x023` | variable | bone table | 50 ordered records | high, observed |

Each bone record is `i16 name_byte_count`, UTF-8 name bytes, then `i32 parent`.
The bone records end at `0x3E5`. Parent `-1` denotes a root. Animation bone order
matches the `rome_man_game` skeleton-array order; in particular indices 0, 2, 3,
and 5 are `bn_hips`, `bn_weapon_02`, `bn_weapon_03`, and `bn_weapon_05`.

## Track maps and counts

| Offset | Size | Field | Interpretation | Confidence |
|---:|---:|---|---|---|
| `0x3E5` | 200 | translation map | 50 `i32` bone-to-track mappings | high |
| `0x4AD` | 200 | rotation map | 50 `i32` bone-to-track mappings | high |
| `0x575` | 4 | translation-track count | `i32`, 6 | high |
| `0x579` | 4 | rotation-track count | `i32`, 32 | high |
| `0x57D` | 4 | stored sample count | `i32`, clip-dependent | high |
| `0x581` | remainder | frame records | frame-major samples | high |

The map value is a track index. `-1` means that the component is absent and must
come from the skeleton's first sample. TheAssetEditor additionally interprets
values above 9999 as `static_track = value - 10000`; no such value and no static
track block occurs in these v5 inputs. Static track blocks are version-7 behavior
in that implementation and must not be invented for these files.

All three clips have identical maps:

- translation: bones 0 through 5 map to tracks 0 through 5; bones 6 through 49
  are `-1`;
- rotation: bones 0 through 25 map to tracks 0 through 25, bone 30 maps to 26,
  bones 33 through 37 map to 27 through 31, and all other bones are `-1`.

Consequently the four validation bones use ordinary tracks:

| Bone | Translation track | Rotation track |
|---|---:|---:|
| `bn_hips` (0) | 0 | 0 |
| `bn_weapon_02` (2) | 2 | 2 |
| `bn_weapon_03` (3) | 3 | 3 |
| `bn_weapon_05` (5) | 5 | 5 |

Weapon roots have no special record type or compression. Unused components omit
tracks through `-1`; there is no per-frame presence mask or offset table.

## Frame records

Records are **frame-major**. For every stored sample, the file contains:

1. `translation_track_count` translations in increasing track-index order;
2. `rotation_track_count` rotations in increasing track-index order.

The translation representation is three unquantized IEEE-754 `f32` values in
`X, Y, Z` order, 12 bytes per track. There is no scale/bias metadata.

The rotation representation is four signed `i16` values in `X, Y, Z, W` order,
8 bytes per track. Each component decodes as `stored / 32767.0`. All four
components, including W, are stored: this is component quantization, not a
three-component/omitted-component quaternion codec. Therefore there is no
omitted-component sign bit or square-root reconstruction. The signs are simply
the signs of the stored `i16` values. Observed decoded norms differ from one by
at most approximately `3.1e-5`, consistent with independent component
quantization. A consumer should normalize before matrix construction to avoid
accumulating this quantization error.

Version 5 stores no scale tracks, scale values, scale map, or scale count. The
external evaluator supplies `(1,1,1)`.

For these clips the frame size is exactly:

```text
frame_bytes = translation_tracks * 12 + rotation_tracks * 8
            = 6 * 12 + 32 * 8
            = 328 bytes
```

## Sample count and endpoints

The stored sample-count rule in every investigated file is:

```text
sample_count = round(duration * sample_rate) + 1
sample_time(i) = i / sample_rate, 0 <= i < sample_count
```

The final endpoint is included. The integer interval count is exact despite the
usual `f32` representation error in the serialized duration.

| Clip | Rate | Stored duration | Intervals | Stored samples | Last index/time |
|---|---:|---:|---:|---:|---:|
| stand | 15 Hz | 2.799999952 s | 42 | 43 | 42 / 2.8 s |
| combat ready | 15 Hz | 2.933333397 s | 44 | 45 | 44 / 2.933333 s |
| javelin throw | 20 Hz | 3.0 s | 60 | 61 | 60 / 3.0 s |

Using `round(duration * rate) + 1` is safer than truncation for the serialized
float, but a decoder must still require the stored count and remaining byte size
to agree rather than silently replacing the stored count with a computed one.

## Exact payload-size reconciliation

The common prefix through the hierarchy is 997 bytes. The maps are 400 bytes,
the three counts are 12 bytes, and frame data starts at byte 1409 (`0x581`).

| File | Frame contribution | Equation | Actual size | Unexplained bytes |
|---|---:|---:|---:|---:|
| stand | `43 * 328 = 14,104` | `997 + 400 + 12 + 14,104` | 15,513 | 0 |
| combat ready | `45 * 328 = 14,760` | `997 + 400 + 12 + 14,760` | 16,169 | 0 |
| javelin throw | `61 * 328 = 20,008` | `997 + 400 + 12 + 20,008` | 21,417 | 0 |

Thus all proposed structures reconcile byte-for-byte. There are no observed
payload flags, masks, offset tables, padding, scale data, or trailing bytes.

## Transform space and hierarchy evaluation

The stored values are absolute **bone-local pose transforms**, not world-space
transforms and not deltas from bind pose. This is supported by:

1. the external reader expands map omissions from the skeleton's first sample;
2. `AnimationClip` treats the resulting values as each bone's position and
   rotation and supplies identity scale;
3. `AnimationSampler` constructs a local SRT matrix and recursively composes it
   with the parent world matrix;
4. the six root weapon translations in real clips are plausible world positions,
   whereas their skeleton fallback translations are zero.

TheAssetEditor uses XNA row vectors and computes
`local = scale * rotation * translation`, then
`world = local * parent_world`. In the project's established column-vector
convention the equivalent operations are:

```text
local = translation * rotation * scale
world = parent_world * local
```

For roots, including all five weapon bones, `world = local`. Quaternion values
must undergo the same Rome-to-project matrix convention conversion already used
for skeleton work; their on-disk component order remains XYZW.

## Numerical spot checks

The following directly decoded first-frame local values predict the requested
tracks. Since these bones are roots, these are also pose-world transforms before
any project coordinate-system conversion.

| Clip / bone | Translation XYZ | Quaternion XYZW |
|---|---|---|
| stand / hips | `[-0.006279, 0.931975, -0.015971]` | `[-0.183050, -0.076937, -0.670400, -0.714957]` |
| stand / weapon 02 | `[0.249603, 0.816128, -0.156509]` | `[-0.339091, 0.521165, 0.190161, -0.759758]` |
| stand / weapon 03 | `[-0.263272, 0.827117, 0.126166]` | `[0.016022, 0.254311, -0.007263, -0.966979]` |
| stand / weapon 05 | `[-0.196910, 1.046562, 0.014772]` | `[-0.500473, 0.515549, 0.587970, -0.371593]` |
| combat ready / weapon 02 | `[0.274189, 0.878139, -0.277364]` | `[-0.099734, 0.646321, -0.146153, -0.742302]` |
| combat ready / weapon 03 | `[0.037602, 0.799778, 0.525783]` | `[0.028687, -0.020020, 0.007477, -0.999390]` |
| combat ready / weapon 05 | `[-0.089720, 0.902978, 0.184102]` | `[-0.182226, 0.230445, 0.780358, -0.552049]` |
| javelin throw / weapon 05 | `[-0.323318, 1.394289, 0.685161]` | `[-0.783624, 0.612964, 0.008057, -0.100711]` |

At javelin frame 60, weapon 05 is
`[-0.078752, 2.511949, 9.466833]` with quaternion
`[-0.065920, 0.697287, -0.176519, -0.691580]`. This large change, along with the
clip-wide forward displacement, independently confirms that weapon roots are
ordinary animated tracks rather than bind-pose attachments.

## Skeleton samples and omitted tracks

`rome_man_game.anim` uses the same version-5 payload representation:

- 50 translation mappings, all `0..49`;
- 50 rotation mappings, all `0..49`;
- counts `(50, 50, 2)`;
- `50 * 12 + 50 * 8 = 1,000` bytes per sample;
- exact size `997 + 400 + 12 + 2 * 1,000 = 3,409` bytes.

The two decoded samples are identical component-for-component. They therefore
confirm both encodings and provide the stable fallback local transform for every
`-1` clip mapping. They do not reveal another compact/static representation.

## `.meta` findings

The companion metadata does not contain an animation sample count, track count,
quantization data, or offsets into the `.anim` payload. It is a separate timed
event stream:

- stand: metadata version 2, two events (`LHAND_POSE`, `RHAND_POSE`);
- combat ready: version 2, three events (`RHAND_POSE`, `LHAND_POSE`,
  `TARGET_POS`);
- javelin throw: version 2, twenty timed events including hand-pose, sound,
  `FIRE_POS`, and `WEAPON_ON` records.

Those events are relevant later for equipment visibility and projectile timing,
but do not participate in transform decoding. Event times are seconds within the
clip, not an independent statement of sample count.

## Conclusions and confidence

| Conclusion | Confidence |
|---|---|
| Header, hierarchy, map/count offsets and sizes | high: directly observed and externally implemented |
| Endpoint-inclusive stored sample count | high across all four examined files |
| Frame-major ordering | high: exact bytes and external reader loop order |
| Translation XYZ `f32` | high |
| Quaternion XYZW signed `i16 / 32767` | high |
| No omitted quaternion component/sign reconstruction | high |
| No scale representation in v5 records | high for examined layout |
| `-1` component fallback to skeleton sample 0 | high: external evaluator plus matching skeleton data |
| Bone-local absolute pose space | high: evaluator and hierarchy/root-value evidence |
| Map values above 9999 denote static tracks | medium for the family, external implementation only; not observed in v5 inputs |
| Unknown header field means a constant type marker | low; only value 1 is established |

## Smallest safe decoder scope

A first project-owned reader can safely be restricted to:

1. version exactly 5 and skeleton ID exactly `rome_man_game`;
2. the serialized 50-bone hierarchy, with exact name/order agreement against the
   supplied skeleton;
3. two 50-entry signed mapping tables;
4. nonnegative dynamic track/sample counts;
5. translation `3*f32` and rotation `4*i16/32767` records in frame-major order;
6. `-1` fallback from skeleton sample 0, rejecting static-map values above 9999
   until a v5 example proves their accompanying storage;
7. identity scale, quaternion normalization, discrete frame selection, local
   hierarchy composition, finite-value checks, and exact EOF consumption.

That scope is sufficient for an `inspect-animation-pose` command and for the
stand-pose transforms of `bn_weapon_02`, `bn_weapon_03`, and `bn_weapon_05`. It
does not require interpolation, Blender actions, keyframes, or general animation
import.

## Implemented discrete-pose boundary

The project-owned `tools/rome2_pack/src/anim_v5.rs` module now implements the
verified boundary through:

```text
rome2aoe2-pack inspect-animation-pose \
  --animation sws_stand.anim \
  --skeleton-anim rome_man_game.anim \
  --inverse-bind rome_man_game.bone_inv_trans_mats \
  --frame first
```

Frame selection accepts `first`, `last`, or a zero-based numeric index. It does
not interpolate. Output format `rome2aoe2.animation-pose` version 1 records the
filename, timing, maps, normalized local translations/quaternions, local/world
matrices, and explicit entries for weapon bones 02, 03 and 05. Absolute input
paths are excluded.

The reader requires version 5, 50 bones, the verified 6/32 clip track counts,
the endpoint-inclusive clip sample count, valid maps, exact payload consumption,
and exact hierarchy/name agreement with the supplied skeleton. The fallback
skeleton is separately restricted to its verified 50/50 tracks, identity maps,
and two samples. Its sample 0 supplies only a missing component whose clip map
is `-1`; inverse-bind matrices are not substituted. Quaternions must be within
`0.003` of unit length before normalization. The existing skeleton inspection is
also run, so hierarchy, inverse-bind count, finiteness, singularity and bind-pose
reconstruction remain validated. The complete throw clip proves that valid
stored quaternions can differ from unit length by `0.0024662`; the implemented
strict bound is therefore `0.003`, followed by mandatory normalization.

Real frame-0 output for `sws_stand.anim` gives:

- `bn_weapon_02`: `[0.249603346, 0.816128433, -0.156508744]`;
- `bn_weapon_03`: `[-0.263271868, 0.827116728, 0.126165688]`;
- `bn_weapon_05`: `[-0.196910322, 1.046561718, 0.014771926]`.

Frame 21 addresses a distinct sample; for example weapon 02 becomes
`[0.236128300, 0.818281174, -0.194151059]`.

## Standing-pose equipment proof

The version-3 dependency origins were consumed directly, producing gladius to
`weapon_02`, scutum to `weapon_03`, and pilum to `weapon_05`. No filename or
slot-name inference was used. The sword-and-shield fragment's `STAND` record
enables weapon bones 2, 3 and 4, but not 5. Consequently the gladius and shield
are visible while the mapped pilum remains inactive; transform availability does
not control visibility.

Blender 5.2 imported the six weighted body-stack glTFs into one 50-bone
armature. Frame 0 was applied as an absolute local pose with the established
Rome/glTF-to-Blender axis conversion. Rigid transforms use:

```text
equipment_world = weapon_bone_world_at_frame_0 * identity * identity
```

The crest continues through `pose_world[23] * crest_centre_local`. No item-level
translation, rotation, scale, pivot, or axis correction was introduced.

The final ignored proof contains one armature, 50 bones, 8 weighted source mesh
objects and 12 visible meshes total. The gladius bounds are
`[0.064717,-0.139707,0.524880]` to `[0.434490,0.452725,1.107377]`; the right-hand
point lies inside them. Shield bounds are
`[-0.619626,-0.400046,0.254594]` to `[0.093082,0.147714,1.399639]`; the left-hand
point lies inside them. The pivots and axes therefore align with their expected
hands without correction, and the complete bounds are
`[-0.619626,-0.738040,0.002720]` to `[0.649770,0.609273,1.997924]`. The assembled
silhouette is a recognizable standing sword-and-shield Praetorian.

## Canonical full-clip architecture

`decode_animation_clip` is now the single decoding path. It parses each input
once and produces an ordered `AnimationClip` whose `AnimationFrame` entries
contain source index/time plus expanded local and evaluated world transforms for
all 50 bones. `inspect-animation` serializes every frame, while
`inspect-animation-pose` selects a frame from the same decoded clip. No sample is
decoded through a pose-specific path.

```text
.anim v5 + skeleton sample 0 + inverse-bind validation
    -> canonical AnimationClip (all source samples)
       -> inspect-animation JSON
       -> inspect-animation-pose selection
       -> Blender Action
```

The canonical output preserves sample order, rate and the cyclic endpoint. It
does not deduplicate, interpolate, resample, smooth or simplify. Real validation
produced exactly 43 stand, 45 combat-ready and 61 throw frames, each containing
50 bones. Their final times are 2.8, 2.933333333 and 3.0 seconds respectively;
all agree with declared duration within the documented float tolerance.

## Blender Action import

`src/blender/import_animation_clip.py` consumes the canonical JSON and creates
one Action. Scene FPS defaults to 60 and is configurable independently of source
rate. Source time maps to `timeline_start + time_seconds * scene_fps`; the
validated ranges are:

| Clip | Source samples/rate | Blender frames | F-curves | Keyframe points |
|---|---|---|---:|---:|
| stand | 43 at 15 Hz | 1–169, every 4 frames | 350 | 15,050 |
| combat ready | 45 at 15 Hz | 1–177, every 4 frames | 350 | 15,750 |
| pilum throw | 61 at 20 Hz | 1–181, every 3 frames | 350 | 21,350 |

Every bone receives three location and four quaternion curves. All source
positions are retained, interpolation is explicitly linear, scale remains
identity, and no extra baked keys or simplification are used. Blender rest/parent
conversion reconstructs sampled source world matrices with maximum error
`2.87e-6` across the three proofs. Weighted bounds remain finite and coherent;
stand and combat endpoints have no visible discontinuity. Their maximum local
component endpoint differences are `0.003052` and `0.000288`. The throw is not a
loop and advances about 8.78 source units, as encoded.

Equipment uses version-3 provenance and bone-follow constraints rather than
independent object animation. A shared Rome-to-Blender basis wrapper is separate
from the identity item-local transform. Maximum sampled equipment-follow error
is below `7.7e-8`. Fragment flags give:

- `STAND`: gladius 02 and shield 03 visible; pilum 05 hidden;
- `COMBAT_READY`: gladius 02 and shield 03 visible; pilum 05 hidden;
- `THROW_PILUM`: gladius 02, shield 03 and pilum 05 active.

The crest follows `bn_head` using the original `crest_centre` matrix. Clip-level
pilum activation does not establish the projectile release/hide frame; timed
metadata and projectile handoff remain a later milestone.

## Future render sampling boundary

Render sampling must consume, never mutate, the canonical clip:

```text
canonical full animation
    -> configurable render-frame sampler
    -> selected AoE2 sprite frames
```

The future default is `render_sampling.mode: source_samples`. Possible later
policies are `every_nth_sample`, `target_fps`, `explicit_frames`, and `adaptive`.
None belongs in the `.anim` decoder or Blender Action importer.

Limitations remain deliberate: only the reconciled Rome II v5 50-bone/6/32
layout is accepted. There is no general animation-version support, nonlinear
interpolation, projectile release timing, rendering, or AoE2 action mapping.
