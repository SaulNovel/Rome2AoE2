# Third-party patches

Do not reset, update, stage, or casually build in the current `third_party/rpfm` checkout. It is a managed dirty overlay on GPL-3.0 upstream commit `fdde51aa9e6826afda1832d1b563b5f11125dc75`.

Only two ordered semantic patches are portable project state:

| Order | Patch | SHA-256 |
|---|---|---|
| 1 | `patches/rpfm/0001-support-rome2-default-layout-materials.patch` | `0dd66768c8656119ea6e1460f9ac4a927661e5c3898f0153984527bae28ee2be` |
| 2 | `patches/rpfm/0002-preserve-rmv-pivots-and-serialize-gltf-vertices.patch` | `0e38820ecf99809b36ce9729d9ce36a1bfb8870fa42c17b4742484afec7f8a08` |

The live Windows overlay has accidental mixed CRLF/LF bytes in `rpfm_extensions/src/gltf/mod.rs`. They are not functional state and are deliberately excluded from the patch series. Doctor may warn about that live checkout, but validates normalized LF source identities:

| Modified path | Normalized-text SHA-256 |
|---|---|
| `rpfm_extensions/src/gltf/mod.rs` | `a6ce533d0a301984c25f902cbb8e70ff7b79cf3cef747cf8463f718a8b8d365f` |
| `rpfm_lib/src/files/rigidmodel/materials/mod.rs` | `f57f7e16353702ec1e2f49b5f2f7b5bffcc97844d33868088f78a07b7935fab3` |
| `rpfm_lib/src/files/rigidmodel/test_rigidmodel.rs` | `16ebf67f4d6f3084eba9476cf084b0e2d5c70f6eb1f382487c9abd3bb5299eb9` |
| `rpfm_lib/src/files/rigidmodel/vertices/mod.rs` | `fe9ff8467e5ad7c4551f3a35f5639a0b6c127007ddfe19dd3240d9cbf14697c9` |

Initialize and apply on a new machine, failing loudly if the gitlink is wrong:

```powershell
git submodule update --init -- third_party/rpfm
$expected='fdde51aa9e6826afda1832d1b563b5f11125dc75'
$actual=git -C third_party/rpfm rev-parse HEAD
if ($actual -ne $expected) { throw "RPFM base mismatch: $actual" }
git -C third_party/rpfm apply --check ..\..\patches\rpfm\0001-support-rome2-default-layout-materials.patch
git -C third_party/rpfm apply ..\..\patches\rpfm\0001-support-rome2-default-layout-materials.patch
git -C third_party/rpfm apply --check ..\..\patches\rpfm\0002-preserve-rmv-pivots-and-serialize-gltf-vertices.patch
git -C third_party/rpfm apply ..\..\patches\rpfm\0002-preserve-rmv-pivots-and-serialize-gltf-vertices.patch
git -C third_party/rpfm diff --check
git -C third_party/rpfm status --short
cargo check --locked --manifest-path third_party/rpfm/rpfm_lib/Cargo.toml
cargo test --locked --manifest-path third_party/rpfm/rpfm_lib/Cargo.toml
```

`status --short` must list exactly the four paths in the hash table. Disposable replay at the pinned base must pass both forward `apply --check` operations; reverse-check in order 0002 then 0001; match all four normalized hashes; pass `git diff --check`; and compile/test under the locked dependency graph. It need not reproduce host-specific line endings.

A maintained fork remains cleaner for a long-lived overlay, but no fork or remote was created. `third_party/googletest` is pinned at `b78aa5ee64be299ae50932e7b4d7e5d7b89a72f6`; `third_party/AoE2ScenarioParser` at `b763e2e37006bedab50c7d349b3ce24b9c2497f6`. The Asset Editor reference patch `patches/the-asset-editor/rmv2-rigid-pivot-gltf-node.patch` is source-only; Asset Editor itself is manually supplied and not vendored.
