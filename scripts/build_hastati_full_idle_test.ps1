[CmdletBinding()]
param(
    [string]$FramesRoot = 'build\cache\hastati-full-idle',
    [string]$SourceDat = 'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat',
    [string]$TemplateScenario = 'test_data\EmptyMap.aoe2scenario',
    [string]$Texconv = 'build\tools\directxtex-may2026\texconv.exe'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$frames = (Resolve-Path (Join-Path $root $FramesRoot)).Path
$sourceDatPath = (Resolve-Path $SourceDat).Path
$template = (Resolve-Path (Join-Path $root $TemplateScenario)).Path
$texconvPath = (Resolve-Path (Join-Path $root $Texconv)).Path
$validation = Join-Path $root 'build\validation\hastati-full-idle'
$devTest = Join-Path $root 'build\dev-test\hastati'
New-Item -ItemType Directory -Path $validation -Force | Out-Null
New-Item -ItemType Directory -Path $devTest -Force | Out-Null

Push-Location $root
try {
    python -B -m src.aoe2.generate_full_idle_sld `
        --frames-root $frames --texconv $texconvPath --output-root $validation
    if ($LASTEXITCODE -ne 0) { throw 'Full-idle SLD generation or offline validation failed' }
    python -B src\aoe2\package_full_idle_sld.py `
        --source-dat $sourceDatPath --source-scenario $template `
        --sld-x1 (Join-Path $validation 'hastati-idle_x1.sld') `
        --sld-x2 (Join-Path $validation 'hastati-idle_x2.sld') `
        --output-root $devTest
    if ($LASTEXITCODE -ne 0) { throw 'Full-idle stable dev package generation failed' }
}
finally {
    Pop-Location
}

Write-Output "Validation: $validation"
Write-Output "Generated mod: $(Join-Path $devTest 'Rome2AoE2 Hastati Dev Test')"
Write-Output "Generated scenario: $(Join-Path $devTest 'Rome2AoE2HastatiDevTest.aoe2scenario')"
