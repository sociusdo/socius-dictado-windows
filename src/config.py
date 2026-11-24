"""Settings (JSON in %APPDATA%) + the OpenAI API key (Windows Credential Manager).

The API key is a secret: it lives in the Windows Credential Locker via `keyring`,
never in a file or the repo.
"""
from __future__ import annotations
import json
import os
from typing import Any

import paths

_SERVICE = "SociusDictado"
_ACCOUNT = "openai_api_key"

_DEFAULTS: dict[str, Any] = {
    "model": "gpt-4o-mini-transcribe",   # or "gpt-4o-transcribe"
    "language": "auto",                   # auto | es | en
    "ai_mode": "none",                    # none | clean | bullets | email | translate_en
    "dictionary": "",                     # one term per line
    "purple_hex": "#6D28D9",
    "sound": True,
    "launch_at_login": False,
    "hotkey_dictate": "ctrl+shift+space",
    "hotkey_toggle": "ctrl+shift+d",
}


def _load() -> dict[str, Any]:
    try:
        with open(paths.config_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        merged = dict(_DEFAULTS)
        merged.update({k: v for k, v in data.items() if k in _DEFAULTS})
        return merged
    except Exception:
        return dict(_DEFAULTS)


def _save(data: dict[str, Any]) -> None:
    try:
        with open(paths.config_file(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def get(key: str) -> Any:
    return _load().get(key, _DEFAULTS.get(key))


def set(key: str, value: Any) -> None:
    data = _load()
    data[key] = value
    _save(data)


# ---- API key (secret) ----

def get_api_key() -> str | None:
    # 1) Credential Manager
    try:
        import keyring
        k = keyring.get_password(_SERVICE, _ACCOUNT)
        if k:
            return k
    except Exception:
        pass
    # 2) Environment fallback (useful for first-run / CI)
    return os.environ.get("OPENAI_API_KEY") or None


def set_api_key(key: str) -> bool:
    key = (key or "").strip()
    if not key:
        return False
    try:
        import keyring
        keyring.set_password(_SERVICE, _ACCOUNT, key)
        return True
    except Exception:
        return False


def has_api_key() -> bool:
    return bool(get_api_key())
