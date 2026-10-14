@echo off
setlocal
cd /d "%~dp0"
set "CLIPLINK_DATA_DIR=%~dp0data"
set "TEMP=%~dp0.build-temp"
set "TMP=%TEMP%"
set "PIP_CACHE_DIR=%~dp0.build-cache\pip"
if not exist "%TEMP%" mkdir "%TEMP%"
if not exist "%PIP_CACHE_DIR%" mkdir "%PIP_CACHE_DIR%"

if exist "ClipLink.exe" (
  start "" "%~dp0ClipLink.exe"
  exit /b 0
)

if not exist "desktop_app.py" (
  echo Esta pasta nao contem o aplicativo desktop.
  echo Extraia o pacote completo com a opcao "Extrair tudo".
  if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
  exit /b 1
)

if not exist "url_safety.py" (
  echo Arquivo essencial ausente: url_safety.py
  echo Extraia novamente todos os arquivos do pacote antes de iniciar.
  if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    where python >nul 2>nul
    if errorlevel 1 (
      echo Python 3.10 ou superior nao foi encontrado.
      if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
      exit /b 1
    )
    python -m venv .venv
  )
)
if errorlevel 1 (
  echo Nao foi possivel criar o ambiente Python.
  if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
  exit /b 1
)

".venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)" >nul 2>nul
if errorlevel 1 (
  echo O ambiente Python precisa ser a versao 3.10 ou superior.
  if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
  exit /b 1
)

if exist "requirements-desktop.txt" (
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade -r requirements-desktop.txt
) else (
  echo O arquivo requirements-desktop.txt nao esta nesta pasta.
  echo Instalando o motor atualizado diretamente...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --upgrade "yt-dlp[default,curl-cffi]==2026.8.19"
)
if errorlevel 1 (
  ".venv\Scripts\python.exe" -c "import yt_dlp" >nul 2>nul
  if errorlevel 1 (
    echo Falha ao instalar o motor. Confira sua conexao e tente novamente.
    if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
    exit /b 1
  )
  echo AVISO: nao foi possivel atualizar agora. Vou abrir com a versao ja instalada.
)

if not exist ".venv\Scripts\pythonw.exe" (
  echo O Python sem console nao foi encontrado. Execute start_windows.bat novamente.
  if /i not "%CLIPLINK_HIDDEN_LAUNCH%"=="1" pause
  exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" desktop_app.py
exit /b 0
