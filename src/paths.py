"""App data paths (Windows: %APPDATA%\\SociusDictado)."""
from __future__ import annotations
import os
from pathlib import Path


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
