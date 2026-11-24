"""Clipboard + paste at the cursor on Windows.

Unlike macOS, Windows needs NO special accessibility permission to synthesize
Ctrl+V — a normal desktop app can do it. We always copy first (so manual Ctrl+V
is a fallback), then send the keystroke.
"""
from __future__ import annotations
import time

import pyperclip


def copy(text: str) -> None:
    try:
        pyperclip.copy(text)
    except Exception:
        pass


def paste_at_cursor(text: str) -> bool:
    """Copy text and simulate Ctrl+V. Returns True if the keystroke was sent."""
    copy(text)
    time.sleep(0.05)   # let the clipboard settle
    try:
        import keyboard
        keyboard.send("ctrl+v")
        return True
    except Exception:
        # Fallback: the text is on the clipboard; user can paste manually.
        return False
