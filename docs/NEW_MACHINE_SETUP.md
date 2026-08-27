# New Windows machine setup

Use Windows 10/11 x64 and PowerShell. Clone branch `generic-unit-converter`, then run commands from the repository root. Install commands may require an Administrator terminal; close and reopen PowerShell after Git, Python, Rust, or Build Tools changes so PATH refreshes.

## Conversion/render development (no games required)

```powershell
winget install --exact --id Git.Git --version 2.55.0
winget install --exact --id Python.Python.3.14 --version 3.14.6
winget install --exact --id Rustlang.Rustup
winget install --exact --id Kitware.CMake --version 4.4.0
git --version
py -3.14 --version
rustc --version
cmake --version
```

If a pinned winget version is unavailable, install that exact release from the vendor's official archive. Blender output is version-sensitive: install Blender **5.2.0 LTS** from Blender.org (or `winget show BlenderFoundation.Blender.LTS`, accepting only 5.2.0), then configure its location without assuming a username:

```powershell
[Environment]::SetEnvironmentVariable('ROME2AOE2_BLENDER','C:\Program Files\Blender Foundation\Blender 5.2\blender.exe','User')
& $env:ROME2AOE2_BLENDER --version
```

Obtain Asset Editor 0.78.0.0 through its official/community distribution and set `ROME2AOE2_ASSET_EDITOR` to the full path of `AssetEditor.exe`. Its approximately 197 MB inspected application directory had no established redistribution grant or stable official versioned URL with a published checksum, so it is not in Git and is not downloaded by bootstrap. Verify it with `(Get-Item $env:ROME2AOE2_ASSET_EDITOR).VersionInfo.FileVersion`. Only new `.anim` conversion through `RmvToGltfExporter` requires it.

```powershell
git submodule update --init -- third_party/googletest third_party/AoE2ScenarioParser
py -3.14 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_windows.ps1 -SkipInstall
```

Python 3.14.6 is the supported baseline because all pinned packages publish CPython 3.14 Windows wheels and the complete suite was executed with that version. The audited interpreter is the official PSF 64-bit build. On the source machine, `ensurepip` 26.1.2 fails only because the execution sandbox denies writes inside Python-created temporary directories. Bootstrap first uses normal `venv`; if that fails but the official base installation has pip, it creates `--without-pip` and seeds the environment with `py -3.14 -m pip --python .venv`. Do not use `get-pip.py`. If both routes fail, repair/reinstall Python 3.14.6 from python.org or winget with pip and venv enabled.

The pinned Blender is the stable Windows Blender 5.2.0 LTS release: branch `blender-v5.2-release`, build hash `fbe6228777e7`, build date 2026-07-14. Doctor rejects another major/minor/patch version.

Bootstrap initializes the exact RPFM gitlink and applies only the two reviewed semantic patches when the checkout is clean; it fails on a base mismatch and never normalizes host line endings. See `docs/THIRD_PARTY_PATCHES.md` for replay/build validation. Microsoft Visual Studio 2022 Build Tools with the Desktop development with C++ workload is optional for CMake-native tests (`winget install Microsoft.VisualStudio.2022.BuildTools` then select that workload). .NET SDK 10 is optional for Asset Editor source work (`winget install Microsoft.DotNet.SDK.10`).

## Import private fixtures

Copy `rome2aoe2-offline-fixtures.zip` via USB or another private, non-public mechanism into any local directory. Do not upload it. From the repo:

```powershell
.venv\Scripts\python.exe scripts\import_offline_fixtures.py 'E:\private\rome2aoe2-offline-fixtures.zip'
.venv\Scripts\python.exe scripts\verify_offline_fixtures.py
.venv\Scripts\python.exe scripts\doctor.py --fixtures
.venv\Scripts\python.exe scripts\smoke_offline.py
.venv\Scripts\python.exe scripts\run_blender_fast_smoke.py
```

The first two stages—conversion/render development—work from `data/local-fixtures` without Rome II. The structural smoke validates the complete hashed closure and native animation identities. The prepared `.blend` FAST/x2 smoke also runs without Asset Editor; only conversion of a new `.anim` requires it. These checks deliberately avoid FULL rendering, SLD/DAT changes, and installation. Exact render hashes are not portable across GPU drivers, so verify dimensions, RGBA alpha, direction identity, and non-empty bounds.

Run the full suite with process-local repository temporary directories:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_tests_windows.ps1
```

This script restores the caller's `TEMP`/`TMP` values and never changes global environment variables.

## Source extraction (Rome II required)

Install Steam and Total War: Rome II only on a licensed machine. Set `ROME2AOE2_ROME2_DATA` to its `data` directory and pass that value to commands accepting `--game-data`. Build the helper with `cargo build --locked --release --manifest-path tools/rome2_pack/Cargo.toml`. Never copy game files into tracked directories.

## In-game testing (AoE2 DE required)

Install AoE2 DE through Steam only when testing SLD/DAT/scenarios. Set `ROME2AOE2_AOE2_PROFILE` to the numeric Steam profile directory and pass it to install scripts. Bootstrap never installs or modifies either game.
