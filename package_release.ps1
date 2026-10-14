$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$releaseRoot = Join-Path $PSScriptRoot "release"
$releaseDir = Join-Path $releaseRoot "ClipLink"
$exe = Join-Path $PSScriptRoot "dist\ClipLink.exe"

if (-not (Test-Path $exe -PathType Leaf)) {
    throw "Executável ausente. Execute build_windows.ps1 antes de empacotar a release."
}

New-Item -ItemType Directory -Force -Path $releaseDir | Out-Null
Copy-Item $exe (Join-Path $releaseDir "ClipLink.exe") -Force
Copy-Item (Join-Path $PSScriptRoot "README.md") (Join-Path $releaseDir "README.md") -Force
Copy-Item (Join-Path $PSScriptRoot "CHANGELOG.md") (Join-Path $releaseDir "CHANGELOG.md") -Force
Copy-Item (Join-Path $PSScriptRoot "Criar_Atalho.vbs") (Join-Path $releaseDir "Criar_Atalho.vbs") -Force
Copy-Item (Join-Path $PSScriptRoot "Iniciar_Silencioso.vbs") (Join-Path $releaseDir "Iniciar_Silencioso.vbs") -Force
Copy-Item (Join-Path $PSScriptRoot "start_windows.bat") (Join-Path $releaseDir "start_windows.bat") -Force

$assetsDir = Join-Path $releaseDir "assets"
New-Item -ItemType Directory -Force -Path $assetsDir | Out-Null
Copy-Item (Join-Path $PSScriptRoot "assets\cliplink.ico") (Join-Path $assetsDir "cliplink.ico") -Force

$toolsSource = Join-Path $PSScriptRoot "tools"
$optionalTools = @("ffmpeg.exe", "ffprobe.exe", "node.exe")
$availableTools = @($optionalTools | Where-Object { Test-Path (Join-Path $toolsSource $_) -PathType Leaf })
if ($availableTools.Count -gt 0) {
    $toolsDir = Join-Path $releaseDir "tools"
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    foreach ($tool in $availableTools) {
        Copy-Item (Join-Path $toolsSource $tool) (Join-Path $toolsDir $tool) -Force
    }
}

$hash = (Get-FileHash (Join-Path $releaseDir "ClipLink.exe") -Algorithm SHA256).Hash.ToUpperInvariant()
Set-Content -Path (Join-Path $releaseDir "ClipLink.exe.sha256") -Value "$hash  ClipLink.exe" -Encoding ascii

Write-Host "Release pronta: $releaseDir" -ForegroundColor Green
Write-Host "FFmpeg/Node incluídos: $($availableTools.Count -gt 0)"
