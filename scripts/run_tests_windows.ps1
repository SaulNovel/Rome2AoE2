[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$TestTemp = Join-Path $Root 'build\test-tmp\unittest'
New-Item -ItemType Directory -Force -Path $TestTemp | Out-Null
$resolved = (Resolve-Path -LiteralPath $TestTemp).Path
if (-not $resolved.StartsWith((Join-Path $Root 'build'), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing unsafe test temporary path: $resolved"
}
$priorTemp = $env:TEMP; $priorTmp = $env:TMP
try {
    $env:TEMP = $resolved
    $env:TMP = $resolved
    & (Join-Path $Root '.venv\Scripts\python.exe') -m unittest discover -s tests -p '*Tests.py'
    exit $LASTEXITCODE
} finally {
    $env:TEMP = $priorTemp
    $env:TMP = $priorTmp
}
