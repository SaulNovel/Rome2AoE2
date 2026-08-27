# Project overview

Rome2AoE2 is a generic conversion pipeline from Total War: Rome II units to native Age of Empires II: Definitive Edition sprites/mods. Principes is the current generic working unit. Hastati is frozen: it is a known-good oracle and must not be regenerated, modified, installed, or overwritten.

## Pipeline

Rome II packs/assets → extraction and dependency resolution → RMV2/VMD/skeleton/material/texture preparation → `.anim` conversion through Asset Editor's `RmvToGltfExporter` → normal Blender glTF import with the imported Action unchanged → native assembly → headless rendering through the recovered Rome II runtime-equivalent material backend → 16 canonical AoE2 directions → direct SLD authoring → optional DAT/scenario development integration.

Never manually reconstruct animation Actions, zero hips, or remove root motion. Animated weighted geometry uses the native Asset Editor skeleton basis. The shared material backend is `src/blender/render_hastati_runtime_parity.py`; its historical name is now generic. Production visual scale is `7.27480212108078`. Render sizes are 800 master, 400 x2, and 200 x1. Direction `i` uses `yaw(i) = (292.5 - 22.5*i) % 360`.

FAST is diagnostic-only x2; release SLD authoring must reject FAST. V4 shield readability and V5 weapon readability are approved. Physical world-height corpse sinking and the attack recovery-tail hold matching gameplay reload are human-approved and must not regress.

## Frozen Principes contract

Manifest: `config/manifests/rom_principes-explicit-animations-v2.json`. The verified tracked byte SHA-256 is `4ead2bf1a918fe33a4ef3ae2fd472233877717b8ab54679fd500b97449e5a496`. The frozen project identity `611db84c371e707bbf8c14626402077a8974f7d8c14af1941b0f38905f39625b` is the SHA-256 of UTF-8 canonical JSON (`sort_keys=True`, separators `(',', ':')`, no ASCII escaping), as used by `rome2aoe2.conversion.manifest_digest`. HEAD and working-tree bytes are identical: 9,556 bytes, UTF-8 without BOM, LF endings, one final newline. Git history contains this path only from commit `8f19570bf39be85a7b95518defdc7d18a40fc7ee`; no alternate historical bytes exist locally. Doctor requires the byte hash, canonical hash, and frozen clip names/counts/FPS, so neither formatting nor semantic changes are silently accepted.

Clips: idle `sws_stand.anim` (43 frames, 15 FPS); walk `sws_walk_162_cm.anim` (23, 20 FPS); attack `sws_sync_atk_005.anim` (27 native frames, 20 FPS); death `sws_death_stand_004.anim` (33, 15 FPS). The approved 13-frame attack recovery hold produces 40 frames, exactly 2.0 seconds.

## Established capabilities and history

Verified branch history includes dependency resolution (`7ef489a`), generic infantry conversion (`5f3cb98`), native animation configuration (`8f19570`), production rendering (`805acf0`), direct SLD authoring (`4668887`), configurable visual scale (`ebbc7c4`), shield readability (`087a1df`), weapon readability (`a38e65a`), FAST diagnostics (`cd28faa`), physical corpse sinking (`0a3cb5d`), and recovery-tail holding (`1e7dc03`). Earlier oracle commits freeze Asset Editor conversion (`dcb2a2d`), rigid pivots (`334ee1f`), and validated Hastati animation (`56fadae`, `328716f`).

## Open work

Lighting remains diagnostic-only; V5 production has not been replaced. Pure camera-axis lighting and camera-right offsets were unsatisfactory. Next: illumination-contributor decomposition, then physically summed symmetric camera-relative candidates. No lighting experiment may be promoted without human visual approval.

## Known verification baseline

The clean-suite inherited baseline is documented in `docs/KNOWN_ISSUES.md`: 321 tests, 318 passed, 0 skipped, 2 failed, and 1 error. The wrapper remains intentionally nonzero until those pre-existing rendering-contract and generated-report issues are resolved separately.
