$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Keep the WiX/NuGet cache used by this build under D:.
$env:TEMP = Join-Path $PSScriptRoot ".build-temp"
$env:TMP = $env:TEMP
$env:NUGET_PACKAGES = Join-Path $PSScriptRoot ".build-cache\nuget"
New-Item -ItemType Directory -Force -Path $env:TEMP, $env:NUGET_PACKAGES | Out-Null

$payload = Join-Path $PSScriptRoot "release\ClipLink"
$output = Join-Path $PSScriptRoot "ClipLink-Setup.msi"
$wixDir = Join-Path $PSScriptRoot ".build-env\wix"
$wix = Join-Path $wixDir "wix.exe"
$wixVersion = "6.0.2"
$version = (Select-String -Path (Join-Path $PSScriptRoot "app_version.py") -Pattern 'APP_VERSION\s*=\s*"([0-9.]+)"').Matches.Groups[1].Value

if (-not (Test-Path (Join-Path $payload "ClipLink.exe") -PathType Leaf)) {
    throw "Release ausente. Execute build_windows.ps1 e package_release.ps1 primeiro."
}
if (-not (Test-Path $wix -PathType Leaf) -or (& $wix --version 2>$null) -notmatch "^$wixVersion") {
    New-Item -ItemType Directory -Force -Path $wixDir | Out-Null
    if (Test-Path $wix -PathType Leaf) { & dotnet tool uninstall wix --tool-path $wixDir }
    & dotnet tool install wix --tool-path $wixDir --version $wixVersion
    if ($LASTEXITCODE -ne 0) { throw "Não consegui instalar o WiX Toolset localmente." }
}

& $wix build (Join-Path $PSScriptRoot "ClipLink.wxs") `
    -d "AppVersion=$version" `
    -d "PayloadDir=$payload" `
    -o $output
if ($LASTEXITCODE -ne 0) { throw "O WiX não conseguiu gerar o MSI." }

$hash = (Get-FileHash $output -Algorithm SHA256).Hash.ToUpperInvariant()
Set-Content -Path (Join-Path $PSScriptRoot "ClipLink-Setup.msi.sha256") -Value "$hash  ClipLink-Setup.msi" -Encoding ascii
Write-Host "MSI criado: $output" -ForegroundColor Green
