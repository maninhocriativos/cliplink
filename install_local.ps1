$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$source = Join-Path $PSScriptRoot "release\ClipLink"
$destination = Join-Path $PSScriptRoot "ClipLink-Instalado"
$setup = Join-Path $PSScriptRoot "ClipLink-Setup.exe"

if (-not (Test-Path (Join-Path $source "ClipLink.exe") -PathType Leaf)) {
    throw "A release não existe. Execute package_release.ps1 antes de instalar."
}

if (Test-Path $setup -PathType Leaf) {
    & $setup --silent --target $destination
    if ($null -ne $LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "O instalador não conseguiu atualizar a cópia local." }
} else {
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    Copy-Item (Join-Path $source "*") $destination -Recurse -Force
}

$hash = (Get-FileHash (Join-Path $destination "ClipLink.exe") -Algorithm SHA256).Hash.ToUpperInvariant()
$declared = (Get-Content (Join-Path $destination "ClipLink.exe.sha256")).Split(' ')[0].ToUpperInvariant()
if ($hash -ne $declared) {
    throw "A instalação falhou na validação do checksum do executável."
}

Write-Host "ClipLink instalado na pasta:" -ForegroundColor Green
Write-Host $destination
Write-Host "Execute ClipLink.exe ou use Criar_Atalho.vbs para criar um atalho na área de trabalho."
