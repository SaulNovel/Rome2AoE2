[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GeneratedMod,
    [Parameter(Mandatory = $true)][string]$GeneratedScenario,
    [Parameter(Mandatory = $true)][string]$Receipt,
    [switch]$ReplaceExisting,
    [string]$AoEProfile = 'C:\Users\sauln\Games\Age of Empires 2 DE\76561198088401383'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceMod = (Resolve-Path -LiteralPath $GeneratedMod).Path
$sourceScenario = (Resolve-Path -LiteralPath $GeneratedScenario).Path
$receiptPath = (Resolve-Path -LiteralPath $Receipt).Path
$modName = Split-Path -Leaf $sourceMod
$scenarioName = Split-Path -Leaf $sourceScenario
if (-not $modName.StartsWith('Rome2AoE2 ') -or -not $modName.EndsWith(' FAST Corpse Test')) { throw "Unsafe FAST corpse mod name: $modName" }
if (-not $scenarioName.StartsWith('Rome2AoE2') -or -not $scenarioName.EndsWith('FASTCorpseTest.aoe2scenario')) { throw "Unsafe FAST corpse scenario name: $scenarioName" }
$modsRoot = Join-Path $AoEProfile 'mods\local'; $scenarioRoot = Join-Path $AoEProfile 'resources\_common\scenario'
$destinationMod = Join-Path $modsRoot $modName; $destinationScenario = Join-Path $scenarioRoot $scenarioName
New-Item -ItemType Directory -Path $modsRoot -Force | Out-Null; New-Item -ItemType Directory -Path $scenarioRoot -Force | Out-Null
if (Test-Path -LiteralPath $destinationMod) {
    if (-not $ReplaceExisting) { throw "Refusing to overwrite existing FAST corpse test without -ReplaceExisting: $destinationMod" }
    Remove-Item -LiteralPath $destinationMod -Recurse -Force
}
Copy-Item -LiteralPath $sourceMod -Destination $destinationMod -Recurse
Copy-Item -LiteralPath $sourceScenario -Destination $destinationScenario -Force:$ReplaceExisting
$report = Join-Path (Split-Path -Parent $receiptPath) 'install-verification.json'
python -B (Join-Path $root 'src\aoe2\verify_manifest_dev_install.py') --receipt $receiptPath --mod $destinationMod --scenario $destinationScenario --report $report
if ($LASTEXITCODE -ne 0) { throw 'FAST corpse installation verification failed' }
Write-Output "Installed mod: $destinationMod"; Write-Output "Installed scenario: $destinationScenario"; Write-Output "Verification: $report"
