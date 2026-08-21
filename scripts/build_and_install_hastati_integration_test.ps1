[CmdletBinding()]
param([string]$AoEProfile = 'C:\Users\sauln\Games\Age of Empires 2 DE\76561198088401383')

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$devTest = Join-Path $root 'build\dev-test\hastati'
$sourceMod = Join-Path $devTest 'Rome2AoE2 Hastati Dev Test'
$scenario = Join-Path $devTest 'Rome2AoE2HastatiDevTest.aoe2scenario'
$report = Join-Path $root 'build\validation\hastati-integration-test'
$installedMod = Join-Path $AoEProfile 'mods\local\Rome2AoE2 Hastati Dev Test'
$installedScenario = Join-Path $AoEProfile 'resources\_common\scenario\Rome2AoE2HastatiDevTest.aoe2scenario'

$assetNames = @(
    'rome2aoe2_hastati_test_x1.sld', 'rome2aoe2_hastati_test_x2.sld',
    'rome2aoe2_hastati_walk_x1.sld', 'rome2aoe2_hastati_walk_x2.sld',
    'rome2aoe2_hastati_attack_x1.sld', 'rome2aoe2_hastati_attack_x2.sld',
    'rome2aoe2_hastati_death_x1.sld', 'rome2aoe2_hastati_death_x2.sld'
)
$before = @{}
foreach ($name in $assetNames) {
    $path = Join-Path $installedMod "resources\_common\drs\graphics\$name"
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Installed approved asset is missing: $path" }
    $before[$name] = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
}

Push-Location $root
try {
    python -B src\aoe2\generate_hastati_integration_scenario.py `
        --template test_data\EmptyMap.aoe2scenario --output $scenario `
        --report (Join-Path $report 'scenario-report.json')
    if ($LASTEXITCODE -ne 0) { throw 'Hastati integration scenario generation failed' }
    & (Join-Path $PSScriptRoot 'install_hastati_test.ps1') `
        -GeneratedMod $sourceMod -GeneratedScenario $scenario -AoEProfile $AoEProfile
    if ($LASTEXITCODE -ne 0) { throw 'Hastati integration installation failed' }
    foreach ($name in $assetNames) {
        $path = Join-Path $installedMod "resources\_common\drs\graphics\$name"
        $after = (Get-FileHash -Algorithm SHA256 -LiteralPath $path).Hash
        if ($after -ne $before[$name]) { throw "Approved installed asset hash changed: $name" }
    }
    python -B src\aoe2\verify_hastati_integration_install.py `
        --mod $installedMod --scenario $installedScenario --source-mod $sourceMod `
        --report (Join-Path $report 'install-verification.json')
    if ($LASTEXITCODE -ne 0) { throw 'Hastati integration pre-game verification failed' }
}
finally { Pop-Location }

Write-Output "Integration mod: $installedMod"
Write-Output "Integration scenario: $installedScenario"
Write-Output 'Approved idle/walk/attack/death x1/x2 hashes: unchanged'
