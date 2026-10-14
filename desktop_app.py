from __future__ import annotations

import json
import hashlib
import os
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path

from app_paths import app_data_dir


if getattr(sys, "frozen", False):
    _frozen_root = Path(getattr(sys, "_MEIPASS", ""))
    _bundled_tkinter = _frozen_root / "tkinter"
    if _bundled_tkinter.is_dir():
        sys.path.insert(0, str(_frozen_root))

    # Some Windows Python installations expose Tcl/Tk but cannot resolve the
    # scripts from their original path. Use a persistent local copy instead of
    # relying on the one-file extraction directory or a broken system path.
    _tcl_source = _frozen_root / "_tcl_data"
    _tk_source = _frozen_root / "_tk_data"
    _runtime_root = Path(sys.executable).resolve().parent / "tcl-runtime"
    _runtime_tcl = _runtime_root / "tcl8.6"
    _runtime_tk = _runtime_root / "tk8.6"
    if not (_runtime_tcl / "init.tcl").is_file() or not (_runtime_tk / "tk.tcl").is_file():
        try:
            if _tcl_source.is_dir():
                _runtime_tcl.mkdir(parents=True, exist_ok=True)
                shutil.copytree(_tcl_source, _runtime_tcl, dirs_exist_ok=True)
            if _tk_source.is_dir():
                _runtime_tk.mkdir(parents=True, exist_ok=True)
                shutil.copytree(_tk_source, _runtime_tk, dirs_exist_ok=True)
        except OSError:
            pass
    if (_runtime_tcl / "init.tcl").is_file():
        os.environ["TCL_LIBRARY"] = str(_runtime_tcl)
    if (_runtime_tk / "tk.tcl").is_file():
        os.environ["TK_LIBRARY"] = str(_runtime_tk)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError as exc:
    if getattr(sys, "frozen", False):
        try:
            log_dir = app_data_dir()
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "startup.log").write_text(
                f"Falha ao carregar a interface: {exc}\n"
                f"MEIPASS={getattr(sys, '_MEIPASS', '')}\n"
                f"sys.path={sys.path}\n",
                encoding="utf-8",
            )
        except OSError:
            pass
    raise
from typing import Any

from url_safety import validate_url
from app_version import APP_NAME, APP_VERSION, UPDATE_MANIFEST_URL


BG = "#0B100E"
PANEL = "#121916"
PANEL_SOFT = "#17211D"
BORDER = "#26332D"
TEXT = "#F0F4EE"
MUTED = "#92A097"
ACCENT = "#C5F27A"
ACCENT_HOVER = "#D4FF8F"
RED = "#F08D82"
MAX_HISTORY_ITEMS = 8
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif", ".bmp", ".tif", ".tiff"}
QUALITY_PRESETS = ("Melhor disponível", "2160p", "1440p", "1080p", "720p", "480p", "360p", "240p")

# TikTok increasingly serves a challenge page to generic web requests. yt-dlp
# already contains a supported mobile API fallback; an ephemeral install id
# enables it without storing cookies, accounts, or other credentials.
_TIKTOK_IID = str(7250000000000000000 + secrets.randbelow(7509999899994577))


