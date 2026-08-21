[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$GeneratedMod,

    [Parameter(Mandatory = $true)]
    [string]$GeneratedScenario,

    [string]$AoEProfile = 'C:\Users\sauln\Games\Age of Empires 2 DE\76561198088401383'
)

$ErrorActionPreference = 'Stop'
$stableModName = 'Rome2AoE2 Hastati Dev Test'
$stableScenarioName = 'Rome2AoE2HastatiDevTest.aoe2scenario'
$sourceMod = (Resolve-Path -LiteralPath $GeneratedMod).Path
$sourceScenario = (Resolve-Path -LiteralPath $GeneratedScenario).Path

if (-not (Test-Path -LiteralPath $sourceMod -PathType Container)) {
    throw "Generated mod directory is missing: $sourceMod"
}
if (-not (Test-Path -LiteralPath $sourceScenario -PathType Leaf)) {
    throw "Generated scenario is missing: $sourceScenario"
}

$requiredRelative = @(
    'info.json',
    'resources\_common\dat\empires2_x2_p1.dat',
    'resources\_common\drs\graphics\rome2aoe2_hastati_test_x1.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_test_x2.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_walk_x1.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_walk_x2.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_attack_x1.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_attack_x2.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_death_x1.sld',
    'resources\_common\drs\graphics\rome2aoe2_hastati_death_x2.sld'
)
foreach ($relative in $requiredRelative) {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceMod $relative) -PathType Leaf)) {
        throw "Generated mod is incomplete; missing $relative"
    }
}

$modsRoot = Join-Path $AoEProfile 'mods\local'
$scenarioRoot = Join-Path $AoEProfile 'resources\_common\scenario'
$destinationMod = Join-Path $modsRoot $stableModName
$destinationScenario = Join-Path $scenarioRoot $stableScenarioName
New-Item -ItemType Directory -Path $modsRoot -Force | Out-Null
New-Item -ItemType Directory -Path $scenarioRoot -Force | Out-Null

# The only recursive replacement permitted here is our exact stable dev folder.
if ((Split-Path -Leaf $destinationMod) -ne $stableModName) {
    throw "Refusing unsafe mod destination: $destinationMod"
}
if (Test-Path -LiteralPath $destinationMod) {
    Remove-Item -LiteralPath $destinationMod -Recurse -Force
}
Copy-Item -LiteralPath $sourceMod -Destination $destinationMod -Recurse
Copy-Item -LiteralPath $sourceScenario -Destination $destinationScenario -Force

foreach ($relative in $requiredRelative) {
    $installed = Join-Path $destinationMod $relative
    if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
        throw "Installation verification failed: $installed"
    }
}
if (-not (Test-Path -LiteralPath $destinationScenario -PathType Leaf)) {
    throw "Installation verification failed: $destinationScenario"
}

Write-Output "Installed mod: $destinationMod"
Write-Output "Installed scenario: $destinationScenario"
foreach ($relative in $requiredRelative) {
    Write-Output "Verified: $(Join-Path $destinationMod $relative)"
}
Write-Output "Verified: $destinationScenario"
