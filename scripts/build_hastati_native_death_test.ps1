[CmdletBinding()]
param(
    [string]$SourceDat = 'C:\Program Files (x86)\Steam\steamapps\common\AoE2DE\resources\_common\dat\empires2_x2_p1.dat',
    [string]$TemplateScenario = 'test_data\EmptyMap.aoe2scenario',
    [string]$Texconv = 'build\tools\directxtex-may2026\texconv.exe'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$deathFrames = Join-Path $root 'build\cache\hastati-native-death'
$deathShadows = Join-Path $root 'build\cache\hastati-native-death-shadows'
$validation = Join-Path $root 'build\validation\hastati-native-death'
$idleValidation = Join-Path $root 'build\validation\hastati-full-idle'
$walkValidation = Join-Path $root 'build\validation\hastati-native-walk'
$attackValidation = Join-Path $root 'build\validation\hastati-native-attack'
$devTest = Join-Path $root 'build\dev-test\hastati'
$sourceDatPath = (Resolve-Path $SourceDat).Path
$scenarioPath = (Resolve-Path (Join-Path $root $TemplateScenario)).Path
$texconvPath = (Resolve-Path (Join-Path $root $Texconv)).Path

Push-Location $root
try {
    python -B src\aoe2\generate_hastati_animation_sld.py `
        --animation death --frames 33 --main-root $deathFrames --shadow-root $deathShadows `
        --texconv $texconvPath --output-root $validation --frame-duration (1.0 / 15.0) `
        --hotspot-x1 100 122 --hotspot-x2 200 244
    if ($LASTEXITCODE -ne 0) { throw 'Native death SLD generation failed' }
    python -B src\aoe2\package_hastati_idle_walk_sld.py `
        --source-dat $sourceDatPath --source-scenario $scenarioPath `
        --idle-x1 (Join-Path $idleValidation 'hastati-idle_x1.sld') `
        --idle-x2 (Join-Path $idleValidation 'hastati-idle_x2.sld') `
        --walk-x1 (Join-Path $walkValidation 'hastati-walk_x1.sld') `
        --walk-x2 (Join-Path $walkValidation 'hastati-walk_x2.sld') `
        --attack-x1 (Join-Path $attackValidation 'hastati-attack_x1.sld') `
        --attack-x2 (Join-Path $attackValidation 'hastati-attack_x2.sld') `
        --death-x1 (Join-Path $validation 'hastati-death_x1.sld') `
        --death-x2 (Join-Path $validation 'hastati-death_x2.sld') `
        --output-root $devTest --walk-cycle-duration 1.1 --attack-cycle-duration 1.3 `
        --death-frame-duration (1.0 / 15.0)
    if ($LASTEXITCODE -ne 0) { throw 'Native idle/walk/attack/death DAT package failed' }
}
finally { Pop-Location }

Write-Output "Validation: $validation"
Write-Output "Generated mod: $(Join-Path $devTest 'Rome2AoE2 Hastati Dev Test')"