def app_resource_path(relative: str) -> Path:
    """Return a bundled resource path when running from a PyInstaller build."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / relative


def media_tool(name: str) -> str | None:
    bundled = app_resource_path(f"tools/{name}")
    if bundled.is_file():
        return str(bundled)
    return shutil.which(name)


def _history_file() -> Path:
    return app_data_dir() / "history.json"


def _settings_file() -> Path:
    return app_data_dir() / "settings.json"


def _load_settings() -> dict[str, Any]:
    try:
        raw = json.loads(_settings_file().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return raw if isinstance(raw, dict) else {}


def _save_settings(settings: dict[str, Any]) -> bool:
    try:
        path = _settings_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return True
    except OSError:
        return False


def _default_download_dir() -> Path:
    settings = _load_settings()
    saved = settings.get("download_dir")
    if isinstance(saved, str) and saved.strip():
        return Path(saved).expanduser()
    return app_data_dir() / "Downloads"


def _quality_values(available_heights: list[int] | None = None) -> tuple[str, ...]:
    heights = sorted({int(height) for height in (available_heights or []) if int(height) > 0}, reverse=True)
    return (QUALITY_PRESETS[0],) + tuple(f"{height}p" for height in heights)


def _load_history(path: Path) -> list[dict[str, str]]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    items: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        file_path = Path(item["path"])
        if not file_path.is_file():
            continue
        items.append({
            "title": str(item.get("title") or file_path.name)[:180],
            "platform": str(item.get("platform") or "Vídeo")[:40],
            "path": str(file_path),
            "saved_at": str(item.get("saved_at") or "")[:32],
        })
        if len(items) >= MAX_HISTORY_ITEMS:
            break
    return items


def _save_history(path: Path, items: list[dict[str, str]]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(items[:MAX_HISTORY_ITEMS], ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(path)
        return True
    except OSError:
        return False


def _quiet_logger() -> Any:
    class QuietLogger:
        def debug(self, _message: str) -> None:
            pass

        def warning(self, _message: str) -> None:
            pass

        def error(self, _message: str) -> None:
            pass

    return QuietLogger()


def _base_options() -> dict[str, Any]:
    ffmpeg = media_tool("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    node = media_tool("node.exe" if os.name == "nt" else "node")
    options: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "ignoreconfig": True,
        "cachedir": False,
        "socket_timeout": 20,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 2,
        "extractor_args": {
            "tiktok": {
                "app_info": [_TIKTOK_IID],
            },
        },
        "restrictfilenames": True,
        "color": "never",
        "logger": _quiet_logger(),
    }
    if ffmpeg:
        options["ffmpeg_location"] = ffmpeg
    if node:
        options["js_runtimes"] = {"node": {"path": node}}
    return options


def _safe_metadata(info: dict[str, Any], source_url: str = "") -> dict[str, Any]:
    formats = info.get("formats") or []
    heights = sorted({
        int(item["height"])
        for item in formats
        if isinstance(item, dict) and item.get("height") and str(item["height"]).isdigit()
        and int(item["height"]) > 0
    }, reverse=True)
    duration = info.get("duration")
    duration = int(duration) if isinstance(duration, (int, float)) and duration >= 0 else None
    extractor = str(info.get("extractor_key") or info.get("extractor") or "Site compatível")
    extractor = extractor.replace("IE", "").replace("_", " ").strip().title()[:40]
    extension = str(info.get("ext") or "").lower()
    mime_type = str(info.get("mime_type") or "").lower()
    is_story = "story" in extractor.lower() or "/stories/" in source_url.lower()
    is_image = extension in {item.lstrip(".") for item in IMAGE_EXTENSIONS} or mime_type.startswith("image/")
    media_kind = "image" if is_image else "story" if is_story else "video"
    format_sizes = [
        item.get("filesize") or item.get("filesize_approx")
        for item in formats
        if isinstance(item, dict)
    ]
    estimated_size = max((int(size) for size in format_sizes if isinstance(size, (int, float)) and size > 0), default=None)
    return {
        "title": str(info.get("title") or "Vídeo encontrado")[:180],
        "platform": extractor or "Site compatível",
        "duration": duration,
        "max_height": max(heights) if heights else None,
        "available_heights": heights,
        "is_live": bool(info.get("is_live")),
        "has_drm": bool(info.get("has_drm")),
        "availability": str(info.get("availability") or "unknown"),
        "content_type": str(info.get("_type") or "video"),
        "media_kind": media_kind,
        "extension": extension,
        "format_count": len(formats),
        "estimated_size": estimated_size,
        "has_audio": any(str(item.get("acodec") or "none") not in {"", "none"} for item in formats if isinstance(item, dict)),
        "has_video": any(str(item.get("vcodec") or "none") not in {"", "none"} for item in formats if isinstance(item, dict)),
    }


def _check_content_scope(info: dict[str, Any], source_url: str = "") -> None:
    from yt_dlp.utils import DownloadError

    metadata = _safe_metadata(info, source_url)
    if metadata["has_drm"]:
        raise DownloadError("Este conteúdo está protegido e não pode ser processado.")
    if metadata["content_type"] in {"playlist", "multi_video"} and metadata["media_kind"] not in {"story", "image"}:
        raise DownloadError("Playlists e coleções não entram nesta versão.")
    # A disponibilidade informada pelo extrator é apenas uma indicação. Não
    # bloqueamos preventivamente: o usuário decide se possui autorização e o
    # próprio site determina se a requisição pode ser concluída.


def _format_selector(quality: str, media_format: str = "MP4") -> str:
    if media_format == "Imagem":
        return "best"
    if quality == "Melhor disponível":
        return "bv*+ba/b"
    height = int(quality.replace("p", ""))
    return f"bv*[height<={height}]+ba/b[height<={height}]/bv*+ba/b"


def _duration_label(seconds: int | None) -> str:
    if not seconds:
        return "Duração indisponível"
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{sec:02d}" if hours else f"{minutes}:{sec:02d} min"


def _confine_output_path(path: Path, folder: Path) -> Path:
    """Ensure a downloader-generated path stays inside the selected folder."""
    resolved_path = path.resolve()
    resolved_folder = folder.resolve()
    if resolved_path == resolved_folder or resolved_folder not in resolved_path.parents:
        raise ValueError("O arquivo gerado não pertence à pasta escolhida.")
    return resolved_path


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for item in str(value).strip().split(".")[:4]:
        try:
            parts.append(int(item))
        except ValueError:
            parts.append(0)
    return tuple(parts or [0])


def _update_manifest_url() -> str:
    return os.environ.get("CLIPLINK_UPDATE_URL", UPDATE_MANIFEST_URL).strip()


def _read_update_manifest() -> dict[str, Any]:
    manifest_url = _update_manifest_url()
    if not manifest_url:
        raise RuntimeError("O canal de atualizações ainda não foi configurado.")
    parsed = urllib.parse.urlparse(manifest_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RuntimeError("O canal de atualizações precisa usar uma URL HTTPS válida.")
    request = urllib.request.Request(manifest_url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    with urllib.request.urlopen(request, timeout=15) as response:
        raw = response.read(512 * 1024)
    manifest = json.loads(raw.decode("utf-8"))
    if not isinstance(manifest, dict) or not isinstance(manifest.get("version"), str):
        raise RuntimeError("O manifesto de atualização está incompleto.")
    installer_url = str(manifest.get("installer_url") or "")
    parsed_installer = urllib.parse.urlparse(urllib.parse.urljoin(manifest_url, installer_url))
    if parsed_installer.scheme not in {"http", "https"} or not parsed_installer.netloc:
        raise RuntimeError("O manifesto não informou um instalador HTTPS válido.")
    manifest["installer_url"] = urllib.parse.urljoin(manifest_url, installer_url)
    return manifest


def _download_update_installer(manifest: dict[str, Any]) -> Path:
    installer_url = str(manifest["installer_url"])
    update_dir = Path(sys.executable).resolve().parent / ".updates"
    update_dir.mkdir(parents=True, exist_ok=True)
    version = "".join(character for character in str(manifest["version"]) if character.isalnum() or character in ".-_")
    destination = update_dir / f"ClipLink-Setup-{version}.exe"
    temporary = destination.with_suffix(".download")
    request = urllib.request.Request(installer_url, headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as stream:
        for chunk in iter(lambda: response.read(1024 * 1024), b""):
            stream.write(chunk)
            digest.update(chunk)
    expected = str(manifest.get("sha256") or "").strip().lower()
    if expected and digest.hexdigest().lower() != expected:
        temporary.unlink(missing_ok=True)
        raise RuntimeError("A assinatura SHA-256 do instalador não confere.")
    temporary.replace(destination)
    return destination


def _write_lab_report(source_url: str, info: dict[str, Any], metadata: dict[str, Any]) -> Path | None:
    """Write a local, credential-free diagnostic report for a real link."""
    try:
        report_dir = app_data_dir() / "lab-reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        report_path = report_dir / f"cliplink-lab-{stamp}.json"
        formats = info.get("formats") or []
        format_rows = []
        for item in formats:
            if not isinstance(item, dict):
                continue
            format_rows.append({
                key: item.get(key)
                for key in (
                    "format_id", "ext", "format_note", "height", "width", "fps",
                    "acodec", "vcodec", "protocol", "filesize", "filesize_approx",
                )
                if item.get(key) is not None
            })
        report = {
            "app_version": APP_VERSION,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "url": source_url,
            "title": metadata.get("title"),
            "platform": metadata.get("platform"),
            "media_kind": metadata.get("media_kind"),
            "content_type": metadata.get("content_type"),
            "availability": metadata.get("availability"),
            "is_live": metadata.get("is_live"),
            "has_drm": metadata.get("has_drm"),
            "format_count": metadata.get("format_count", 0),
            "estimated_size": metadata.get("estimated_size"),
            "has_audio": metadata.get("has_audio"),
            "has_video": metadata.get("has_video"),
            "available_heights": metadata.get("available_heights", []),
            "formats": format_rows,
            "evidence": [],
            "credentials_used": False,
        }
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report_path
    except (OSError, TypeError, ValueError):
        return None


def _append_lab_evidence(report_path: Path, media_path: Path) -> bool:
    """Add a downloaded image/video and its integrity hash to a lab report."""
    try:
        if not report_path.is_file() or not media_path.is_file():
            return False
        digest = hashlib.sha256()
        with media_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        report = json.loads(report_path.read_text(encoding="utf-8"))
        if not isinstance(report, dict):
            return False
        evidence = report.setdefault("evidence", [])
        if not isinstance(evidence, list):
            evidence = []
            report["evidence"] = evidence
        evidence.append({
            "path": str(media_path.resolve()),
            "filename": media_path.name,
            "size_bytes": media_path.stat().st_size,
            "sha256": digest.hexdigest().upper(),
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        })
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary.replace(report_path)
        return True
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False


class ClipLinkApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("ClipLink — Downloads locais")
        self.root.geometry("1220x840")
        self.root.minsize(980, 620)
        self.root.configure(bg=BG)
        self.root.protocol("WM_DELETE_WINDOW", self._close)

        self.download_dir = tk.StringVar(value=str(_default_download_dir()))
        self.url = tk.StringVar()
        self.quality = tk.StringVar(value="Melhor disponível")
        self.format = tk.StringVar(value="MP4")
        self.status = tk.StringVar(value="Pronto para começar")
        self.legal_confirmed = tk.BooleanVar(value=False)
        self.lab_mode = tk.BooleanVar(value=False)
        self.lab_report = tk.StringVar(value="")
        self.lab_report_path: Path | None = None
        self.current_metadata: dict[str, Any] | None = None
        self.history_path = _history_file()
        self.history = _load_history(self.history_path)
        self.last_download = Path(self.history[0]["path"]) if self.history else None
        self.working = False
        self.cancel_requested = False
        self.update_working = False
        self.update_manifest: dict[str, Any] | None = None

        Path(self.download_dir.get()).mkdir(parents=True, exist_ok=True)
        self._configure_styles()
        if os.name == "nt":
            try:
                self.root.iconbitmap(str(app_resource_path("assets/cliplink.ico")))
            except tk.TclError:
                pass
        self._build_ui()
        self.url.trace_add("write", self._input_changed)
        self.legal_confirmed.trace_add("write", lambda *_: self._sync_buttons())

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PANEL_SOFT, background=PANEL_SOFT,
                        foreground=TEXT, arrowcolor=ACCENT, bordercolor=BORDER,
                        lightcolor=BORDER, darkcolor=BORDER, padding=(12, 10))
        style.map("TCombobox", fieldbackground=[("readonly", PANEL_SOFT)],
                  foreground=[("readonly", TEXT)], selectbackground=[("readonly", PANEL_SOFT)],
                  selectforeground=[("readonly", TEXT)])
        style.configure("Clip.Horizontal.TProgressbar", troughcolor=PANEL_SOFT,
                        background=ACCENT, bordercolor=PANEL_SOFT, lightcolor=ACCENT,
                        darkcolor=ACCENT, thickness=7)
        style.configure("Clip.Vertical.TScrollbar", background=PANEL_SOFT, troughcolor=BG,
                        bordercolor=BG, arrowcolor=MUTED, width=9)
        style.map("Clip.Vertical.TScrollbar", background=[("active", BORDER)])
        style.configure("Clip.TCheckbutton", background=PANEL, foreground=TEXT,
                        font=("Segoe UI", 9), focuscolor=PANEL)
        style.map("Clip.TCheckbutton", background=[("active", PANEL)],
                  foreground=[("disabled", MUTED)])

    def _card(self, parent: tk.Widget, **kwargs: Any) -> tk.Frame:
        outer = tk.Frame(parent, bg=BORDER, padx=1, pady=1)
        inner = tk.Frame(outer, bg=PANEL, padx=kwargs.get("padx", 22), pady=kwargs.get("pady", 20))
        inner.pack(fill="both", expand=True)
        return outer

    def _build_ui(self) -> None:
        root = self.root
        viewport = tk.Frame(root, bg=BG)
        viewport.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(viewport, bg=BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(viewport, orient="vertical", command=self.canvas.yview,
                                  style="Clip.Vertical.TScrollbar")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        shell = tk.Frame(self.canvas, bg=BG, padx=34, pady=20)
        shell_window = self.canvas.create_window((0, 0), window=shell, anchor="nw")
        shell.bind("<Configure>", lambda _event: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda event: self.canvas.itemconfigure(shell_window, width=event.width))
        self.canvas.bind("<Enter>", self._bind_mousewheel)
        self.canvas.bind("<Leave>", self._unbind_mousewheel)
        shell.grid_columnconfigure(0, weight=1)

        header = tk.Frame(shell, bg=BG)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 34))
        header.grid_columnconfigure(1, weight=1)
        mark = tk.Canvas(header, width=40, height=40, bg=BG, highlightthickness=0)
        mark.grid(row=0, column=0, rowspan=2, sticky="w", padx=(0, 12))
        mark.create_rectangle(2, 2, 38, 38, fill=PANEL_SOFT, outline=BORDER, width=1)
        mark.create_oval(7, 12, 24, 29, outline=ACCENT, width=2)
        mark.create_oval(16, 10, 33, 27, outline=ACCENT, width=2)
        mark.create_polygon(17, 15, 17, 25, 25, 20, fill=ACCENT, outline=ACCENT)
        tk.Label(header, text="CLIPLINK", bg=BG, fg=TEXT, font=("Segoe UI", 13, "bold")).grid(
            row=0, column=1, sticky="sw")
        tk.Label(header, text=f"DESKTOP  ·  BETA {APP_VERSION}", bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).grid(row=1, column=1, sticky="nw", pady=(2, 0))
        self._pill(header, "●  LOCAL  ·  PRIVADO", fg=ACCENT).grid(row=0, column=2, rowspan=2, sticky="e")

        titlebox = tk.Frame(shell, bg=BG)
        titlebox.grid(row=1, column=0, sticky="ew", pady=(0, 22))
        tk.Label(titlebox, text="Downloads, sem ruído.", bg=BG, fg=TEXT,
                 font=("Segoe UI", 28, "bold")).pack(anchor="w")
        tk.Label(titlebox, text="Salve no seu computador os vídeos que você tem autorização para guardar.",
                 bg=BG, fg=MUTED, font=("Segoe UI", 10)).pack(anchor="w", pady=(6, 0))

        content = tk.Frame(shell, bg=BG)
        content.grid(row=2, column=0, sticky="nsew")
        content.grid_columnconfigure(0, weight=7, uniform="columns")
        content.grid_columnconfigure(1, weight=4, uniform="columns")
        content.grid_rowconfigure(0, weight=1)
        left = tk.Frame(content, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        right = tk.Frame(content, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=(14, 0))

        self._build_download_card(left)
        self._build_result_card(left)
        self._build_progress_card(left)
        self._build_history_card(left)
        self._build_info_card(right)
        self._build_update_card(right)
        self._build_privacy_card(right)
        self._build_footer(shell)

    def _bind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _unbind_mousewheel(self, _event: tk.Event) -> None:
        self.canvas.unbind_all("<MouseWheel>")

    def _on_mousewheel(self, event: tk.Event) -> None:
        delta = getattr(event, "delta", 0)
        if delta:
            self.canvas.yview_scroll(int(-delta / 120) or (-1 if delta > 0 else 1), "units")

    def _pill(self, parent: tk.Widget, text: str, fg: str = MUTED) -> tk.Label:
        return tk.Label(parent, text=text, bg=PANEL_SOFT, fg=fg,
                        font=("Segoe UI", 8, "bold"), padx=12, pady=7)

    def _section_title(self, parent: tk.Widget, title: str, subtitle: str | None = None) -> None:
        tk.Label(parent, text=title, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 12, "bold")).pack(anchor="w")
        if subtitle:
            tk.Label(parent, text=subtitle, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

    def _build_download_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=22, pady=21)
        card.pack(fill="x", pady=(0, 12))
        body = card.winfo_children()[0]
        tk.Label(
            body,
            text="YouTube  \u2022  TikTok  \u2022  Instagram  \u2022  Imagem p\u00fablica",
            bg=PANEL,
            fg=ACCENT,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w", pady=(0, 7))
        self._section_title(body, "Novo download", "Cole o endereço público do vídeo abaixo.")

        tk.Label(body, text="LINK DO VÍDEO", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(20, 7))
        url_row = tk.Frame(body, bg=PANEL_SOFT, highlightthickness=1, highlightbackground=BORDER)
        url_row.pack(fill="x")
        self.url_entry = tk.Entry(url_row, textvariable=self.url, bg=PANEL_SOFT, fg=TEXT,
                                  insertbackground=ACCENT, relief="flat", bd=0,
                                  font=("Segoe UI", 10), highlightthickness=0)
        self.url_entry.pack(side="left", fill="x", expand=True, padx=(13, 4), pady=12)
        self.url_entry.bind("<Return>", lambda _event: self._inspect())
        self.paste_button = self._text_button(url_row, "Colar", self._paste_clipboard, compact=True)
        self.paste_button.pack(side="right", padx=5, pady=5)

        options = tk.Frame(body, bg=PANEL)
        options.pack(fill="x", pady=(16, 0))
        options.grid_columnconfigure(0, weight=1)
        options.grid_columnconfigure(1, weight=1)
        for col, label in enumerate(("FORMATO", "QUALIDADE / RESOLUÇÃO")):
            tk.Label(options, text=label, bg=PANEL, fg=MUTED,
                     font=("Segoe UI", 8, "bold")).grid(row=0, column=col, sticky="w", pady=(0, 7))

        format_frame = tk.Frame(options, bg=PANEL_SOFT, padx=4, pady=4)
        format_frame.grid(row=1, column=0, sticky="ew", padx=(0, 8))
        self.format_buttons: dict[str, tk.Button] = {}
        for fmt in ("MP4", "MP3", "Imagem"):
            button = tk.Button(format_frame, text=fmt, command=lambda value=fmt: self._select_format(value),
                               relief="flat", bd=0, cursor="hand2", font=("Segoe UI", 9, "bold"),
                               padx=15, pady=7)
            button.pack(side="left", fill="x", expand=True)
            self.format_buttons[fmt] = button
        self._update_format_buttons()

        self.quality_combo = ttk.Combobox(options, textvariable=self.quality, state="readonly",
                                          values=("Melhor disponível", "1080p", "720p", "480p"),
                                          font=("Segoe UI", 9))
        self.quality_combo.grid(row=1, column=1, sticky="ew", padx=(8, 0))
        self.quality_combo.configure(values=QUALITY_PRESETS)
        tk.Label(
            body,
            text="Escolha a resolu\u00e7\u00e3o m\u00e1xima; o ClipLink usa a melhor op\u00e7\u00e3o dispon\u00edvel at\u00e9 esse limite.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(anchor="w", pady=(7, 0))

        folder_header = tk.Frame(body, bg=PANEL)
        folder_header.pack(fill="x", pady=(17, 7))
        tk.Label(folder_header, text="SALVAR EM", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(side="left")
        self.folder_button = self._text_button(folder_header, "Escolher pasta", self._choose_folder, compact=True)
        self.folder_button.pack(side="right")
        folder_view = tk.Frame(body, bg=PANEL_SOFT, highlightthickness=1, highlightbackground=BORDER)
        folder_view.pack(fill="x")
        tk.Label(folder_view, text="↳", bg=PANEL_SOFT, fg=ACCENT,
                 font=("Segoe UI", 12, "bold")).pack(side="left", padx=(12, 8), pady=9)
        tk.Label(folder_view, textvariable=self.download_dir, bg=PANEL_SOFT, fg=TEXT,
                 font=("Segoe UI", 9), anchor="w").pack(side="left", fill="x", expand=True, pady=9, padx=(0, 12))

        check_row = tk.Frame(body, bg=PANEL)
        check_row.pack(fill="x", pady=(14, 0))
        ttk.Checkbutton(check_row, variable=self.legal_confirmed, style="Clip.TCheckbutton").pack(side="left", anchor="n", pady=(1, 0))
        tk.Label(check_row, text="Tenho 18 anos ou mais e autorização para salvar este conteúdo.\nUsarei apenas materiais públicos, legais e consensuais.",
                 bg=PANEL, fg=MUTED, justify="left", font=("Segoe UI", 8)).pack(side="left", anchor="w")

        lab_row = tk.Frame(body, bg=PANEL)
        lab_row.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(
            lab_row,
            text="Modo laboratório",
            variable=self.lab_mode,
            style="Clip.TCheckbutton",
        ).pack(side="left", anchor="n")
        tk.Label(
            lab_row,
            text="Testa links reais e gera diagnóstico local; não usa credenciais.",
            bg=PANEL,
            fg=MUTED,
            font=("Segoe UI", 8),
        ).pack(side="left", padx=(8, 0), anchor="w")

        actions = tk.Frame(body, bg=PANEL)
        actions.pack(fill="x", pady=(17, 0))
        self.analyze_button = tk.Button(actions, text="Analisar link  →", command=self._inspect,
                                        relief="flat", bd=0, cursor="hand2", bg=ACCENT, fg=BG,
                                        activebackground=ACCENT_HOVER, activeforeground=BG,
                                        font=("Segoe UI", 10, "bold"), padx=17, pady=11)
        self.analyze_button.pack(side="left", fill="x", expand=True)
        self.download_button = tk.Button(actions, text="Baixar arquivo", command=self._download,
                                         relief="flat", bd=0, cursor="hand2", bg=PANEL_SOFT, fg=MUTED,
                                         activebackground=PANEL_SOFT, font=("Segoe UI", 10, "bold"),
                                         padx=17, pady=11, state="disabled")
        self.download_button.pack(side="left", fill="x", expand=True, padx=(9, 0))

    def _build_result_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=18, pady=15)
        card.pack(fill="x", pady=(0, 12))
        body = card.winfo_children()[0]
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x")
        self._pill(row, "LINK AINDA NÃO ANALISADO").pack(side="left")
        self.result_title = tk.Label(body, text="Os detalhes do vídeo aparecerão aqui", bg=PANEL,
                                     fg=TEXT, font=("Segoe UI", 10, "bold"), anchor="w", justify="left", wraplength=580)
        self.result_title.pack(fill="x", pady=(10, 4))
        self.result_subtitle = tk.Label(body, text="Plataforma  —     Duração  —     Resolução  —", bg=PANEL,
                                        fg=MUTED, font=("Segoe UI", 8), anchor="w")
        self.result_subtitle.pack(fill="x")
        self.detected_type = tk.StringVar(value="Tipo: aguardando an\u00e1lise")
        tk.Label(body, textvariable=self.detected_type, bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(7, 0))
        tk.Label(body, textvariable=self.lab_report, bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8), anchor="w", justify="left", wraplength=580).pack(fill="x", pady=(5, 0))

    def _build_progress_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=18, pady=15)
        card.pack(fill="x")
        body = card.winfo_children()[0]
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x")
        tk.Label(row, textvariable=self.status, bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 9, "bold")).pack(side="left")
        self.progress_percent = tk.Label(row, text="", bg=PANEL, fg=ACCENT,
                                         font=("Segoe UI", 8, "bold"))
        self.progress_percent.pack(side="right")
        self.cancel_button = self._text_button(row, "Cancelar", self._cancel_download, compact=True)
        self.cancel_button.pack(side="right", padx=(0, 8))
        self.cancel_button.pack_forget()
        self.progress = ttk.Progressbar(body, style="Clip.Horizontal.TProgressbar", maximum=100, value=0)
        self.progress.pack(fill="x", pady=(12, 7))
        detail = tk.Frame(body, bg=PANEL)
        detail.pack(fill="x")
        tk.Label(detail, text="Seu arquivo fica no computador", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8)).pack(side="left")
        self.open_folder_button = self._text_button(detail, "Abrir pasta", self._open_folder, compact=True)
        self.open_folder_button.pack(side="right", padx=(7, 0))
        self.open_file_button = self._text_button(detail, "Abrir último vídeo", self._open_last_file, compact=True)
        self.open_file_button.pack(side="right")

    def _build_history_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=18, pady=15)
        card.pack(fill="x", pady=(12, 0))
        body = card.winfo_children()[0]
        header = tk.Frame(body, bg=PANEL)
        header.pack(fill="x", pady=(0, 9))
        tk.Label(header, text="Downloads recentes", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.history_clear_button = self._text_button(header, "Limpar histórico", self._clear_history, compact=True)
        self.history_clear_button.pack(side="right")
        self.history_rows = tk.Frame(body, bg=PANEL)
        self.history_rows.pack(fill="x")
        self._refresh_history()

    def _refresh_history(self) -> None:
        self.open_file_button.configure(
            state="normal" if self.last_download and self.last_download.is_file() else "disabled"
        )
        for child in self.history_rows.winfo_children():
            child.destroy()
        if not self.history:
            tk.Label(self.history_rows, text="Os arquivos baixados aparecerão aqui.",
                     bg=PANEL, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(2, 3))
            self.history_clear_button.configure(state="disabled")
            return
        self.history_clear_button.configure(state="normal")
        for item in self.history[:MAX_HISTORY_ITEMS]:
            row = tk.Frame(self.history_rows, bg=PANEL_SOFT, padx=10, pady=8)
            row.pack(fill="x", pady=(0, 6))
            details = tk.Frame(row, bg=PANEL_SOFT)
            details.pack(side="left", fill="x", expand=True)
            tk.Label(details, text=item["title"], bg=PANEL_SOFT, fg=TEXT,
                     font=("Segoe UI", 8, "bold"), anchor="w", justify="left",
                     wraplength=500).pack(anchor="w", fill="x")
            detail_text = "  ·  ".join(part for part in (item.get("platform"), item.get("saved_at")) if part)
            tk.Label(details, text=detail_text, bg=PANEL_SOFT, fg=MUTED,
                     font=("Segoe UI", 7), anchor="w").pack(anchor="w", pady=(2, 0))
            self._text_button(row, "Abrir", lambda entry=item: self._open_history_item(entry), compact=True).pack(side="right", padx=(8, 0))

    def _open_path(self, path: Path) -> None:
        if not path.exists():
            messagebox.showerror("Arquivo não encontrado", "Esse arquivo não está mais nesta pasta.", parent=self.root)
            return
        try:
            if os.name == "nt":
                os.startfile(str(path))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError as exc:
            messagebox.showerror("Não foi possível abrir o arquivo", str(exc), parent=self.root)

    def _open_last_file(self) -> None:
        if self.last_download:
            self._open_path(self.last_download)
        else:
            messagebox.showinfo("Ainda sem downloads", "Conclua um download para abrir o vídeo por aqui.", parent=self.root)

    def _open_history_item(self, item: dict[str, str]) -> None:
        self._open_path(Path(item["path"]))

    def _clear_history(self) -> None:
        if not self.history:
            return
        if not messagebox.askyesno("Limpar histórico", "Remover os itens recentes? Os arquivos de vídeo não serão apagados.", parent=self.root):
            return
        self.history = []
        self.last_download = None
        _save_history(self.history_path, self.history)
        self._refresh_history()

    def _remember_download(self, path: Path) -> None:
        metadata = self.current_metadata or {}
        self.history = [
            {
                "title": str(metadata.get("title") or path.name),
                "platform": str(metadata.get("platform") or "Vídeo"),
                "path": str(path),
                "saved_at": time.strftime("%d/%m/%Y %H:%M"),
            },
            *[item for item in self.history if item.get("path") != str(path)],
        ][:MAX_HISTORY_ITEMS]
        self.last_download = path
        if not _save_history(self.history_path, self.history):
            self.status.set("Download concluído · histórico local indisponível")
        self._refresh_history()

    def _build_info_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=21, pady=21)
        card.pack(fill="x", pady=(0, 12))
        body = card.winfo_children()[0]
        tk.Label(body, text="✳", bg=PANEL, fg=ACCENT, font=("Segoe UI", 18, "bold")).pack(anchor="w")
        self._section_title(body, "Simples por desenho")
        items = [
            ("01", "Cole o link", "O ClipLink identifica o site e os detalhes disponíveis."),
            ("02", "Escolha a qualidade", "Selecione o formato e a resolução que fazem sentido."),
            ("03", "Salve localmente", "O arquivo vai direto para a pasta que você escolheu."),
        ]
        for number, title, desc in items:
            row = tk.Frame(body, bg=PANEL)
            row.pack(fill="x", pady=(18, 0))
            tk.Label(row, text=number, bg=PANEL_SOFT, fg=ACCENT,
                     font=("Segoe UI", 8, "bold"), padx=8, pady=6).pack(side="left", anchor="n")
            text = tk.Frame(row, bg=PANEL)
            text.pack(side="left", fill="x", expand=True, padx=(11, 0))
            tk.Label(text, text=title, bg=PANEL, fg=TEXT,
                     font=("Segoe UI", 9, "bold")).pack(anchor="w")
            tk.Label(text, text=desc, bg=PANEL, fg=MUTED, justify="left", wraplength=205,
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(3, 0))

    def _build_update_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=19, pady=18)
        card.pack(fill="x", pady=(0, 12))
        body = card.winfo_children()[0]
        top = tk.Frame(body, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text="↻", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=(0, 9))
        tk.Label(top, text="Aplicações / Atualizações", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(body, text=f"Versão instalada: {APP_VERSION}", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(9, 0))
        self.update_status_label = tk.Label(
            body, text="Verifique se existe uma versão nova.", bg=PANEL, fg=TEXT,
            font=("Segoe UI", 8), wraplength=260, justify="left")
        self.update_status_label.pack(anchor="w", pady=(6, 0))
        actions = tk.Frame(body, bg=PANEL)
        actions.pack(fill="x", pady=(12, 0))
        self.update_check_button = self._text_button(actions, "Verificar atualizações", self._check_updates, compact=True)
        self.update_check_button.pack(side="left")
        self.update_install_button = self._text_button(
            actions, "Atualizar para a versão mais recente", self._install_latest, compact=True
        )
        self.update_install_button.configure(bg=ACCENT, fg=BG)
        self.update_install_button.pack(side="right")

    def _build_privacy_card(self, parent: tk.Widget) -> None:
        card = self._card(parent, padx=19, pady=18)
        card.pack(fill="x")
        body = card.winfo_children()[0]
        top = tk.Frame(body, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text="◉", bg=PANEL, fg=ACCENT,
                 font=("Segoe UI", 14, "bold")).pack(side="left", padx=(0, 9))
        tk.Label(top, text="Privacidade local", bg=PANEL, fg=TEXT,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        tk.Label(body, text="Os links são processados no seu computador. O ClipLink não pede senha; o histórico fica salvo apenas localmente.",
                 bg=PANEL, fg=MUTED, font=("Segoe UI", 8), wraplength=260,
                 justify="left").pack(anchor="w", pady=(9, 0))
        tk.Frame(body, bg=BORDER, height=1).pack(fill="x", pady=13)
        tk.Label(body, text="LIMITES DE USO", bg=PANEL, fg=MUTED,
                 font=("Segoe UI", 8, "bold")).pack(anchor="w")
        tk.Label(body, text="Não contorna login, assinatura ou DRM. Conteúdo público, inclusive transmissões ao vivo compatíveis, pode ser processado.",
                 bg=PANEL, fg=TEXT, font=("Segoe UI", 8), wraplength=260,
                 justify="left").pack(anchor="w", pady=(6, 0))

    def _build_footer(self, parent: tk.Widget) -> None:
        footer = tk.Frame(parent, bg=BG)
        footer.grid(row=3, column=0, sticky="ew", pady=(15, 0))
        tk.Label(footer, text=f"CLIPLINK {APP_VERSION}  ·  FERRAMENTA LOCAL PARA CONTEÚDO AUTORIZADO",
                 bg=BG, fg="#718078", font=("Segoe UI", 7, "bold")).pack(side="left")
        tk.Label(footer, text="Compatibilidade depende do site e da disponibilidade pública do link.",
                 bg=BG, fg="#718078", font=("Segoe UI", 7)).pack(side="right")

    def _text_button(self, parent: tk.Widget, label: str, command: Any, compact: bool = False) -> tk.Button:
        return tk.Button(parent, text=label, command=command, relief="flat", bd=0,
                         cursor="hand2", bg=PANEL_SOFT if compact else PANEL, fg=TEXT,
                         activebackground=PANEL_SOFT, activeforeground=ACCENT,
                         font=("Segoe UI", 8, "bold"), padx=10 if compact else 8,
                         pady=7 if compact else 5)

    def _update_format_buttons(self) -> None:
        for name, button in self.format_buttons.items():
            selected = self.format.get() == name
            button.configure(bg=ACCENT if selected else PANEL_SOFT,
                             fg=BG if selected else MUTED,
                             activebackground=ACCENT_HOVER if selected else PANEL_SOFT)

    def _select_format(self, value: str) -> None:
        self.format.set(value)
        self._update_format_buttons()
        self.quality_combo.configure(state="disabled" if value in {"MP3", "Imagem"} else "readonly")
        if value == "MP3" and not self._ffmpeg_available():
            self.status.set("MP3 precisa do FFmpeg instalado")
        elif self.status.get() == "MP3 precisa do FFmpeg instalado":
            self.status.set("Pronto para começar")

    def _input_changed(self, *_args: Any) -> None:
        self.current_metadata = None
        self.detected_type.set("Tipo: aguardando an\u00e1lise")
        self.lab_report.set("")
        self.lab_report_path = None
        self.quality.set("Melhor disponível")
        self.quality_combo.configure(values=QUALITY_PRESETS)
        if not self.working:
            self.result_title.configure(text="Os detalhes do vídeo aparecerão aqui")
            self.result_subtitle.configure(text="Plataforma  —     Duração  —     Resolução  —")
            self.status.set("Pronto para começar")
        self._sync_buttons()

    def _sync_buttons(self) -> None:
        if self.working:
            self.analyze_button.configure(state="disabled", text="Processando…")
            self.download_button.configure(state="disabled")
            self.url_entry.configure(state="disabled")
            self.paste_button.configure(state="disabled")
            self.folder_button.configure(state="disabled")
            for button in self.format_buttons.values():
                button.configure(state="disabled")
            self.quality_combo.configure(state="disabled")
        else:
            self.cancel_button.pack_forget()
            self.analyze_button.configure(state="normal", text="Analisar link  →")
            self.url_entry.configure(state="normal")
            self.paste_button.configure(state="normal")
            self.folder_button.configure(state="normal")
            for button in self.format_buttons.values():
                button.configure(state="normal")
            self.quality_combo.configure(state="disabled" if self.format.get() in {"MP3", "Imagem"} else "readonly")
            can_download = bool(self.current_metadata and self.legal_confirmed.get())
            self.download_button.configure(state="normal" if can_download else "disabled",
                                           bg=ACCENT if can_download else PANEL_SOFT,
                                           fg=BG if can_download else MUTED,
                                           activebackground=ACCENT_HOVER if can_download else PANEL_SOFT)

    def _paste_clipboard(self) -> None:
        try:
            text = self.root.clipboard_get()
        except tk.TclError:
            return
        self.url.set(text.strip())
        self.url_entry.focus_set()

    def _choose_folder(self) -> None:
        chosen = filedialog.askdirectory(initialdir=self.download_dir.get(), title="Escolha onde salvar")
        if chosen:
            self.download_dir.set(chosen)
            _save_settings({**_load_settings(), "download_dir": chosen})

    def _open_folder(self) -> None:
        folder = Path(self.download_dir.get())
        folder.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "nt":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
        except OSError as exc:
            messagebox.showerror("Não foi possível abrir a pasta", str(exc), parent=self.root)

    def _check_updates(self) -> None:
        if self.update_working:
            return
        self.update_working = True
        self.update_check_button.configure(state="disabled")
        self.update_install_button.configure(state="disabled")
        self.update_status_label.configure(text="Consultando o canal de atualizações…", fg=MUTED)
        threading.Thread(target=self._check_updates_worker, daemon=True).start()

    def _check_updates_worker(self) -> None:
        try:
            manifest = _read_update_manifest()
            latest = str(manifest["version"])
            if _version_tuple(latest) <= _version_tuple(APP_VERSION):
                message = f"Você já está usando a versão mais recente ({APP_VERSION})."
                self.root.after(0, lambda: self._update_check_finished(message, None))
                return
            message = f"Versão {latest} disponível. Baixe e instale sobre esta mesma instalação."
            self.root.after(0, lambda: self._update_check_finished(message, manifest))
        except Exception as exc:
            message = str(exc).strip() or "Não foi possível verificar atualizações."
            self.root.after(0, lambda msg=message: self._update_check_finished(msg, None, error=True))

    def _update_check_finished(self, message: str, manifest: dict[str, Any] | None, error: bool = False) -> None:
        self.update_working = False
        self.update_manifest = manifest
        self.update_check_button.configure(state="normal")
        self.update_install_button.configure(state="normal")
        self.update_status_label.configure(text=message, fg=RED if error else TEXT)

    def _install_latest(self) -> None:
        """Check the channel and install the newest version from this button."""
        if self.update_working:
            return
        if self.update_manifest and _version_tuple(str(self.update_manifest.get("version", "0"))) > _version_tuple(APP_VERSION):
            self._install_update()
            return
        self.update_working = True
        self.update_check_button.configure(state="disabled")
        self.update_install_button.configure(state="disabled")
        self.update_status_label.configure(text="Verificando a versão mais recente…", fg=MUTED)
        threading.Thread(target=self._check_then_prompt_update, daemon=True).start()

    def _check_then_prompt_update(self) -> None:
        try:
            manifest = _read_update_manifest()
            latest = str(manifest["version"])
            if _version_tuple(latest) <= _version_tuple(APP_VERSION):
                message = f"Você já está usando a versão mais recente ({APP_VERSION})."
                self.root.after(0, lambda: self._update_check_finished(message, None))
                return
            message = f"Versão {latest} disponível. Preparando a atualização…"
            self.root.after(0, lambda: self._prompt_update_from_manifest(message, manifest))
        except Exception as exc:
            message = str(exc).strip() or "Não foi possível verificar atualizações."
            self.root.after(0, lambda msg=message: self._update_check_finished(msg, None, error=True))

    def _prompt_update_from_manifest(self, message: str, manifest: dict[str, Any]) -> None:
        self.update_working = False
        self.update_manifest = manifest
        self.update_status_label.configure(text=message, fg=TEXT)
        self._install_update()

    def _install_update(self) -> None:
        if self.update_working or not self.update_manifest:
            return
        if not messagebox.askyesno(
            "Atualizar ClipLink",
            f"Baixar a versão {self.update_manifest['version']} e atualizar a instalação atual?",
            parent=self.root,
        ):
            return
        self.update_working = True
        self.update_check_button.configure(state="disabled")
        self.update_install_button.configure(state="disabled")
        self.update_status_label.configure(text="Baixando o instalador da atualização…", fg=MUTED)
        threading.Thread(target=self._install_update_worker, args=(self.update_manifest,), daemon=True).start()

    def _install_update_worker(self, manifest: dict[str, Any]) -> None:
        try:
            installer = _download_update_installer(manifest)
            app_dir = Path(sys.executable).resolve().parent
            subprocess.Popen(
                [str(installer), "--silent", "--target", str(app_dir), "--open-after"],
                cwd=str(app_dir),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000),
            )
            self.root.after(0, self.root.destroy)
        except Exception as exc:
            message = str(exc).strip() or "Não foi possível instalar a atualização."
            self.root.after(0, lambda msg=message: self._update_install_failed(msg))

    def _update_install_failed(self, message: str) -> None:
        self.update_working = False
        self.update_check_button.configure(state="normal")
        self.update_install_button.configure(state="normal" if self.update_manifest else "disabled")
        self.update_status_label.configure(text=message, fg=RED)

    @staticmethod
    def _ffmpeg_available() -> bool:
        return bool(media_tool("ffmpeg.exe" if os.name == "nt" else "ffmpeg"))

    def _inspect(self) -> None:
        if self.working:
            return
        raw_url = self.url.get().strip()
        if not raw_url:
            messagebox.showinfo("Cole um link", "Adicione um link público para começar.", parent=self.root)
            return
        try:
            safe_url = validate_url(raw_url)
        except ValueError as exc:
            messagebox.showerror("Link inválido", str(exc), parent=self.root)
            return
        self._start_work("Analisando link…")
        threading.Thread(
            target=self._inspect_worker,
            args=(safe_url, self.lab_mode.get()),
            daemon=True,
        ).start()

    def _inspect_worker(self, safe_url: str, lab_mode: bool = False) -> None:
        try:
            import yt_dlp
            from yt_dlp.utils import DownloadError

            with yt_dlp.YoutubeDL(_base_options()) as ydl:
                info = ydl.extract_info(safe_url, download=False)
            if not isinstance(info, dict):
                raise DownloadError("Não encontrei um vídeo neste link.")
            _check_content_scope(info, safe_url)
            metadata = _safe_metadata(info, safe_url)
            report_path = _write_lab_report(safe_url, info, metadata) if lab_mode else None
            self.root.after(0, lambda report=report_path: self._inspect_success(metadata, report))
        except ImportError:
            self.root.after(0, lambda: self._work_error("O motor de download não foi carregado. Reinstale o ClipLink."))
        except Exception as exc:
            message = self._friendly_error(exc)
            self.root.after(0, lambda msg=message: self._work_error(msg))

    def _inspect_success(self, metadata: dict[str, Any], report_path: Path | None = None) -> None:
        self.working = False
        self.current_metadata = metadata
        self.lab_report_path = report_path
        if report_path:
            self.lab_report.set(f"Relatório do laboratório salvo em: {report_path}")
        elif self.lab_mode.get():
            self.lab_report.set("Modo laboratório ativo, mas não foi possível salvar o relatório local.")
        else:
            self.lab_report.set("")
        kind_labels = {
            "video": "Tipo detectado: v\u00eddeo",
            "story": "Tipo detectado: story",
            "image": "Tipo detectado: imagem original",
        }
        self.detected_type.set(kind_labels.get(metadata.get("media_kind"), "Tipo detectado: conte\u00fado"))
        if metadata.get("media_kind") == "image":
            self.format.set("Imagem")
            self._update_format_buttons()
            self.quality_combo.configure(state="disabled")
        qualities = _quality_values(metadata.get("available_heights", []))
        self.quality_combo.configure(values=qualities)
        if self.quality.get() not in qualities:
            self.quality.set("Melhor disponível")
        self.result_title.configure(text=metadata["title"])
        height = f"Até {metadata['max_height']}p" if metadata["max_height"] else "Resolução variável"
        self.result_subtitle.configure(
            text=f"{metadata['platform']}     ·     {_duration_label(metadata['duration'])}     ·     {height}"
        )
        if metadata.get("media_kind") == "image":
            self.result_subtitle.configure(text=f"{metadata['platform']}     Â·     Imagem original")
        elif metadata.get("media_kind") == "story":
            self.result_subtitle.configure(
                text=f"{metadata['platform']}     Â·     Story     Â·     {_duration_label(metadata['duration'])}"
            )
        for child in self.result_title.master.winfo_children():
            if isinstance(child, tk.Frame):
                for item in child.winfo_children():
                    if isinstance(item, tk.Label):
                        item.configure(text="LINK PÚBLICO IDENTIFICADO", fg=ACCENT)
        self.status.set("Link pronto para download")
        self.progress.configure(value=0)
        self.progress_percent.configure(text="")
        self._sync_buttons()

    def _download(self) -> None:
        if self.working or not self.current_metadata:
            return
        if not self.legal_confirmed.get():
            return
        if self.format.get() == "MP3" and not self._ffmpeg_available():
            messagebox.showwarning("FFmpeg necessário", "Instale o FFmpeg ou adicione ffmpeg.exe à pasta tools antes de extrair MP3.", parent=self.root)
            return
        try:
            safe_url = validate_url(self.url.get().strip())
            folder = Path(self.download_dir.get())
            _save_settings({**_load_settings(), "download_dir": str(folder)})
            folder.mkdir(parents=True, exist_ok=True)
            if not folder.is_dir():
                raise OSError("A pasta escolhida não está disponível.")
        except (ValueError, OSError) as exc:
            messagebox.showerror("Verifique o link ou a pasta", str(exc), parent=self.root)
            return
        self.cancel_requested = False
        self._start_work("Preparando download…", allow_cancel=True)
        threading.Thread(
            target=self._download_worker,
            args=(safe_url, folder, self.quality.get(), self.format.get()),
            daemon=True,
        ).start()

    def _download_worker(self, safe_url: str, folder: Path, quality: str, media_format: str) -> None:
        started_at = time.time()
        try:
            import yt_dlp
            from yt_dlp.utils import DownloadError

            # Resolve again at the point of download to avoid relying on the earlier inspection.
            safe_url = validate_url(safe_url)
            options = _base_options()
            options.update({
                "format": "bestaudio/best" if media_format == "MP3" else _format_selector(quality, media_format),
                "paths": {"home": str(folder)},
                "outtmpl": {"default": "%(title).90B [%(id)s].%(ext)s"},
                "merge_output_format": "mp4",
                "progress_hooks": [self._progress_hook],
            })
            if media_format == "MP3":
                options["postprocessors"] = [{
                    "key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"
                }]
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(safe_url, download=False)
                if not isinstance(info, dict):
                    raise DownloadError("Não encontrei um vídeo neste link.")
                _check_content_scope(info, safe_url)
                metadata = _safe_metadata(info, safe_url)
                effective_format = "Imagem" if metadata["media_kind"] == "image" else media_format
                if effective_format == "Imagem":
                    ydl.params["format"] = "best"
                    ydl.params.pop("merge_output_format", None)
                    ydl.params.pop("postprocessors", None)
                info = ydl.extract_info(safe_url, download=True)
                if not isinstance(info, dict):
                    raise DownloadError("O download não foi concluído.")
                output = _confine_output_path(Path(ydl.prepare_filename(info)), folder)
            if effective_format == "MP3":
                output = _confine_output_path(output.with_suffix(".mp3"), folder)
            elif effective_format != "Imagem" and output.suffix.lower() not in {".mp4", ".m4v"}:
                merged = output.with_suffix(".mp4")
                if merged.exists():
                    output = _confine_output_path(merged, folder)
            if not output.exists():
                candidates = [
                    p for p in folder.iterdir()
                    if p.is_file() and not p.name.endswith((".part", ".ytdl"))
                    and p.stat().st_mtime >= started_at
                ]
                if not candidates:
                    raise DownloadError("Não encontrei o arquivo final na pasta escolhida.")
                output = _confine_output_path(max(candidates, key=lambda p: p.stat().st_mtime), folder)
            self.root.after(0, lambda path=output: self._download_success(path))
        except Exception as exc:
            self._cleanup_partial_files(folder, started_at)
            if self.cancel_requested:
                self.root.after(0, lambda: self._work_error("Download cancelado."))
            else:
                message = self._friendly_error(exc)
                self.root.after(0, lambda msg=message: self._work_error(msg))

    @staticmethod
    def _cleanup_partial_files(folder: Path, started_at: float) -> None:
        """Remove only partial files created by the current download attempt."""
        try:
            for path in folder.iterdir():
                if not path.is_file() or path.suffix.lower() not in {".part", ".ytdl"}:
                    continue
                try:
                    if path.stat().st_mtime >= started_at:
                        path.unlink()
                except OSError:
                    continue
        except OSError:
            return

    def _progress_hook(self, data: dict[str, Any]) -> None:
        if self.cancel_requested:
            from yt_dlp.utils import DownloadError
            raise DownloadError("Download cancelado.")
        if data.get("status") == "downloading":
            total = data.get("total_bytes") or data.get("total_bytes_estimate")
            downloaded = data.get("downloaded_bytes", 0)
            value = round(min(99, (downloaded / total) * 100)) if total else 0
            self.root.after(0, lambda progress=value: self._set_progress(progress))
        elif data.get("status") == "finished":
            self.root.after(0, lambda: self._set_progress(99, "Finalizando arquivo…"))

    def _set_progress(self, value: int, status: str | None = None) -> None:
        self.progress.configure(value=value)
        self.progress_percent.configure(text=f"{value}%" if value < 100 else "")
        if status:
            self.status.set(status)
        elif value < 100:
            self.status.set("Baixando arquivo…")

    def _download_success(self, path: Path) -> None:
        self.working = False
        self.cancel_button.pack_forget()
        self.progress.configure(value=100)
        self.progress_percent.configure(text="100%")
        self.status.set("Download concluído")
        self._remember_download(path)
        if self.lab_report_path and _append_lab_evidence(self.lab_report_path, path):
            self.lab_report.set(f"Evidência adicionada ao relatório: {path.name}")
        self._sync_buttons()
        messagebox.showinfo("Arquivo salvo", f"Download concluído em:\n{path}", parent=self.root)

    def _start_work(self, text: str, allow_cancel: bool = False) -> None:
        self.working = True
        self.status.set(text)
        self.progress.configure(value=0)
        self.progress_percent.configure(text="")
        if allow_cancel:
            self.cancel_button.pack(side="right", padx=(0, 8))
        else:
            self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self._sync_buttons()

    def _cancel_download(self) -> None:
        self.cancel_requested = True
        self.status.set("Cancelando download…")
        self.cancel_button.configure(state="disabled")

    def _work_error(self, message: str) -> None:
        self.working = False
        self.cancel_button.pack_forget()
        self.cancel_button.configure(state="normal")
        self.status.set("Não foi possível concluir")
        self._sync_buttons()
        messagebox.showerror("ClipLink", message, parent=self.root)

    @staticmethod
    def _friendly_error(exc: Exception) -> str:
        text = str(exc).strip()
        lowered = text.lower()
        if "unexpected response from webpage request" in lowered or "unable to extract webpage" in lowered:
            return (
                "O site não enviou os dados do vídeo em um formato reconhecido. "
                "Plataformas podem mudar ou limitar esse acesso. Tente novamente mais tarde; "
                "se o erro persistir, atualize o ClipLink ou teste outro link."
            )
        if "FFmpeg" in text or "ffmpeg" in text.lower():
            return "Este formato precisa do FFmpeg. Instale o FFmpeg ou coloque ffmpeg.exe na pasta tools."
        if "requested format is not available" in lowered:
            return "A plataforma não disponibilizou a resolução escolhida neste link. Selecione ‘Melhor disponível’ ou uma resolução menor e tente novamente."
        if "javascript runtime" in lowered or "no supported javascript runtime" in lowered:
            return "Este vídeo precisa do componente JavaScript do ClipLink. Reinstale a versão mais recente para ativar o suporte ao YouTube."
        if "sign in to confirm" in lowered or "not a bot" in lowered:
            return "O YouTube bloqueou esta solicitação automática. Tente outro link público ou novamente mais tarde."
        if "403" in text or "429" in text or "too many requests" in text.lower():
            return "O site recusou a solicitação ou limitou tentativas. Tente novamente mais tarde."
        if "cancelado" in text.lower():
            return "Download cancelado."
        return (text[:360] if text else "O site não disponibilizou este vídeo para download.")

    def _close(self) -> None:
        if self.working:
            answer = messagebox.askyesno("Fechar ClipLink", "Um processo está em andamento. Deseja fechar o aplicativo?", parent=self.root)
            if not answer:
                return
            self.cancel_requested = True
        self.root.destroy()


def _set_windows_app_id() -> None:
    """Give the window a ClipLink identity so Windows uses its own taskbar icon."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ClipLink.Desktop")
    except (AttributeError, OSError):
        pass


def main() -> None:
    _set_windows_app_id()
    root = tk.Tk()
    ClipLinkApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
