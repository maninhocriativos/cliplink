$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# Keep build caches and temporary files inside the D: project folder.
$env:TEMP = Join-Path $PSScriptRoot ".build-temp"
$env:TMP = $env:TEMP
$env:PIP_CACHE_DIR = Join-Path $PSScriptRoot ".build-cache\pip"
$env:PYINSTALLER_CONFIG_DIR = Join-Path $PSScriptRoot ".build-cache\pyinstaller"
New-Item -ItemType Directory -Force -Path $env:TEMP, $env:PIP_CACHE_DIR, $env:PYINSTALLER_CONFIG_DIR | Out-Null

if (-not (Test-Path (Join-Path $PSScriptRoot "desktop_app.py")) -or
    -not (Test-Path (Join-Path $PSScriptRoot "url_safety.py"))) {
    throw "Arquivos do aplicativo ausentes. Extraia o pacote completo com 'Extrair tudo' e execute o build dentro da pasta extraída."
}

$pythonCommand = $null
$pythonCommandArgs = @()
$pythonVersion = $null

$pythonLauncher = Get-Command py -ErrorAction SilentlyContinue
if ($pythonLauncher) {
    try {
        $probe = (& py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
    } catch {
        $probe = $null
    }
    if ($LASTEXITCODE -eq 0 -and $probe) {
        $pythonCommand = "py"
        $pythonCommandArgs = @("-3")
        $pythonVersion = $probe
    }
}

if (-not $pythonCommand) {
    $pythonExe = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonExe) {
        try {
            $probe = (& $pythonExe.Source -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null).Trim()
        } catch {
            $probe = $null
        }
        if ($LASTEXITCODE -eq 0 -and $probe) {
            $pythonCommand = $pythonExe.Source
            $pythonVersion = $probe
        }
    }
}

if (-not $pythonCommand -and (Test-Path (Join-Path $PSScriptRoot ".venv\Scripts\python.exe"))) {
    $pythonCommand = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
    $pythonVersion = (& $pythonCommand -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
}

if (-not $pythonCommand) {
    throw "Instale o Python 3.10+ para Windows e marque 'Add Python to PATH'."
}

$versionParts = $pythonVersion.Split('.')
if ([int]$versionParts[0] -lt 3 -or ([int]$versionParts[0] -eq 3 -and [int]$versionParts[1] -lt 10)) {
    throw "O ClipLink exige Python 3.10 ou superior. Encontrado: Python $pythonVersion."
}

$buildEnv = Join-Path $PSScriptRoot ".build-env"
if (-not (Test-Path (Join-Path $buildEnv "Scripts/python.exe"))) {
    & $pythonCommand @pythonCommandArgs -m venv $buildEnv
    if ($LASTEXITCODE -ne 0) { throw "Não consegui criar o ambiente de build." }
}

$python = Join-Path $buildEnv "Scripts/python.exe"
$pythonBase = (& $python -c "import sys; print(sys.base_prefix)").Trim()
$appVersion = (& $python -c "from app_version import APP_VERSION; print(APP_VERSION)").Trim()
$appVersionParts = $appVersion.Split('.')
if ($appVersionParts.Count -ne 3) { throw "APP_VERSION precisa ter o formato major.minor.patch." }
$versionTuple = "($($appVersionParts[0]), $($appVersionParts[1]), $($appVersionParts[2]), 0)"
$versionInfoFile = Join-Path $PSScriptRoot "build\ClipLink-version-info.txt"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $versionInfoFile) | Out-Null
@"
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=$versionTuple,
    prodvers=$versionTuple,
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable('040904B0', [
        StringStruct('CompanyName', 'ClipLink'),
        StringStruct('FileDescription', 'ClipLink Desktop'),
        StringStruct('FileVersion', '$appVersion.0'),
        StringStruct('InternalName', 'ClipLink'),
        StringStruct('OriginalFilename', 'ClipLink.exe'),
        StringStruct('ProductName', 'ClipLink'),
        StringStruct('ProductVersion', '$appVersion.0')
      ])
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"@ | Set-Content -Path $versionInfoFile -Encoding ascii
$tclData = Join-Path $pythonBase "tcl\tcl8.6"
$tkData = Join-Path $pythonBase "tcl\tk8.6"
$tkinterData = Join-Path $pythonBase "Lib\tkinter"
$tclDll = Join-Path $pythonBase "DLLs\tcl86t.dll"
$tkDll = Join-Path $pythonBase "DLLs\tk86t.dll"
foreach ($tkPath in @($tclData, $tkData, $tkinterData, $tclDll, $tkDll)) {
    if (-not (Test-Path $tkPath)) {
        throw "Arquivos Tcl/Tk ausentes: $tkPath"
    }
}
& $python -m pip install --disable-pip-version-check --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Não consegui atualizar o pip." }
if (Test-Path (Join-Path $PSScriptRoot "requirements-desktop.txt")) {
    & $python -m pip install --disable-pip-version-check --upgrade -r requirements-desktop.txt
} else {
    Write-Warning "requirements-desktop.txt ausente; instalando as dependências diretamente."
    & $python -m pip install --disable-pip-version-check --upgrade "yt-dlp[default,curl-cffi]==2026.8.19"
}
if ($LASTEXITCODE -ne 0) { throw "Não consegui instalar as dependências do ClipLink." }
& $python -m pip install --disable-pip-version-check --upgrade "pyinstaller==6.22.3"
if ($LASTEXITCODE -ne 0) { throw "Não consegui instalar o PyInstaller." }

$pyiArgs = @(
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--name", "ClipLink",
    "--version-file", $versionInfoFile,
    "--collect-all", "yt_dlp",
    "--collect-all", "yt_dlp_ejs",
    "--collect-all", "curl_cffi",
    "--hidden-import", "yt_dlp.jsinterp",
    "--hidden-import", "tkinter",
    "--hidden-import", "_tkinter",
    "--additional-hooks-dir", (Join-Path $PSScriptRoot "pyinstaller_hooks"),
    "--add-data", "$tclData;_tcl_data",
    "--add-data", "$tkData;_tk_data",
    "--add-data", "$tkinterData;tkinter",
    "--add-binary", "$tclDll;.",
    "--add-binary", "$tkDll;.",
    "--add-data", "assets/cliplink.ico;assets",
    "desktop_app.py"
)

$icon = Join-Path $PSScriptRoot "assets/cliplink.ico"
if (Test-Path $icon) { $pyiArgs = @("--icon", $icon) + $pyiArgs }

$toolsDir = Join-Path $PSScriptRoot "tools"
foreach ($tool in @("ffmpeg.exe", "ffprobe.exe", "node.exe")) {
    $toolPath = Join-Path $toolsDir $tool
    if (Test-Path $toolPath) {
        $pyiArgs += @("--add-binary", "$toolPath;tools")
    }
}

& $python -m PyInstaller @pyiArgs
if ($LASTEXITCODE -ne 0) { throw "O PyInstaller não conseguiu gerar o aplicativo." }

$exePath = Join-Path $PSScriptRoot "dist/ClipLink.exe"
Write-Host ""
Write-Host "Build concluído: $exePath" -ForegroundColor Green
if (-not (Test-Path (Join-Path $toolsDir "ffmpeg.exe"))) {
    Write-Warning "Sem tools/ffmpeg.exe, alguns links e a conversão para MP3 podem não funcionar."
}
