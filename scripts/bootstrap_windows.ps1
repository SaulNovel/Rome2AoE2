[CmdletBinding()]
param([string]$FixtureArchive, [switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Set-Location $Root
function Need([string]$Name, [string]$Install) {
    if (Get-Command $Name -ErrorAction SilentlyContinue) { Write-Host "PASS $Name" }
    else { Write-Warning "Missing $Name. Install: $Install" }
}
Need git 'winget install --exact --id Git.Git --version 2.55.0'
Need py 'winget install --exact --id Python.Python.3.14 --version 3.14.6'
Need cargo 'winget install --exact --id Rustlang.Rustup'
Need cmake 'winget install --exact --id Kitware.CMake --version 4.4.0'
$Blender = if ($env:ROME2AOE2_BLENDER) { $env:ROME2AOE2_BLENDER } else { 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' }
if (-not (Test-Path -LiteralPath $Blender)) { Write-Warning 'Install Blender 5.2.0 LTS, then set ROME2AOE2_BLENDER to blender.exe.' }
git submodule update --init -- third_party/googletest third_party/AoE2ScenarioParser third_party/rpfm
$RpfmExpected = 'fdde51aa9e6826afda1832d1b563b5f11125dc75'
$RpfmActual = git -C third_party/rpfm rev-parse HEAD
if ($RpfmActual -ne $RpfmExpected) { throw "RPFM base mismatch: $RpfmActual" }
$RpfmDirty = git -C third_party/rpfm status --porcelain
if (-not $RpfmDirty) {
    git -C third_party/rpfm apply --check ..\..\patches\rpfm\0001-support-rome2-default-layout-materials.patch
    git -C third_party/rpfm apply ..\..\patches\rpfm\0001-support-rome2-default-layout-materials.patch
    git -C third_party/rpfm apply --check ..\..\patches\rpfm\0002-preserve-rmv-pivots-and-serialize-gltf-vertices.patch
    git -C third_party/rpfm apply ..\..\patches\rpfm\0002-preserve-rmv-pivots-and-serialize-gltf-vertices.patch
} else { Write-Host 'RPFM is already dirty; doctor will require the exact semantic overlay hashes.' }
if (-not (Test-Path .venv\Scripts\python.exe)) {
    py -3.14 -m venv .venv
    if ($LASTEXITCODE -ne 0) {
        Write-Warning 'venv ensurepip failed; creating without pip and seeding with the base interpreter pip.'
        py -3.14 -m venv --clear --without-pip .venv
        py -3.14 -m pip --python .venv install --upgrade pip
    }
}
if (-not $SkipInstall) {
    .venv\Scripts\python.exe -m pip install --upgrade pip
    .venv\Scripts\python.exe -m pip install -r requirements.txt
}
if ($FixtureArchive) { .venv\Scripts\python.exe scripts\import_offline_fixtures.py $FixtureArchive }
.venv\Scripts\python.exe scripts\doctor.py --fixtures
