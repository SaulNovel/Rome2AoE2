[CmdletBinding()]
param(
    [string]$SourceDat = 'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat',
    [string]$TemplateScenario = 'test_data\EmptyMap.aoe2scenario',
    [string]$Texconv = 'build\tools\directxtex-may2026\texconv.exe'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$walkFrames = Join-Path $root 'build\cache\hastati-native-walk'
$walkShadows = Join-Path $root 'build\cache\hastati-native-walk-shadows'
$validation = Join-Path $root 'build\validation\hastati-native-walk'
$idleValidation = Join-Path $root 'build\validation\hastati-full-idle'
$devTest = Join-Path $root 'build\dev-test\hastati'
$sourceDatPath = (Resolve-Path $SourceDat).Path
$scenarioPath = (Resolve-Path (Join-Path $root $TemplateScenario)).Path
$texconvPath = (Resolve-Path (Join-Path $root $Texconv)).Path

Push-Location $root
try {
    python -B src\aoe2\generate_hastati_animation_sld.py `
        --animation walk --frames 23 --main-root $walkFrames --shadow-root $walkShadows `
        --texconv $texconvPath --output-root $validation --frame-duration (1.1 / 23) `
        --hotspot-x1 100 122 --hotspot-x2 200 244
    if ($LASTEXITCODE -ne 0) { throw 'Native walk SLD generation failed' }
    python -B src\aoe2\package_hastati_idle_walk_sld.py `
        --source-dat $sourceDatPath --source-scenario $scenarioPath `
        --idle-x1 (Join-Path $idleValidation 'hastati-idle_x1.sld') `
        --idle-x2 (Join-Path $idleValidation 'hastati-idle_x2.sld') `
        --walk-x1 (Join-Path $validation 'hastati-walk_x1.sld') `
        --walk-x2 (Join-Path $validation 'hastati-walk_x2.sld') `
        --output-root $devTest --walk-cycle-duration 1.1
    if ($LASTEXITCODE -ne 0) { throw 'Native idle/walk DAT package failed' }
}
finally { Pop-Location }

Write-Output "Validation: $validation"
Write-Output "Generated mod: $(Join-Path $devTest 'Rome2AoE2 Hastati Dev Test')"
