[CmdletBinding()]
param(
    [string]$AnimatedGltf = 'build\validation\hastati-gameplay\native-walk-control\sws_walk_162_cm.gltf',
    [string]$AssembledBlend = 'build\community_tool_investigation\complete-hastati-native-textured\complete-hastati-native-textured.blend',
    [string]$Blender = 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe'
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$gltf = (Resolve-Path (Join-Path $root $AnimatedGltf)).Path
$assembled = (Resolve-Path (Join-Path $root $AssembledBlend)).Path
$production = Join-Path $root 'build\cache\hastati-gameplay-actions\sws_walk_162_cm.native-production.blend'
$frames = Join-Path $root 'build\cache\hastati-native-walk'
$shadows = Join-Path $root 'build\cache\hastati-native-walk-shadows'
$validation = Join-Path $root 'build\validation\hastati-native-walk'
New-Item -ItemType Directory -Force $validation | Out-Null

Push-Location $root
try {
    & $Blender --background --python .\src\blender\build_hastati_native_animation.py -- `
        --animated-gltf $gltf --input-blend $assembled --output-blend $production `
        --report (Join-Path $validation 'native-production-build.json')
    if ($LASTEXITCODE -ne 0) { throw 'Native Action production build failed' }
    & $Blender --background --python .\src\blender\render_final_hastati_idle.py -- `
        --input-blend $production --output-dir $frames `
        --report (Join-Path $validation 'render-report.json') --animation-name walk `
        --directions all --frames native-keys --master-size 800 `
        --orthographic-scale 7.27480212108078 --camera-target-z 0.8503072261810303
    if ($LASTEXITCODE -ne 0) { throw 'Native walk colour render failed' }
    & $Blender --background --python .\src\blender\render_hastati_shadow_proof.py -- `
        --input-blend $production --output-root $shadows `
        --report (Join-Path $validation 'shadow-render-report.json') --animation-name walk `
        --directions all --frames native-keys --master-size 800 `
        --orthographic-scale 7.27480212108078 --camera-target-z 0.8503072261810303
    if ($LASTEXITCODE -ne 0) { throw 'Native walk shadow render failed' }
}
finally { Pop-Location }

Write-Output "Native production blend: $production"
Write-Output "Colour frames: $frames"
Write-Output "Shadow frames: $shadows"
