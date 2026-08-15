[CmdletBinding()]
param(
    [string]$SourceX1 = 'build\cache\hastati-scale-static\x1\idle-direction-13-frame-000.png',
    [string]$SourceX2 = 'build\cache\hastati-scale-static\x2\idle-direction-13-frame-000.png',
    [string]$SourceDat = 'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat',
    [string]$TemplateScenario = 'test_data\EmptyMap.aoe2scenario',
    [string]$Texconv = 'build\tools\directxtex-may2026\texconv.exe',
    [int]$HotspotX1X = 100,
    [int]$HotspotX1Y = 122,
    [int]$HotspotX2X = 200,
    [int]$HotspotX2Y = 244
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$validation = Join-Path $root 'build\validation\hastati-static-sld'
$devTest = Join-Path $root 'build\dev-test\hastati'
$sourceX1Path = (Resolve-Path (Join-Path $root $SourceX1)).Path
$sourceX2Path = (Resolve-Path (Join-Path $root $SourceX2)).Path
$sourceDatPath = (Resolve-Path $SourceDat).Path
$templatePath = (Resolve-Path (Join-Path $root $TemplateScenario)).Path
$texconvPath = (Resolve-Path (Join-Path $root $Texconv)).Path

New-Item -ItemType Directory -Path $validation -Force | Out-Null
New-Item -ItemType Directory -Path $devTest -Force | Out-Null

Push-Location $root
try {
    python -B tests\AoE2StaticSLDQualityGateTests.py
    if ($LASTEXITCODE -ne 0) { throw 'Static SLD quality-gate tests failed' }
    python -B -m src.aoe2.generate_static_sld_quality_gate `
        --source-x1 $sourceX1Path --source-x2 $sourceX2Path `
        --texconv $texconvPath --output-root $validation `
        --hotspot-x1 $HotspotX1X $HotspotX1Y `
        --hotspot-x2 $HotspotX2X $HotspotX2Y
    if ($LASTEXITCODE -ne 0) { throw 'Static SLD generation or objective gate failed' }
    python -B src\aoe2\package_static_sld_quality_gate.py `
        --source-dat $sourceDatPath --source-scenario $templatePath `
        --sld-x1 (Join-Path $validation 'hastati-test_x1.sld') `
        --sld-x2 (Join-Path $validation 'hastati-test_x2.sld') `
        --output-root $devTest
    if ($LASTEXITCODE -ne 0) { throw 'Static SLD package generation failed' }
}
finally {
    Pop-Location
}

Write-Output "Validation: $validation"
Write-Output "Generated mod: $(Join-Path $devTest 'Rome2AoE2 Hastati Dev Test')"
Write-Output "Generated scenario: $(Join-Path $devTest 'Rome2AoE2HastatiDevTest.aoe2scenario')"
