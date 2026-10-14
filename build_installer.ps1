$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Keep installer build caches and temporary files inside the D: project.
$env:TEMP = Join-Path $PSScriptRoot ".build-temp"
$env:TMP = $env:TEMP
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot ".build-cache\pyinstaller"
New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PYINSTALLER_CONFIG_DIR | Out-Null

$buildEnv = Join-Path $PSScriptRoot ".build-env"
$python = Join-Path $buildEnv "Scripts\python.exe"
$payload = Join-Path $PSScriptRoot "release\ClipLink"
$icon = Join-Path $PSScriptRoot "assets\cliplink.ico"
$outputDir = $PSScriptRoot
$workDir = Join-Path $PSScriptRoot "build-installer"

if (-not (Test-Path $python -PathType Leaf)) { throw "Ambiente de build ausente. Execute build_windows.ps1 primeiro." }
if (-not (Test-Path (Join-Path $payload "ClipLink.exe") -PathType Leaf)) { throw "Release ausente. Execute package_release.ps1 primeiro." }

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "ClipLink-Setup",
    "--distpath", $outputDir,
    "--workpath", $workDir,
    "--specpath", $workDir,
    "--icon", $icon,
    "--add-data", "$payload;payload",
    "installer_app.py"
)

& $python -m PyInstaller @pyiArgs
if ($LASTEXITCODE -ne 0) { throw "Não consegui gerar o instalador do ClipLink." }

$setup = Join-Path $PSScriptRoot "ClipLink-Setup.exe"
$hash = (Get-FileHash $setup -Algorithm SHA256).Hash.ToUpperInvariant()
Set-Content -Path (Join-Path $PSScriptRoot "ClipLink-Setup.exe.sha256") -Value "$hash  ClipLink-Setup.exe" -Encoding ascii
Write-Host "Instalador criado: $setup" -ForegroundColor Green
