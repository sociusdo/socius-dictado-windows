"""Main window: Historial (search, multi-select delete, export, detail) and
Ajustes (model, language, AI mode, dictionary, API key, color, sound, launch at
login, usage). PyQt6."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QTextEdit, QPushButton, QLabel, QComboBox, QPlainTextEdit,
    QCheckBox, QFormLayout, QFileDialog, QSplitter, QApplication)

import ai
import config
import store as store_mod
import theme

MODELS = [("Rápido  (gpt-4o-mini-transcribe)", "gpt-4o-mini-transcribe"),
          ("Preciso  (gpt-4o-transcribe)", "gpt-4o-transcribe")]
LANGS = [("Automático", "auto"), ("Español", "es"), ("Inglés", "en")]


class MainWindow(QTabWidget):
    def __init__(self, store: store_mod.Store, ctrl, quit_app):
        super().__init__()
        self.store = store
        self.ctrl = ctrl
        self.quit_app = quit_app
        self.setWindowTitle("Socius Dictado")
        self.resize(760, 560)
        self.history = HistoryTab(store)
        self.settings = SettingsTab(store, quit_app)
        self.addTab(self.history, "Historial")
        self.addTab(self.settings, "Ajustes")
        ctrl.history_changed.connect(self.history.refresh)
        ctrl.history_changed.connect(self.settings.refresh_usage)

    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show(); self.raise_(); self.activateWindow()
        _force_foreground(int(self.winId()))

    def show_settings(self):
        self.setCurrentWidget(self.settings)
        self.show_window()


class HistoryTab(QWidget):
    def __init__(self, store: store_mod.Store):
        super().__init__()
        self.store = store
        root = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Buscar")
        self.search.textChanged.connect(self.refresh)
        self.del_btn = QPushButton("Borrar marcadas"); self.del_btn.clicked.connect(self._delete_checked)
        self.exp_btn = QPushButton("Exportar"); self.exp_btn.clicked.connect(self._export)
        self.clr_btn = QPushButton("Borrar todo"); self.clr_btn.clicked.connect(self._clear)
        for w in (self.search, self.del_btn, self.exp_btn, self.clr_btn):
            bar.addWidget(w)
        root.addLayout(bar)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show_detail)
        self.detail = QTextEdit(); self.detail.setReadOnly(True)
        split.addWidget(self.list); split.addWidget(self.detail)
        split.setSizes([320, 440])
        root.addWidget(split, 1)

        self.refresh()

    def _filtered(self):
        q = self.search.text().strip().lower()
        return [i for i in self.store.items if not q or q in i.text.lower()]

    def refresh(self):
        self.list.clear()
        for it in self._filtered():
            li = QListWidgetItem(f"{it.title}\n{it.text[:60]}\n{it.date_display()} · "
                                 f"{it.duration_display()} · {it.words} palabras")
            li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            li.setCheckState(Qt.CheckState.Unchecked)
            li.setData(Qt.ItemDataRole.UserRole, it.id)
            self.list.addItem(li)

    def _show_detail(self, cur, _prev=None):
        if not cur:
            self.detail.clear(); return
        _id = cur.data(Qt.ItemDataRole.UserRole)
        it = next((i for i in self.store.items if i.id == _id), None)
        if it:
            self.detail.setPlainText(f"{it.title}\n{it.date_display()} · "
                                     f"{it.duration_display()} · {it.words} palabras\n\n{it.text}")

    def _checked_ids(self) -> set[str]:
        ids = set()
        for r in range(self.list.count()):
            li = self.list.item(r)
            if li.checkState() == Qt.CheckState.Checked:
                ids.add(li.data(Qt.ItemDataRole.UserRole))
        return ids

    def _delete_checked(self):
        ids = self._checked_ids()
        if ids:
            self.store.delete_many(ids); self.refresh()

    def _clear(self):
        self.store.clear(); self.refresh(); self.detail.clear()

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar historial", "socius-dictado.md",
                                              "Markdown (*.md)")
        if not path:
            return
        md = "\n---\n\n".join(
            f"## {it.title}\n{it.date_display()} · {it.duration_display()} · {it.words} palabras\n\n{it.text}\n"
            for it in self.store.items)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(md)
        except Exception:
            pass


class SettingsTab(QWidget):
    def __init__(self, store: store_mod.Store, quit_app):
        super().__init__()
        self.store = store
        self.quit_app = quit_app
        form = QFormLayout(self)

        self.model = QComboBox()
        for label, val in MODELS:
            self.model.addItem(label, val)
        self.model.setCurrentIndex(max(0, [v for _, v in MODELS].index(config.get("model")) if config.get("model") in [v for _, v in MODELS] else 0))
        self.model.currentIndexChanged.connect(lambda: config.set("model", self.model.currentData()))
        form.addRow("Modelo", self.model)

        self.lang = QComboBox()
        for label, val in LANGS:
            self.lang.addItem(label, val)
        self.lang.setCurrentIndex([v for _, v in LANGS].index(config.get("language")) if config.get("language") in [v for _, v in LANGS] else 0)
        self.lang.currentIndexChanged.connect(lambda: config.set("language", self.lang.currentData()))
        form.addRow("Idioma", self.lang)

        self.mode = QComboBox()
        for key, label in ai.MODE_TITLES.items():
            self.mode.addItem(label, key)
        keys = list(ai.MODE_TITLES.keys())
        self.mode.setCurrentIndex(keys.index(config.get("ai_mode")) if config.get("ai_mode") in keys else 0)
        self.mode.currentIndexChanged.connect(lambda: config.set("ai_mode", self.mode.currentData()))
        form.addRow("Modo IA (antes de pegar)", self.mode)

        self.dict = QPlainTextEdit(config.get("dictionary") or "")
        self.dict.setFixedHeight(80)
        self.dict.textChanged.connect(lambda: config.set("dictionary", self.dict.toPlainText()))
        form.addRow("Diccionario (uno por línea)", self.dict)

        self.key = QLineEdit(); self.key.setEchoMode(QLineEdit.EchoMode.Password)
        self.key.setPlaceholderText("sk-… (se guarda en el Credential Manager)")
        key_row = QHBoxLayout()
        save = QPushButton("Guardar key"); save.clicked.connect(self._save_key)
        self.key_status = QLabel("✅ Configurada" if config.has_api_key() else "⚠️ Falta la API key")
        kw = QWidget(); kw.setLayout(key_row); key_row.addWidget(self.key); key_row.addWidget(save); key_row.addWidget(self.key_status)
        form.addRow("API key OpenAI", kw)

        self.sound = QCheckBox("Sonido al empezar/terminar"); self.sound.setChecked(bool(config.get("sound")))
        self.sound.stateChanged.connect(lambda: config.set("sound", self.sound.isChecked()))
        form.addRow("", self.sound)

        self.login = QCheckBox("Arrancar al iniciar sesión"); self.login.setChecked(bool(config.get("launch_at_login")))
        self.login.stateChanged.connect(self._toggle_login)
        form.addRow("", self.login)

        self.color = QLineEdit(config.get("purple_hex") or theme.PURPLE)
        self.color.editingFinished.connect(self._set_color)
        form.addRow("Color (hex)", self.color)

        self.usage = QLabel()
        form.addRow("Uso", self.usage)
        self.refresh_usage()

        self.hk = QLabel("Dictar: Ctrl+Shift+Espacio    ·    Mostrar/ocultar: Ctrl+Shift+D")
        form.addRow("Atajos", self.hk)

        quit_btn = QPushButton("Salir de Socius Dictado"); quit_btn.clicked.connect(self.quit_app)
        form.addRow("", quit_btn)

    def refresh_usage(self):
        items = self.store.items
        mins = sum(i.duration for i in items) / 60.0
        cost = sum((i.duration / 60.0) * (0.003 if "mini" in i.model else 0.006) for i in items)
        self.usage.setText(f"{len(items)} dictados · {mins:.1f} min · ≈${cost:.3f}")

    def showEvent(self, e):
        self.refresh_usage()
        super().showEvent(e)

    def _set_color(self):
        from PyQt6.QtGui import QColor
        txt = self.color.text().strip()
        if not QColor(txt).isValid():
            self.color.setText(config.get("purple_hex") or theme.PURPLE)
            return
        config.set("purple_hex", txt)
        for w in QApplication.topLevelWidgets():   # repaint the orb with the new color
            w.update()

    def _save_key(self):
        if config.set_api_key(self.key.text()):
            self.key.clear(); self.key_status.setText("✅ Configurada")

    def _toggle_login(self):
        on = self.login.isChecked()
        config.set("launch_at_login", on)
        try:
            set_launch_at_login(on)
        except Exception:
            pass


def _force_foreground(hwnd: int) -> None:
    """Bring our window to the front. The orb never takes focus (so pasting lands in
    the user's app), which means Windows' foreground lock refuses a plain
    SetForegroundWindow and the window opens *behind* the active app. Briefly
    attaching to the foreground thread's input is the standard workaround."""
    try:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.AttachThreadInput.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL]
        user32.BringWindowToTop.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        fg = user32.GetForegroundWindow()
        fg_tid = user32.GetWindowThreadProcessId(fg, None) if fg else 0
        me = kernel32.GetCurrentThreadId()
        attached = bool(fg_tid and fg_tid != me and user32.AttachThreadInput(me, fg_tid, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(me, fg_tid, False)
    except Exception:
        pass


def set_launch_at_login(enable: bool) -> None:
    """Windows: HKCU Run key pointing at the running exe."""
    import sys
    import winreg
    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    name = "SociusDictado"
    import os
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'            # PyInstaller .exe
    else:                                      # running from source: pythonw + main.py
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        main_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")
        cmd = f'"{pyw}" "{main_py}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key, 0, winreg.KEY_SET_VALUE) as k:
        if enable:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass
