"""Socius branding colors (mirrors the macOS app)."""
from __future__ import annotations

PURPLE = "#6D28D9"      # brand purple
NEAR_BLACK = "#0B0B0D"
RECORDING = "#EF4444"   # red while recording
SUCCESS = "#22C55E"     # green ~1s when pasted
WARNING = "#F59E0B"     # amber = copied but not pasted


def adjust(hex_color: str, delta: float) -> str:
    """Shift brightness by delta (-1..1), keeping hue. Returns #rrggbb."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    import colorsys
    hh, ll, ss = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
    ll = max(0.0, min(1.0, ll + delta))
    r, g, b = colorsys.hls_to_rgb(hh, ll, ss)
    return "#{:02x}{:02x}{:02x}".format(int(r * 255), int(g * 255), int(b * 255))
