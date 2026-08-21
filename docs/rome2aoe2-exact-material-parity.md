# Exact Hastati material parity

The approved production call path is:

1. `scripts/render_hastati_native_{walk,attack,death}.ps1`
2. `src/blender/render_final_hastati_idle.py:main`
3. `hastati_runtime_scene.configure` for the frozen production scene and Raw
   colour management
4. `render_hastati_runtime_parity.render_aov` / `build_pass` for raw texture,
   tangent-basis, mask, dirt, gloss and family buffers
5. `runtime_material_preparation.prepare_weighted`,
   `prepare_weighted_skin_dirtmap`, `prepare_weighted_dirtmap`, or
   `prepare_decal_dirtmap`
6. `render_hastati_runtime_parity.shade` for captured standard/skin lighting,
   environment reflection, the captured S-curve, XYZ/Yxy conversion, brightness,
   gamma and display matrix
7. `downsample_rgba` for the x1/x2 production frames

The rejected generic path first diverged before material preparation by
replacing steps 4–6 with a Principled node approximation. Stage findings:

| Material | First divergent stage | Cause |
|---|---|---|
| `roman_body1`, `roman_1_head` | specular/skin lighting | SkinMask was reduced to bounded Principled subsurface instead of retained as captured RT2 data and routed through event-1926 skin lighting. |
| `roman_1_sandals`, `roman_1_eyes_teeth` | specular/gloss lighting | RGB F0, smoothness and reflectivity were collapsed into Principled scalar controls instead of standard event-1915 lighting. |
| `roman_early_scutum_lod1` | faction-mask composition | The approximation did not use the oracle's exact linear faction constants and shield slot order before DecalDirtmap preparation. |
| `roman_gladius_lod1`, `roman_pilum_light_lod1` | specular/gloss lighting | The accepted production fallback uses the same raw-AOV standard-lighting path; the approximation used a different BRDF and display transform. |
| `lorica_hamata_A`, `roman_belt_01`, `hellenic_konos` | legacy diffuse/faction preparation | Recovered by composing captured Weighted faction semantics with captured event-1418 WeightedDirtmap semantics. RMV float0/float1 now drive dirt UV scale; `test_black` remains zero contribution. |

`test_black.dds` remains an engine sentinel with zero dirt contribution. It is
not treated as authored full dirt coverage.

The controlled shared-asset harness is
`src/blender/render_shared_material_parity.py`. It rasterizes each isolated
asset's raw AOVs once. The rejected generic preparation and the oracle then use
those identical inputs and the same captured lighting/display function. The
`*-ab.png` sheets expose that real mismatch. The corrected `*-fixed-ab.png`
sheets compare the oracle against the generic exact-backend entry point. The
machine-readable report is generated at
`build/validation/rome2aoe2/shared-material-parity/report.json`.

The legacy Principled backend is not production-ready. `convert` now stops with
`UNSUPPORTED_MATERIAL_FIDELITY` rather than rendering its acknowledged
approximations and claiming READY material support.
