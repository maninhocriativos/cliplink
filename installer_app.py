from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
import sys
import time
import traceback
import winreg
from pathlib import Path

from app_version import APP_NAME, APP_VERSION
from app_paths import app_data_dir

HIDDEN_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def show_message(message: str, title: str, flags: int) -> int:
    return int(ctypes.windll.user32.MessageBoxW(None, message, title, flags))


def _powershell_literal(value: Path | str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_powershell(script: str, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
        check=True,
        creationflags=HIDDEN_WINDOW,
        stdout=subprocess.PIPE if capture_output else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )


def choose_destination() -> Path | None:
    if "--target" in sys.argv:
        index = sys.argv.index("--target") + 1
        if index < len(sys.argv) and sys.argv[index].strip():
            return Path(sys.argv[index]).expanduser().resolve()
    if len(sys.argv) > 1 and not sys.argv[1].startswith("--") and sys.argv[1].strip():
        return Path(sys.argv[1]).expanduser().resolve()
    existing = _existing_install_destination()
    if existing:
        return existing
    project_copy = Path.cwd() / f"{APP_NAME}-Instalado"
    default = project_copy if project_copy.is_dir() else Path(
        os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
    ) / "Programs"
    script = (
        "Add-Type -AssemblyName System.Windows.Forms;"
        "[System.Windows.Forms.Application]::EnableVisualStyles();"
        "$dialog=New-Object System.Windows.Forms.FolderBrowserDialog;"
        f"$dialog.Description={_powershell_literal('Escolha a pasta onde o ClipLink será instalado')};"
        f"$dialog.SelectedPath={_powershell_literal(default)};"
        "if($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK){Write-Output $dialog.SelectedPath}"
    )
    result = _run_powershell(script, capture_output=True)
    selected = result.stdout.strip()
    return (Path(selected) / APP_NAME).resolve() if selected else None


def _shortcut_paths() -> tuple[Path, ...]:
    user_profile = Path(os.environ.get("USERPROFILE", str(Path.home())))
    app_data = Path(os.environ.get("APPDATA", str(Path.home())))
    profiles = {user_profile, Path.home(), app_data.parent}
    paths: list[Path] = []
    for profile in profiles:
        paths.append(profile / "Desktop" / f"{APP_NAME}.lnk")
    for profile in profiles:
        roaming = profile / "AppData" / "Roaming"
        paths.append(roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / APP_NAME / f"{APP_NAME}.lnk")
        paths.append(roaming / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar" / f"{APP_NAME}.lnk")
    return tuple(dict.fromkeys(paths))


def _registry_install_destination() -> Path | None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipLink"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            raw, _ = winreg.QueryValueEx(key, "InstallLocation")
        candidate = Path(str(raw)).expanduser().resolve()
        return candidate if (candidate / "ClipLink.exe").is_file() else None
    except (FileNotFoundError, OSError, ValueError):
        return None


def _shortcut_target(shortcut: Path) -> Path | None:
    if not shortcut.is_file():
        return None
    script = (
        "$shell=New-Object -ComObject WScript.Shell;"
        f"$link=$shell.CreateShortcut({_powershell_literal(shortcut)});"
        "Write-Output $link.TargetPath"
    )
    try:
        result = _run_powershell(script, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        return None
    target = result.stdout.strip()
    return Path(target).resolve() if target else None


def _existing_install_destination() -> Path | None:
    registry_path = _registry_install_destination()
    if registry_path:
        return registry_path
    project_copy = Path.cwd() / f"{APP_NAME}-Instalado"
    if (project_copy / "ClipLink.exe").is_file():
        return project_copy.resolve()
    for shortcut in _shortcut_paths():
        target = _shortcut_target(shortcut)
        if target and target.name.lower() == "cliplink.exe" and target.is_file():
            return target.parent
    return None


def _user_install_destination() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "Programs"
    return (base / APP_NAME).resolve()


def _is_elevated() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def _is_protected_destination(destination: Path) -> bool:
    if _is_elevated():
        return False
    protected_roots = [
        Path(os.environ.get("ProgramFiles", r"C:\\Program Files")),
        Path(os.environ.get("ProgramFiles(x86)", r"C:\\Program Files (x86)")),
        Path(os.environ.get("WINDIR", r"C:\\Windows")),
    ]
    destination = destination.resolve()
    for root in protected_roots:
        try:
            destination.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def _create_shortcut(shortcut: Path, target: Path, working_dir: Path, icon: Path) -> None:
    shortcut.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "$shell=New-Object -ComObject WScript.Shell;"
        f"$link=$shell.CreateShortcut({_powershell_literal(shortcut)});"
        f"$link.TargetPath={_powershell_literal(target)};"
        f"$link.WorkingDirectory={_powershell_literal(working_dir)};"
        f"$link.IconLocation={_powershell_literal(str(icon) + ',0')};"
        f"$link.Description={_powershell_literal('Abrir o ClipLink')};"
        "$link.Save()"
    )
    _run_powershell(script)


def _uninstaller_content() -> str:
    return r'''$ErrorActionPreference = "SilentlyContinue"
$installDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$shortcuts = @(
    (Join-Path ([Environment]::GetFolderPath("Desktop")) "ClipLink.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\ClipLink\ClipLink.lnk"),
    (Join-Path $env:APPDATA "Microsoft\Internet Explorer\Quick Launch\User Pinned\TaskBar\ClipLink.lnk")
)
foreach ($shortcut in $shortcuts) { Remove-Item $shortcut -Force }
Remove-Item (Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\ClipLink") -Force
Remove-Item "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\ClipLink" -Recurse -Force
$command = "/c ping 127.0.0.1 -n 2 > nul & rmdir /s /q `"$installDir`""
Start-Process -FilePath $env:ComSpec -ArgumentList $command -WindowStyle Hidden
'''


def _register_uninstall(destination: Path, uninstaller: Path) -> None:
    uninstall_command = f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{uninstaller}"'
    script = (
        "$key='HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\ClipLink';"
        "New-Item -Path $key -Force | Out-Null;"
        f"Set-ItemProperty -Path $key -Name DisplayName -Value {_powershell_literal(APP_NAME)};"
        f"Set-ItemProperty -Path $key -Name DisplayVersion -Value {_powershell_literal(APP_VERSION)};"
        f"Set-ItemProperty -Path $key -Name InstallLocation -Value {_powershell_literal(destination)};"
        f"Set-ItemProperty -Path $key -Name Publisher -Value {_powershell_literal('ClipLink')};"
        f"Set-ItemProperty -Path $key -Name UninstallString -Value {_powershell_literal(uninstall_command)}"
    )
    _run_powershell(script)


def install(destination: Path) -> Path:
    if _is_protected_destination(destination):
        destination = _user_install_destination()
    payload = resource_path("payload")
    if not (payload / "ClipLink.exe").is_file():
        raise RuntimeError("O pacote do ClipLink está incompleto.")
    destination.mkdir(parents=True, exist_ok=True)
    last_error: OSError | None = None
    for _attempt in range(60):
        try:
            shutil.copytree(payload, destination, dirs_exist_ok=True)
            last_error = None
            break
        except PermissionError as exc:
            last_error = exc
            time.sleep(0.5)
    if last_error:
        raise RuntimeError("Feche o ClipLink aberto e tente a atualização novamente.") from last_error

    # Keep a small local marker so future installers can identify this exact
    # installation even when the uninstall registry entry is unavailable.
    (destination / ".cliplink-install.json").write_text(
        '{"name":"ClipLink","version":"' + APP_VERSION + '"}\n',
        encoding="utf-8",
    )

    uninstaller = destination / "Uninstall-ClipLink.ps1"
    uninstaller.write_text(_uninstaller_content(), encoding="utf-8")
    installed_exe = destination / "ClipLink.exe"
    icon = destination / "assets" / "cliplink.ico"
    for shortcut in _shortcut_paths():
        try:
            _create_shortcut(shortcut, installed_exe, destination, icon)
        except (OSError, subprocess.SubprocessError):
            pass
    try:
        _register_uninstall(destination, uninstaller)
    except (OSError, subprocess.SubprocessError):
        pass
    return destination


def main() -> None:
    silent = "--silent" in sys.argv
    try:
        destination = choose_destination()
        if destination is None:
            return
        destination = install(destination)
    except Exception as exc:
        try:
            (app_data_dir() / "installer.log").write_text(traceback.format_exc(), encoding="utf-8")
        except OSError:
            pass
        if not silent:
            show_message(str(exc), "Instalação do ClipLink", 0x10)
        raise SystemExit(1) from exc

    if silent:
        if "--open-after" in sys.argv:
            subprocess.Popen([str(destination / "ClipLink.exe")], cwd=str(destination))
        return
    answer = show_message(
        f"O ClipLink foi instalado em:\n{destination}\n\nDeseja abrir o programa agora?",
        "ClipLink instalado",
        0x44,
    )
    if answer == 6:
        subprocess.Popen([str(destination / "ClipLink.exe")], cwd=str(destination))


if __name__ == "__main__":
    main()
