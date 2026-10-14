"""Paths used by the installed ClipLink application.

The desktop build is intentionally self-contained: runtime data lives beside
the executable so an installation on D: does not create application data in
the user's C: profile.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def app_data_dir() -> Path:
    path = app_root() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path
