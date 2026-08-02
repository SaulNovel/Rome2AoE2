# Rome II materials and final-scale rendering

The Praetorian material pipeline preserves the authored Rome II DDS inputs,
DirectX tangent normals, gloss/specular data, alpha-tested silhouettes, shield
decal, dirt inputs, and unresolved faction masks. Readability calibration does
not simplify or edit those canonical materials.

The final gameplay-scale profile is documented in
`AOE2_DE_RENDER_CALIBRATION.md`. It uses lighting, exposure and alpha-correct
4x bicubic reduction to improve chainmail and cloth separation at 43-45 pixels.
It deliberately applies no per-material contrast, saturation, metallic, alpha,
or sharpening override. Skin scattering and faction-mask semantics remain
unresolved, but neither produces an obvious defect at the target sprite size.

The standing shield is strongly foreshortened in most useful body directions.
Its authored decal is retained, but its motif can fall below identifiable size
after reduction. This is recorded as a projected-area limitation rather than
being compensated with an unverified material change.
