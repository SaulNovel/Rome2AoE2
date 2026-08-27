[CmdletBinding()]
param([string]$AoEProfile = $env:ROME2AOE2_AOE2_PROFILE)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'build_hastati_native_attack_test.ps1')
if ($LASTEXITCODE -ne 0) { throw 'Native attack build failed' }
& (Join-Path $PSScriptRoot 'install_hastati_test.ps1') `
    -GeneratedMod (Join-Path $root 'build\dev-test\hastati\Rome2AoE2 Hastati Dev Test') `
    -GeneratedScenario (Join-Path $root 'build\dev-test\hastati\Rome2AoE2HastatiDevTest.aoe2scenario') `
    -AoEProfile $AoEProfile
if ($LASTEXITCODE -ne 0) { throw 'Native attack installation failed' }
