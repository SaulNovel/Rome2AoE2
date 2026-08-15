# AoE2 DE sprite-tool audit (2026-08-15)

## Decision

Use the repository's native SLDX v4 authoring path with Microsoft DirectXTex
`texconv` as the BC1 backend:

```
RGBA frame + shadow alpha + shaded player-colour mask
    -> src/aoe2/sld_authoring.py
    -> DirectXTex texconv (BC1_UNORM main layer)
    -> project BC4 encoder (shadow and player colour)
    -> src/aoe2/sld.py strict serializer
    -> paired _x1.sld / _x2.sld
```

This is the best *programmatic* production route currently available to this
project. It is not a speculative choice: project-authored x1 and x2 files have
already rendered in AoE2 DE, including saturated RGB/CMY controls, and the
player-colour representation is covered by a runtime diagnostic and unit tests.
The selected DirectXTex build improves opaque-RGB PSNR from 28.48 dB to 30.25
dB over the deterministic fallback while preserving the silhouette exactly.

The code boundary is narrow and reviewable. The SLD container/block work adapts
only the required portions of `justinas-kazanavicius/aoe2-transparent-buildings`
at `bce7f2f795483ae1c91afb915cc014a520dc0a30`; that project is MIT licensed and
its notice is retained in `third_party/licenses/aoe2-transparent-buildings-MIT.txt`.
DirectXTex is also MIT licensed. See `AOE2_DE_SLD_AUTHORING.md` for the format,
compression, and in-game evidence.

## Investigated tools

| Candidate | Programmatic interface | Output / coverage | Source and licence status | Result for Rome2AoE2 |
|---|---|---|---|---|
| Project SLD authoring + DirectXTex | Python API/CLI plus `texconv.exe` CLI | Native SLDX v4; main, shadow, player colour; x1/x2 | Project code; narrowly adapted upstream MIT code; DirectXTex MIT | **Selected production route** |
| Official DESpriteTool 4.20.1 | Folder argument and batch files | PSD->SLD; SLP->SMP->SMX; x1 generation and 16-facet settings | Closed binary shipped with the installed game | Keep for official comparison and legacy SMX only |
| aoe2-transparent-buildings | Python CLI/source modules | Strict SLD parsing/writing and compressed-block modification | Public MIT source | Selected technical foundation; already adapted |
| openage | Source/library, build required | Detailed SLD/SMX parsing and conversion research | GPLv3-or-later | Independent format oracle; not a production encoder |
| genieutils / AGE source | C++ library, build required | Strong SMX reader/writer and DAT integration | Bundled source has its own upstream/licensing constraints | SMX validator/fallback only |
| SMX Workshop | GUI and GUI batch features; no documented stable CLI found | SMX editing/conversion and SLD interoperability | Closed community binary; redistribution/source licence not established | Manual independent control only |
| SLX Studio 1.4.1 | GUI and GUI batch features; no documented stable CLI found | SMX/SLP authoring, masks, palettes, anchors | Closed community binary; redistribution/source licence not established | Manual known-good SMX control only |
| Siege Engineers SLD Extractor | Browser JavaScript can be scripted with extra integration work | SLD extraction/editing, player colour and anchors | Public source, but no licence file was visible in the audited repository | Read-only comparison; do not vendor |
| MerySLP | Java command-line encoder/decoder | Legacy SLP main/player/shadow channels | Public source; no reusable licence established during audit | Wrong runtime generation; do not adopt |
| Advanced Genie Editor | GUI | DAT metadata and graphic records, not sprite production | Official/bundled tool and source | DAT inspection only |

## Why DESpriteTool PSD-to-SLD is not selected

The installed binary and documentation are real and callable. The current
installation contains `DESpriteTool.exe`, `convert_psd.bat`, `convert_slp.bat`,
root/unit `settings.json`, palettes, and templates. Unit settings declare 16
facets and the root configuration enables x1 generation, player colour, BC
compression, and bicubic downsampling.

The blocking issue is the PSD contract. DESpriteTool accepts its required Adobe
RGB16 PSD structure, including `Lr16` layer records. Maintained Python PSD
writers tested by the project did not emit that structure. Automating Photoshop
or GIMP to reproduce a proprietary document dialect would add a large fragile
dependency before encoding even starts. It would also discard the already
validated direct control over frame order, hotspots, block bounds, alpha
thresholds, and player-colour values.

DESpriteTool remains useful for the proven legacy SLP->SMP->SMX path and as an
official-output comparison. It should not gate native SLD production.

## Why the GUI tools are not production dependencies

SMX Workshop and SLX Studio are valuable manual controls, particularly for
checking masks, direction ordering, anchors, and whether a palette problem is
specific to the project's SMX staging. Neither supplied a documented stable CLI
or a publicly licensed source boundary suitable for unattended builds. GUI
automation would be slower and less reproducible than the native SLD path and
would still target SMX in SLX Studio's main workflow.

They should be used only if a specific runtime discrepancy needs an independent
community-authored comparison. Their output can then be compared without
making either application a build dependency.

## Verification performed for this audit

- Installed DESpriteTool binary SHA-256:
  `E2BF4F10430AFE433F9533930CF0C1FC0543C57C02439B2B531D84A31244D456`.
- Local openage reference commit:
  `9a5a7ccbfc20c2de658fc746462cd4a69aa758ef`.
- Local aoe2-transparent-buildings reference commit:
  `bce7f2f795483ae1c91afb915cc014a520dc0a30`.
- `python -B tests/AoE2SLDAuthoringTests.py`: 20 tests passed.
- `python -B tests/AoE2PlayerColorDiagnosticTests.py`: 1 test passed.
- `git diff --check`: passed (one existing line-ending warning only).

## Required static gate before any animation

Do not encode directions or animation yet. Freeze one accepted representative
Hastati frame and author main-colour-only x1/x2 SLD files. Strictly decode both,
compare source and decoded RGB/A visually and objectively, and only if that gate
passes test x1 with UHD disabled and x2 with UHD enabled through the isolated
DAT/scenario path. Establish infantry scale against vanilla Militia using one
camera-scaled validation render. Shadow and player colour then require separate,
sequential gates. Complete 67-frame by 16-direction authoring is prohibited
until main colour, scale, UHD, shadow, and player colour have each passed.

## Public references checked

- Microsoft DirectXTex: <https://github.com/microsoft/DirectXTex>
- MIT SLD parser/writer foundation:
  <https://github.com/justinas-kazanavicius/aoe2-transparent-buildings>
- openage: <https://github.com/SFTtech/openage>
- Siege Engineers SLD Extractor:
  <https://github.com/SiegeEngineers/sld-extractor>
- SLX Studio distribution description:
  <https://ageofnotes.com/download/slx-studio/>
