"""Socius Dictado (Windows) — entry point.

Floating purple mic orb that records your voice, transcribes it with OpenAI and
pastes it where your cursor is. Runs as a tray app (no taskbar window).
"""
from __future__ import annotations
import logging
import sys

import paths

logging.basicConfig(
    filename=str(paths.debug_log()), level=logging.INFO, encoding="utf-8",
    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
sys.excepthook = lambda t, v, tb: logging.getLogger("crash").error("unhandled", exc_info=(t, v, tb))

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QAction
from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox

import config
import theme
from store import Store
from controller import Controller
from orb import Orb
from window import MainWindow
from hotkeys import HotKeys


def _tray_icon() -> QIcon:
    pm = QPixmap(32, 32); pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(config.get("purple_hex") or theme.PURPLE)); p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(3, 3, 26, 26); p.end()
    return QIcon(pm)


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # tray app: closing the window keeps the orb

    store = Store()
    ctrl = Controller(store)
    window = MainWindow(store, ctrl, app.quit)
    ctrl.open_window = window.show_window

    orb = Orb(ctrl, window.show_window, window.show_settings, app.quit)
    orb.show()

    # Tray
    tray = QSystemTrayIcon(_tray_icon(), app)
    tray.setToolTip("Socius Dictado")
    menu = QMenu()
    menu.addAction("Abrir ventana", window.show_window)
    menu.addAction("Mostrar / ocultar círculo", lambda: orb.setVisible(not orb.isVisible()))
    menu.addAction("Ajustes", window.show_settings)
    menu.addSeparator()
    menu.addAction("Salir", app.quit)
    tray.setContextMenu(menu)
    tray.show()

    # Needs-key prompt
    def on_need_key():
        QMessageBox.information(window, "Falta la API key",
                                "Agrega tu API key de OpenAI en Ajustes para poder dictar.")
        window.show_settings()
    ctrl.need_key_signal.connect(on_need_key)

    # Global hotkeys (callbacks come from another thread -> emit signals)
    ctrl.trigger_toggle_window.connect(lambda: orb.setVisible(not orb.isVisible()))
    hk = HotKeys()
    hk.reload(on_dictate=lambda: ctrl.trigger_primary.emit(),
              on_toggle=lambda: ctrl.trigger_toggle_window.emit())
    app.aboutToQuit.connect(hk.clear)

    # First run: no key yet -> open settings so the user can paste it.
    if not config.has_api_key():
        window.show_settings()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
