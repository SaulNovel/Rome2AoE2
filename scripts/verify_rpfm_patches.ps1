[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

$expectedBaseCommit = 'fdde51aa9e6826afda1832d1b563b5f11125dc75'
$repositoryRoot = Split-Path -Parent $PSScriptRoot
$submodulePath = Join-Path $repositoryRoot 'third_party/rpfm'
$patchDirectory = Join-Path $repositoryRoot 'patches/rpfm'

if (-not (Test-Path -LiteralPath $submodulePath -PathType Container)) {
    throw "RPFM submodule is missing: $submodulePath. Run git submodule update --init --recursive first."
}

$actualBaseCommit = (& git -C $submodulePath rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $actualBaseCommit -ne $expectedBaseCommit) {
    throw "RPFM base commit mismatch. Expected $expectedBaseCommit; found $actualBaseCommit."
}

$patches = Get-ChildItem -LiteralPath $patchDirectory -Filter '*.patch' -File | Sort-Object Name
if ($patches.Count -eq 0) {
    throw "No managed RPFM patches found in $patchDirectory."
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

foreach ($patch in $patches) {
    if (-not (Test-RpfmPatchApplied $patch.FullName)) {
        throw "Managed patch '$($patch.Name)' is missing or incompatible with the current RPFM working tree."
    }
}

$temporaryDirectory = Join-Path ([System.IO.Path]::GetTempPath()) ("rome2aoe2-rpfm-verify-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $temporaryDirectory | Out-Null
try {
    $expectedPaths = @()
    foreach ($patch in $patches) {
        $patchPaths = @(& git -C $submodulePath apply --numstat $patch.FullName | ForEach-Object { ($_ -split "`t")[-1] })
        if ($LASTEXITCODE -ne 0 -or $patchPaths.Count -eq 0) {
            throw "Unable to determine paths managed by '$($patch.Name)'."
        }
        $expectedPaths += $patchPaths
    }
    $expectedPaths = $expectedPaths | Sort-Object -Unique

    foreach ($path in $expectedPaths) {
        $archivePath = Join-Path $temporaryDirectory ("source-" + [guid]::NewGuid() + '.tar')
        $archiveCommand = 'git -C "{0}" archive HEAD -- "{1}" > "{2}"' -f $submodulePath, $path, $archivePath
        & $env:ComSpec /d /c $archiveCommand
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to archive base RPFM source '$path' for managed-overlay verification."
        }
        & tar -xf $archivePath -C $temporaryDirectory
        if ($LASTEXITCODE -ne 0) {
            throw "Unable to materialize base RPFM source '$path' for managed-overlay verification."
        }
    }
    Push-Location $temporaryDirectory
    try {
        foreach ($patch in $patches) {
            & git apply --check $patch.FullName
            if ($LASTEXITCODE -ne 0) {
                throw "Managed patch '$($patch.Name)' cannot be applied to the expected RPFM base sources."
            }
            & git apply $patch.FullName
            if ($LASTEXITCODE -ne 0) {
                throw "Managed patch '$($patch.Name)' failed while constructing the expected overlay."
            }
        }
    }
    finally {
        Pop-Location
    }

    $actualPaths = @(& git -C $submodulePath diff --name-only HEAD)
    $unexpectedPaths = Compare-Object -ReferenceObject $expectedPaths -DifferenceObject $actualPaths | Where-Object SideIndicator -eq '=>'
    $missingPaths = Compare-Object -ReferenceObject $expectedPaths -DifferenceObject $actualPaths | Where-Object SideIndicator -eq '<='
    if ($unexpectedPaths -or $missingPaths) {
        throw "RPFM has unmanaged changes or a missing managed change. Expected paths: $($expectedPaths -join ', '); actual paths: $($actualPaths -join ', ')."
    }
    foreach ($path in $expectedPaths) {
        $actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $submodulePath $path)).Hash
        $expectedHash = (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $temporaryDirectory $path)).Hash
        if ($actualHash -ne $expectedHash) {
            throw "RPFM contains unmanaged edits in managed file '$path'."
        }
    }
}
finally {
    Remove-Item -LiteralPath $temporaryDirectory -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host "RPFM managed overlay verified at base commit $expectedBaseCommit."
