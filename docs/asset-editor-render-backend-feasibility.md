# The Asset Editor render-backend feasibility (2026-08-09)

## Scope and control

This investigation deliberately stops before an AoE finishing or SLD sweep. The
preserved control is `config/render_profiles/hastati_p5_stock_punch_baseline.json`
(SHA-256 `49D83F0F8BADBFF47BD92BB9E93BD0E096B19937F501905DC9418ABB495C32B7`).
`tests/AoE2HastatiStockPunchTests.py` passes against the preserved P5 artifacts.

## Version and license

The inspected upstream revision is The Asset Editor v0.78,
`df28da06e4704c6025f2902873811ae391a64fb7` (2026-07-27). The upstream project is
MIT licensed. Its bundled Phazer/Nadrin PBR shader sources also carry MIT
licenses.

## Proven capabilities

- Rome II is a defined game type, with RMV2 and Rome II test fixtures.
- Kitbash can render rigid models, skeletons, and animations.
- The camera implements perspective and orthographic projections with explicit
  position, yaw, pitch, zoom, look-at target, and orthographic size.
- PhotoStudio persists camera/light settings and writes transparent PNG frames.
  Capture is viewport-sized at either 1x or 2x, rather than arbitrary requested
  dimensions.
- The material factory chooses a specular/gloss PBR path for Rome II. It binds
  diffuse, normal, specular, gloss, and mask slots and has faction-tint support.
  This is a Total-War-aware approximation implemented with the editor's own PBR
  shaders, not proof of Rome II's exact runtime shader.
- IPC is a Windows named pipe (`TheAssetEditor.Ipc`) using newline-delimited JSON.
  In v0.78 its only action is `open`; it has no camera, animation-time, rotation,
  capture, resolution, or output-path actions.

## Same-Hastati loading result

The official v0.78 binary was run with Rome II selected. Opening the exact
`roman_hastati.variantmeshdefinition` by virtual path failed. Opening a selected
Hastati RMV2 with Rome II `models.pack` supplied through `packPathOnDisk` returned
`{"ok":false,"error":"Pack file load failed"}`. The IPC loader accepts a pack
file, not the project's extracted system folder. Therefore a same-composition,
same-pose Asset Editor control render was not produced in this bounded test.

Opening the VMD directly would not in any case guarantee the resolver's selected
representative. The effective-unit manifest's selected RMV2 paths and their
texture references are directly useful, but composition transforms, attachment
relationships, skeleton/animation selection, faction colours, exact animation
time, and deterministic camera/capture settings need an adapter.

## Architectural conclusion

No defensible visual ranking (better/equivalent/worse than P5) is possible until
the exact resolved soldier is rendered. The release executable has the necessary
rendering primitives but not the required batch-control surface. A minimal useful
integration is therefore a small source-level helper/fork that:

1. loads a system-folder asset container or a deliberately prepared small pack;
2. assembles the selected effective-unit components rather than rerolling a VMD;
3. sets faction tint, skeleton, animation, and exact sample time;
4. sets orthographic camera/object rotation deterministically; and
5. captures arbitrary-size transparent PNG to a specified path.

That helper would make 16 directions times N frames feasible, but the stock v0.78
IPC does not. Building it is beyond this feasibility milestone and should not be
started before comparing one exact control frame.

## Official fallback

The installed Rome II Assembly Kit contains
`TWeak_VariantEditor.AssemblyKit.dll` and
`editor_working_data/Weather/variant_editor_day.environment`. This makes the
official Variant Editor the correct next visual control. No standalone CLI or
documented batch-capture surface was found in the installed files, so initially
it should be tested manually on the exact Hastati rather than treated as the
production automation backend.
