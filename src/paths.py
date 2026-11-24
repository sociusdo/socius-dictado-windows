"""App data paths (Windows: %APPDATA%\\SociusDictado)."""
from __future__ import annotations
import os
import sys
from pathlib import Path


def resource_path(rel: str) -> str:
    """Path to a bundled resource, working both from source and from the
    PyInstaller onefile .exe (which unpacks data under sys._MEIPASS)."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return str(Path(base) / rel)
    return str(Path(__file__).resolve().parent / rel)


def app_icon() -> str:
    return resource_path("assets/icon.png")


def app_dir() -> Path:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    d = Path(base) / "SociusDictado"
    d.mkdir(parents=True, exist_ok=True)
    return d


def history_file() -> Path:
    return app_dir() / "history.json"


def config_file() -> Path:
    return app_dir() / "config.json"


def debug_log() -> Path:
    return app_dir() / "debug.log"


def temp_dir() -> Path:
    d = app_dir() / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d
