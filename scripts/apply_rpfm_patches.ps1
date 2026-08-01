[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$expectedBaseCommit = 'fdde51aa9e6826afda1832d1b563b5f11125dc75'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$submodulePath = Join-Path $repositoryRoot 'third_party/rpfm'
$patchDirectory = Join-Path $repositoryRoot 'patches/rpfm'

function Invoke-RpfmGit {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & git -C $submodulePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git -C third_party/rpfm $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Test-RpfmPatchApplied {
    param([string]$PatchPath)
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & git -C $submodulePath apply --reverse --check $PatchPath 2>$null
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $previousErrorActionPreference
    return $exitCode -eq 0
}

if (-not (Test-Path -LiteralPath $submodulePath -PathType Container)) {
    throw "RPFM submodule is missing: $submodulePath. Run git submodule update --init --recursive first."
}

$actualBaseCommit = (& git -C $submodulePath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualBaseCommit -ne $expectedBaseCommit) {
    throw "RPFM base commit mismatch. Expected $expectedBaseCommit; found $actualBaseCommit. Refusing to apply managed patches."
}

$patches = Get-ChildItem -LiteralPath $patchDirectory -Filter '*.patch' -File | Sort-Object Name
if ($patches.Count -eq 0) {
    throw "No managed RPFM patches found in $patchDirectory."
}

foreach ($patch in $patches) {
    if (Test-RpfmPatchApplied $patch.FullName) {
        Write-Host "Already applied: $($patch.Name)"
        continue
    }

    & git -C $submodulePath apply --check $patch.FullName
    if ($LASTEXITCODE -ne 0) {
        throw "Patch '$($patch.Name)' is incompatible with third_party/rpfm. No changes were applied."
    }

    Invoke-RpfmGit apply $patch.FullName
    Write-Host "Applied: $($patch.Name)"
}

Write-Host 'Managed RPFM patches are applied. third_party/rpfm is intentionally dirty; run scripts/verify_rpfm_patches.ps1 before building.'
