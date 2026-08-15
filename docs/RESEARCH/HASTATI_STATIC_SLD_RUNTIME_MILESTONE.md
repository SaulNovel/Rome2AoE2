# Accepted Hastati static native-SLD runtime milestone

Date: 2026-08-15

## Accepted result

The one-frame, main-colour-only Hastati native SLD test is visually accepted in
AoE2 DE with Enhanced Graphics both disabled and enabled.

Manual x1 result (Enhanced Graphics disabled):

- visible and stable, with no crash;
- approximately 1.25 times vanilla Militia infantry height;
- accepted Rome II colours and material separation preserved;
- feet/ground placement correct and no obvious clipping.

Manual x2 result (Enhanced Graphics enabled):

- visible and stable, with no crash or disappearance;
- same logical size and ground position as x1;
- accepted colours/material separation preserved;
- sharper detail, correct hotspot and no obvious clipping.

## Frozen production values

- camera: orthographic, elevation 18 degrees;
- absolute orthographic scale: `7.27480212108078`;
- world target: `(0.0, 0.0, 0.8503072261810303)`;
- x1 canvas/hotspot: `200x200`, `(100,122)`;
- x2 canvas/hotspot: `400x400`, `(200,244)`;
- scale relationship: native x2 dimensions and hotspot are exactly 2x x1;
- SLD: SLDX v4, DirectXTex BC1_UNORM, main layer only;
- no shadow, player colour, or outline.

Installed accepted static hashes:

- x1: `089027280D64AA30FD6AF3AA725084331A823A1518C9AF060A4F89EECFBE25EC`;
- x2: `259F4FCB4FEFDDB9621CCCEF49BEB2E0DED9263648039B756B224BD6D47949FE`.

Static scaled source bounds are 52 pixels high at x1 and 103 pixels high at
x2. Strict source-to-SLD decode has zero silhouette errors and exact binary
alpha coverage at both resolutions. Opaque RGB PSNR is 28.31 dB for x1 and
29.58 dB for x2.

## Freeze boundary

Full-idle work must reuse the same corrected Blend, native `sws_stand` action,
accepted material renderer, world-origin anchor calculation, camera values,
DirectXTex-backed main-colour SLD authoring, and x1/x2 relationship. Changes to
materials, colour transport, scale, attachments, skeleton, or animation
mathematics require new hard evidence and are outside the idle transport gate.

