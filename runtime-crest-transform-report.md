# Rome II runtime named-crest transform

## Verdict

**NAMED RMV2 ATTACHMENT SEMANTIC RECOVERED**

Rome II evaluates the record as:

```text
feather_world =
    soldier_root
  * animated_bone_delta[Attachment.BoneIndex]
  * bone_world_bind[Attachment.BoneIndex]
  * RMV_MODEL_FRAME
  * Attachment.SerializedMatrix
  * child.Material.Transform.Pivot
```

where, in the captured RMV coordinate convention:

```text
RMV_MODEL_FRAME = diag(-1, -1, +1, +1)
```

The serialized attachment matrix is direct and is not inverted. The child pivot is evaluated inside the attachment transform.

## Runtime evidence

- Capture: `images-frame46753.rdc`
- Feather draw: event 1051, 1002 indices / 334 triangles, 29 instances
- Montefortino draw: event 1418, 1698 indices, 10 instances
- Instance data resource: 3750
- Feather stride: 96 bytes; final 3x4 transform at offsets 0/16/32
- Helmet stride: 88 bytes; soldier-root rows at offsets 0/16/32
- Helmet animation texture: resource 4022, `R32G32B32A32_FLOAT`, 420x1024
- `bn_head` is bone 23, therefore rows are texture columns 69, 70 and 71.

Nine Montefortino soldiers had an unambiguous feather match by world X/Z. Removing the captured root and animation delta from each pair produced one invariant local transform. Maximum element spread was `4.001754e-5`.

The complete source formula reconstructed all nine captured final matrices with maximum component error `4.117865e-5` and RMS maximum-component error `3.869833e-5`. This is consistent with captured float32 data and the glTF bind-frame round trip.

## Representative target

Helmet instance 0 matches feather instance 1.

Captured soldier root:

```text
[0.947655261, 0, 0, 247.446914673]
[0, 0.947655261, 0, 366.161712646]
[0, 0, 0.947655261, -425.561157227]
```

Captured `bn_head` animation delta:

```text
[ 0.995918989, -0.085893668,  0.027858261,  0.162444428]
[ 0.085765496,  0.996301115,  0.005751329, -0.943452418]
[-0.028253458, -0.003339224,  0.999593437,  0.073481321]
```

Captured final feather transform:

```text
[-0.943787515, -0.084564865, -0.013102650, 247.435455322]
[-0.081278794,  0.931241035, -0.155685633, 367.082366943]
[ 0.026772477, -0.153925747, -0.934685349,-425.545288086]
```

## Source-local reconstruction

The source-derived runtime local transform, including the child pivot, is:

```text
[-1.000014410,  0.000020540,  0.000035957, -0.007953460]
[ 0.000014927,  0.987257222, -0.159233670,  1.923078653]
[-0.000041774, -0.159228446, -0.987243728, -0.050567150]
[ 0,             0,             0,             1]
```

The previously missing operation was `bone_world_bind * RMV_MODEL_FRAME` between the animated bone delta and the serialized named-attachment matrix. Treating the animation-texture matrix as an absolute bone transform, or reducing directly to `animated bn_head * crest_centre`, omits that frame.

## Integration and validation

The assembly path now distinguishes generic RMV2 named-attachment records from skeleton weapon-bone sockets. Named records apply the fixed RMV model frame followed by the direct serialized matrix. Weapon sockets remain identity below their weapon bones. No asset name or crest-specific numeric correction is used.

The clean Blender rebuild retains the imported feather pivot and visibly seats the feather roots at the top-centre helmet fitting. Gladius, shield and pilum paths were not altered. Start, frame 33 and end renders completed; the crest follows the head in each sampled frame.

No material, animation, geometry, skeleton, skin, pivot-export, lighting or camera system was changed. No commit was created.
