# Dependency inventory

Versions below were derived from the working installation, lockfiles, submodule commits, imports, and executable calls on 2026-08-27.

| Class | Dependency | Version/commit | Requirement and purpose | Install/location | Verify | Stage |
|---|---|---|---|---|---|---|
| Python package | Pillow | 12.1.0 | Required PNG/SLD I/O | `requirements.txt`; system venv | `python -c "from PIL import Image"` | authoring/tests |
| Python package | NumPy | 2.5.1 system target; Blender bundles 2.3.4 | Required image/material math | requirements; use Blender-bundled copy in Blender | `python -c "import numpy"`; `blender --background --python-expr "import numpy"` | prep/render/tests |
| Python package | opencv-python | optional; no known-working install present | Optional D03 finishing; deterministic fallback exists | omit unless explicitly testing OpenCV | `python -c "import cv2"` | finishing |
| Python package | aoe2-genie-tooling | 1.2.4 | Required DAT/graphics workspace adapter; 1.3.0 metadata also existed locally but is not published on the configured package index | requirements; published package index | `python -c "import aoe2_genie_tooling"` | DAT/tests |
| Python package | deprecation / ordered-set / typing_extensions | 2.1.0 / 4.1.0 / 4.12.2 | Required by ScenarioParser | requirements | import each | scenario |
| System/runtime | Python x64 | 3.14.6 | Required project/test interpreter | winget `Python.Python.3.14` | `py -3.14 --version` | all non-Blender Python |
| System/runtime | Git for Windows | 2.55.0 | Required source/submodules/patches | winget `Git.Git` | `git --version` | bootstrap |
| System/runtime | Blender LTS | 5.2.0, release branch `blender-v5.2-release`, build `fbe6228777e7` | Required pinned render/import runtime; output can change by version | official Blender/winget; `ROME2AOE2_BLENDER` or standard Program Files path | `& $env:ROME2AOE2_BLENDER --version` | assembly/render |
| System/runtime | Rust toolchain | rustc/cargo 1.97.1; crate MSRV 1.85 | Required to build `rome2aoe2-pack` and patched RPFM libraries | rustup/winget | `rustc --version; cargo --version` | extraction/RMV2 export |
| Optional development | CMake + MSVC Build Tools | CMake 4.4.0; VS 2022-compatible | C++ tests/scenario targets | winget + Visual Studio Build Tools C++ workload | `cmake --version; cl` | native tests |
| Optional development | .NET SDK | 10.0.302 observed | Asset Editor source investigation/build only | winget `Microsoft.DotNet.SDK.10` | `dotnet --info` | tool research |
| Optional development | 7-Zip | no CLI on PATH on audit machine | archives/source inspection only; fixture scripts use stdlib ZIP | winget `7zip.7zip` | `7z i` | tooling |
| Git source | googletest | `b78aa5ee64be299ae50932e7b4d7e5d7b89a72f6` | C++ tests; upstream BSD-3-Clause | pinned submodule | `git -C third_party/googletest rev-parse HEAD` | native tests |
| Git source | AoE2ScenarioParser | `b763e2e37006bedab50c7d349b3ce24b9c2497f6` | scenario generation; upstream MIT | pinned submodule + requirements | `git -C third_party/AoE2ScenarioParser rev-parse HEAD` | scenario |
| Git source | RPFM | `fdde51aa9e6826afda1832d1b563b5f11125dc75` + patches | pack/RMV2 decoding; GPL-3 upstream | pinned submodule; see patch guide | commit + `cargo test` | extraction/export |
| Proprietary app | The Asset Editor | 0.78.0.0 observed | Required `RmvToGltfExporter` native `.anim`→glTF path | manually supplied; set `ROME2AOE2_ASSET_EDITOR` to `AssetEditor.exe`; never vendor | `(Get-Item $env:ROME2AOE2_ASSET_EDITOR).VersionInfo.FileVersion` | new animation conversion |
| Proprietary data/app | Total War: Rome II / Steam | user-owned, version not encoded | Needed only to extract source packs; not needed with fixtures | Steam; optional `ROME2AOE2_ROME2_DATA` | path contains game `.pack` files | extraction only |
| Proprietary data/app | AoE2 DE / Steam | user-owned | Needed only for installation/in-game tests and DAT source data | Steam; optional `ROME2AOE2_AOE2_PROFILE` | user profile path | game integration |
| Downloaded binary | DirectXTex/texconv encoder | project code discovers local executable where configured; exact distributable not established | Optional BC encoding path; redistribution not audited, so not vendored | official Microsoft release/manual configuration | executable help plus authoring tests | SLD compression |

No external Python package is required inside Blender beyond the NumPy bundled by Blender 5.2. If verification fails: `& $env:ROME2AOE2_BLENDER --background --python-expr "import ensurepip; ensurepip.bootstrap()"`, then `& '<Blender directory>\5.2\python\bin\python.exe' -m pip install numpy==2.3.4`. `bpy` and `mathutils` are Blender-provided and never belong in root requirements.

Active scripts use repository-relative paths or `ROME2AOE2_BLENDER`, `ROME2AOE2_ASSET_EDITOR`, `ROME2AOE2_ROME2_DATA`, and `ROME2AOE2_AOE2_PROFILE`. The only tracked old-user path is the immutable `provenance` annotation in the frozen Principes manifest; it identifies the source report and is not consulted as a filesystem dependency. Changing it would alter both verified manifest identities.

## Binary acquisition policy

No required executable is vendored in Git. Git 2.55.0, Python 3.14.6 x64, Blender 5.2.0 LTS (`fbe6228777e7`), Rust/Cargo 1.97.1, and optional CMake/.NET/7-Zip are manually supplied system installations from their official publishers (the setup guide uses pinned `winget` packages where available). RPFM is built from the pinned GPL-3.0 submodule plus the two hashed patches above. `rome2aoe2-pack` is built from repository source against that pinned dependency. Steam, Rome II, and AoE2 DE are proprietary manual installations. DirectXTex is optional and remains manual because no audited redistributable artifact is part of the required path.

Asset Editor remains manual because inspection established neither a redistribution grant suitable for committing its approximately 197 MB application directory nor a stable official versioned download URL with a published checksum. Expected version is file version `0.78.0.0`; configure the full executable path through `ROME2AOE2_ASSET_EDITOR`. It is required only to convert a new Rome II `.anim` through `RmvToGltfExporter`. Fixture validation, structural offline smoke, and the prepared `.blend` Blender FAST smoke do not require it. Do not place it in Git unless provenance, license, size policy, and SHA-256 are independently approved.
