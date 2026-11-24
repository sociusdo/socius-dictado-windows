"""Global keyboard shortcuts via the `keyboard` library (Windows-friendly, no admin
needed for these combos). Callbacks are marshalled to the Qt thread by the caller.
"""
from __future__ import annotations
from typing import Callable

import config


class HotKeys:
    def __init__(self) -> None:
        self._registered = []

    def reload(self, on_dictate: Callable[[], None], on_toggle: Callable[[], None]) -> None:
        import keyboard
        self.clear()
        try:
            self._registered.append(
                keyboard.add_hotkey(config.get("hotkey_dictate"), on_dictate, suppress=False))
            self._registered.append(
                keyboard.add_hotkey(config.get("hotkey_toggle"), on_toggle, suppress=False))
        except Exception:
            pass

    def clear(self) -> None:
        try:
            import keyboard
            for h in self._registered:
                try:
                    keyboard.remove_hotkey(h)
                except Exception:
                    pass
        except Exception:
            pass
        self._registered = []
