[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$GeneratedMod,
    [Parameter(Mandatory = $true)][string]$GeneratedScenario,
    [Parameter(Mandatory = $true)][string]$Receipt,
    [string]$AoEProfile = 'C:\Users\sauln\Games\Age of Empires 2 DE\76561198088401383'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sourceMod = (Resolve-Path -LiteralPath $GeneratedMod).Path
$sourceScenario = (Resolve-Path -LiteralPath $GeneratedScenario).Path
$receiptPath = (Resolve-Path -LiteralPath $Receipt).Path
$modName = Split-Path -Leaf $sourceMod
$scenarioName = Split-Path -Leaf $sourceScenario
if (-not $modName.StartsWith('Rome2AoE2 ') -or -not $modName.EndsWith(' Dev Test')) { throw "Unsafe generated mod name: $modName" }
if (-not $scenarioName.StartsWith('Rome2AoE2') -or -not $scenarioName.EndsWith('DevTest.aoe2scenario')) { throw "Unsafe scenario name: $scenarioName" }
$modsRoot = Join-Path $AoEProfile 'mods\local'; $scenarioRoot = Join-Path $AoEProfile 'resources\_common\scenario'
$destinationMod = Join-Path $modsRoot $modName; $destinationScenario = Join-Path $scenarioRoot $scenarioName
if ((Split-Path -Parent $destinationMod) -ne $modsRoot -or (Split-Path -Leaf $destinationMod) -ne $modName) { throw "Unsafe mod destination: $destinationMod" }
New-Item -ItemType Directory -Path $modsRoot -Force | Out-Null; New-Item -ItemType Directory -Path $scenarioRoot -Force | Out-Null
if (Test-Path -LiteralPath $destinationMod) { Remove-Item -LiteralPath $destinationMod -Recurse -Force }
Copy-Item -LiteralPath $sourceMod -Destination $destinationMod -Recurse
Copy-Item -LiteralPath $sourceScenario -Destination $destinationScenario -Force
$receiptDocument = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
$statusPath = Join-Path $AoEProfile 'mods\mod-status.json'; $statusModPath = "local//$modName"
$activationArgs = @('-B',(Join-Path $root 'src\aoe2\activate_local_test_mod.py'),'--status',$statusPath,'--target',$receiptDocument.mod_title,'--target-path',$statusModPath,'--disable-local-prefix','Rome2AoE2')
foreach ($conflict in $receiptDocument.conflicting_mod_titles) { $activationArgs += @('--disable',$conflict) }
python @activationArgs
if ($LASTEXITCODE -ne 0) { throw 'Generic dev data-mod activation failed' }
$report = Join-Path (Split-Path -Parent $receiptPath) 'install-verification.json'
python -B (Join-Path $root 'src\aoe2\verify_manifest_dev_install.py') --receipt $receiptPath --mod $destinationMod --scenario $destinationScenario --report $report --status $statusPath --mods-root (Join-Path $AoEProfile 'mods') --target-status-path $statusModPath
if ($LASTEXITCODE -ne 0) { throw 'Generic dev integration verification failed' }
Write-Output "Installed mod: $destinationMod"; Write-Output "Installed scenario: $destinationScenario"; Write-Output "Verification: $report"
