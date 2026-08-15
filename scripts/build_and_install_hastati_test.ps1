[CmdletBinding()]
param(
    [string]$SourceX1 = 'build\cache\hastati-scale-static\x1\idle-direction-13-frame-000.png',
    [string]$SourceX2 = 'build\cache\hastati-scale-static\x2\idle-direction-13-frame-000.png',
    [string]$AoEProfile = 'C:\Users\sauln\Games\Age of Empires 2 DE\76561198088401383',
    [int]$HotspotX1X = 100,
    [int]$HotspotX1Y = 122,
    [int]$HotspotX2X = 200,
    [int]$HotspotX2Y = 244
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'build_hastati_static_test.ps1') -SourceX1 $SourceX1 -SourceX2 $SourceX2 `
    -HotspotX1X $HotspotX1X -HotspotX1Y $HotspotX1Y -HotspotX2X $HotspotX2X -HotspotX2Y $HotspotX2Y
if ($LASTEXITCODE -ne 0) { throw 'Static test build failed' }
& (Join-Path $PSScriptRoot 'install_hastati_test.ps1') `
    -GeneratedMod (Join-Path $root 'build\dev-test\hastati\Rome2AoE2 Hastati Dev Test') `
    -GeneratedScenario (Join-Path $root 'build\dev-test\hastati\Rome2AoE2HastatiDevTest.aoe2scenario') `
    -AoEProfile $AoEProfile
