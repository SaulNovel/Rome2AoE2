# Rome II coherent environment-yaw experiment

Eight frozen facet-03 candidates rotate the recovered environment around Blender
world Z by 45-degree increments. Each candidate applies the same `Renv` to the
directional sun (`Renv @ L0`), ambient-cube coordinates (`N @ Renv`), and HDR
cubemap lookup (`reflected @ Renv @ transform`). Materials, shader equations,
intensities, colours, display, camera, pose, and scale remain unchanged.

| yaw | transformed sun direction | body P10 / median / P90 | cuirass median | skin median | tunic median | clipped |
|---:|---|---|---:|---:|---:|---:|
| 0 | (-.752205, .546509, .368125) | .04643 / .16856 / .39741 | .14512 | .29329 | .20722 | 0% |
| 45 | (-.918329, -.145449, .368125) | .04646 / .22643 / .41993 | .14739 | .31281 | .23127 | 0% |
| 90 | (-.546509, -.752205, .368125) | .04649 / .28106 / .48310 | .23408 | .39287 | .25802 | 0% |
| 135 | (.145449, -.918329, .368125) | .05914 / .29428 / .56451 | .32325 | .44525 | .28557 | 0% |
| 180 | (.752205, -.546509, .368125) | .05774 / .25181 / .51997 | .29736 | .41318 | .27923 | 0% |
| 225 | (.918329, .145449, .368125) | .04648 / .18331 / .38839 | .18918 | .27206 | .24863 | 0% |
| 270 | (.546509, .752205, .368125) | .04646 / .15745 / .35778 | .14598 | .22874 | .22748 | 0% |
| 315 | (-.145449, .918329, .368125) | .04644 / .16105 / .38628 | .14813 | .27666 | .21254 | 0% |

This is not a metric-selected winner. Visually, 135 and 180 degrees make the
helmet, cuirass, upper torso, and shield-facing side dramatically more readable
than the captured zero-yaw orientation. They also make large leg regions very
pale. Yaw 225 is a warmer, less forceful candidate. These images demonstrate that
coherent orientation alone can address much of the dark-main-body problem, while
leaving the later camera-relative sprite-lighting choice open.

Images and the machine-readable report remain ignored under
`build/local-integration/rome2/runtime-parity-proof/`.
