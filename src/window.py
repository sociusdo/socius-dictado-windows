"""Main window: Historial (search, multi-select delete, export, editable detail
with version history), Transcribir archivos (drag-and-drop, ordered, combined),
and Ajustes. PyQt6."""
from __future__ import annotations

import os
import threading
from datetime import datetime

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QTabWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLineEdit, QTextEdit, QPushButton, QLabel, QComboBox, QPlainTextEdit,
    QCheckBox, QFormLayout, QFileDialog, QSplitter, QApplication, QDialog)

import ai
import config
import store as store_mod
import theme

MODELS = [("Rápido  (gpt-4o-mini-transcribe)", "gpt-4o-mini-transcribe"),
          ("Preciso  (gpt-4o-transcribe)", "gpt-4o-transcribe")]
LANGS = [("Automático", "auto"), ("Español", "es"), ("Inglés", "en")]

AUDIO_EXTS = {"m4a", "m4b", "mp3", "mpga", "mpeg", "mpg", "wav", "caf", "aiff",
              "aif", "mp4", "mov", "oga", "ogg", "opus", "flac", "webm", "amr", "3gp"}


def _fmt_iso(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).strftime("%d %b %Y, %I:%M %p")
    except Exception:
        return iso


def _rgba(hex_color: str, a: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{a})"


def _app_qss(accent: str) -> str:
    """A measured, system-font theme with the Socius accent. Uses palette() for
    neutrals so it adapts to the user's light/dark Windows theme; only the accent,
    radii, spacing and selection are opinionated."""
    hover = theme.adjust(accent, -0.06)
    tint = _rgba(accent, 0.14)
    return f"""
    * {{ font-family: 'Segoe UI', system-ui, sans-serif; font-size: 13px; }}
    QTabWidget::pane {{ border: none; }}
    QTabBar {{ qproperty-drawBase: 0; }}
    QTabWidget::tab-bar {{ alignment: center; }}
    /* Pill-style segmented tabs: selected on the accent, like the macOS app. */
    QTabBar::tab {{
        background: transparent; color: palette(text);
        padding: 7px 16px; margin: 4px 2px; border: none; border-radius: 9px;
    }}
    QTabBar::tab:selected {{ background: {accent}; color: white; font-weight: 600; }}
    QTabBar::tab:hover:!selected {{ background: {tint}; }}

    QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{
        border: 1px solid palette(mid); border-radius: 8px; padding: 6px 9px;
        selection-background-color: {accent}; selection-color: white;
    }}
    QLineEdit:focus, QComboBox:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {accent};
    }}
    QComboBox::drop-down {{ border: none; width: 22px; }}

    /* History list as cards: each row a rounded tile. */
    QListWidget {{ border: none; background: transparent; padding: 2px; outline: none; }}
    QListWidget::item {{
        border-radius: 11px; padding: 10px 11px; margin: 3px 2px;
        background: rgba(127,127,127,0.08);
    }}
    QListWidget::item:hover {{ background: {tint}; }}
    QListWidget::item:selected {{ background: {_rgba(accent, 0.16)}; color: palette(text); }}

    QPushButton {{
        border: 1px solid palette(mid); border-radius: 8px; padding: 6px 13px;
        background: palette(button);
    }}
    QPushButton:hover {{ background: {tint}; border: 1px solid {accent}; }}
    QPushButton:pressed {{ background: {_rgba(accent, 0.22)}; }}
    QPushButton:disabled {{ color: palette(mid); border: 1px solid palette(midlight); }}

    /* Primary action: filled accent gradient, white text. */
    QPushButton[accent="true"] {{
        border: 1px solid {theme.adjust(accent, -0.10)}; border-radius: 8px;
        padding: 7px 15px; color: white; font-weight: 600;
        background: qlineargradient(x1:0,y1:0, x2:0,y2:1,
            stop:0 {theme.adjust(accent, 0.10)}, stop:1 {theme.adjust(accent, -0.08)});
    }}
    QPushButton[accent="true"]:hover {{
        background: qlineargradient(x1:0,y1:0, x2:0,y2:1,
            stop:0 {theme.adjust(accent, 0.14)}, stop:1 {theme.adjust(accent, -0.04)});
    }}
    QPushButton[accent="true"]:pressed {{ background: {theme.adjust(accent, -0.10)}; }}
    QPushButton[accent="true"]:disabled {{
        color: rgba(255,255,255,160); background: {_rgba(accent, 0.45)}; border: none;
    }}

    QCheckBox {{ spacing: 7px; }}
    QSplitter::handle {{ background: transparent; }}
    """


class MainWindow(QTabWidget):
    def __init__(self, store: store_mod.Store, ctrl, quit_app):
        super().__init__()
        self.store = store
        self.ctrl = ctrl
        self.quit_app = quit_app
        self.setWindowTitle("Socius Dictado")
        self.resize(760, 560)
        self.history = HistoryTab(store)
        self.files = FilesTab(store, ctrl)
        self.settings = SettingsTab(store, quit_app)
        self.addTab(self.history, "Historial")
        self.addTab(self.files, "Transcribir archivos")
        self.addTab(self.settings, "Ajustes")
        ctrl.history_changed.connect(self.history.refresh)
        ctrl.history_changed.connect(self.settings.refresh_usage)
        self.apply_theme()

    def apply_theme(self):
        import config
        accent = config.get("purple_hex") or theme.PURPLE
        self.setStyleSheet(_app_qss(accent))

    def show_window(self):
        if self.isMinimized():
            self.showNormal()
        self.show(); self.raise_(); self.activateWindow()
        _force_foreground(int(self.winId()))

    def show_settings(self):
        self.setCurrentWidget(self.settings)
        self.show_window()


# --------------------------------------------------------------------------- #
# Reusable editable transcript widget (used by Historial and the files result)
# --------------------------------------------------------------------------- #

class _EditPane(QTextEdit):
    """QTextEdit that reports when it loses focus (to snapshot a version)."""
    focus_lost = pyqtSignal()

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.focus_lost.emit()


class TranscriptEditor(QWidget):
    """Notepad-style editor for one transcript: edit in place (auto-saves),
    snapshots a version on blur / 'Guardar versión', and opens a version-history
    dialog. Everywhere a transcript is shown, it is shown through this."""
    deleted = pyqtSignal()

    def __init__(self, store: store_mod.Store, show_delete: bool = True):
        super().__init__()
        self.store = store
        self._id: str | None = None
        self._loading = False

        v = QVBoxLayout(self); v.setContentsMargins(0, 0, 0, 0)
        self.meta = QLabel(""); self.meta.setStyleSheet("color:#888; font-size:11px;")
        self.edit = _EditPane()
        self.edit.textChanged.connect(self._on_edit)
        self.edit.focus_lost.connect(self._snapshot)

        row = QHBoxLayout()
        self.copy_btn = QPushButton("Copiar"); self.copy_btn.clicked.connect(self._copy)
        self.copy_btn.setProperty("accent", "true")
        self.save_btn = QPushButton("Guardar versión"); self.save_btn.clicked.connect(self._snapshot)
        self.ver_btn = QPushButton("Versiones"); self.ver_btn.clicked.connect(self._versions)
        row.addWidget(self.copy_btn); row.addWidget(self.save_btn); row.addWidget(self.ver_btn)
        row.addStretch(1)
        if show_delete:
            self.del_btn = QPushButton("Borrar"); self.del_btn.clicked.connect(self._delete)
            row.addWidget(self.del_btn)

        v.addWidget(self.meta)
        v.addWidget(self.edit, 1)
        v.addLayout(row)

        self._timer = QTimer(self); self._timer.setSingleShot(True); self._timer.setInterval(350)
        self._timer.timeout.connect(self._persist)
        self.setEnabled(False)

    def _item(self, _id):
        return next((i for i in self.store.items if i.id == _id), None)

    def load(self, item_id: str):
        self._snapshot()                      # flush the previously loaded one
        it = self._item(item_id)
        self._loading = True
        self._id = item_id if it else None
        if it:
            self.meta.setText(f"{it.date_display()} · {it.duration_display()} · {it.words} palabras")
            self.edit.setPlainText(it.text)
            self.setEnabled(True)
        else:
            self.meta.setText(""); self.edit.clear(); self.setEnabled(False)
        self._loading = False

    def clear(self):
        self._snapshot()
        self._loading = True
        self._id = None
        self.edit.clear(); self.meta.setText(""); self.setEnabled(False)
        self._loading = False

    def _on_edit(self):
        if self._loading or not self._id:
            return
        self._timer.start()

    def _persist(self):
        if self._id:
            self.store.update_text(self._id, self.edit.toPlainText())

    def _snapshot(self):
        if self._id:
            self.store.update_text(self._id, self.edit.toPlainText())
            self.store.snapshot_version(self._id)

    def _copy(self):
        QApplication.clipboard().setText(self.edit.toPlainText())

    def _versions(self):
        if not self._id:
            return
        self._snapshot()
        dlg = VersionsDialog(self.store, self._id, self)
        if dlg.exec() and dlg.restored_text is not None:
            self._loading = True
            self.edit.setPlainText(dlg.restored_text)
            self._loading = False

    def _delete(self):
        if not self._id:
            return
        _id = self._id
        self._id = None
        self.store.delete(_id)
        self.clear()
        self.deleted.emit()


class VersionsDialog(QDialog):
    """Google-Docs-style version panel: snapshots newest-first, preview on the
    right, restore any older one."""
    def __init__(self, store: store_mod.Store, item_id: str, parent=None):
        super().__init__(parent)
        self.store = store
        self.item_id = item_id
        self.restored_text: str | None = None
        self.setWindowTitle("Historial de versiones")
        self.resize(700, 460)

        v = QVBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.currentItemChanged.connect(self._show)
        self.prev = QTextEdit(); self.prev.setReadOnly(True)
        split.addWidget(self.list); split.addWidget(self.prev); split.setSizes([250, 440])
        v.addWidget(split, 1)

        row = QHBoxLayout()
        self.restore_btn = QPushButton("Restaurar esta versión")
        self.restore_btn.setProperty("accent", "true")
        self.restore_btn.clicked.connect(self._restore)
        close = QPushButton("Cerrar"); close.clicked.connect(self.reject)
        row.addStretch(1); row.addWidget(self.restore_btn); row.addWidget(close)
        v.addLayout(row)

        self._versions = list(reversed(store.versions_of(item_id)))   # newest first
        for idx, ver in enumerate(self._versions):
            label = _fmt_iso(ver["date"]) + ("    ·  Actual" if idx == 0 else "")
            preview = (ver["text"][:70] or "(vacío)").replace("\n", " ")
            li = QListWidgetItem(f"{label}\n{preview}")
            li.setData(Qt.ItemDataRole.UserRole, idx)
            self.list.addItem(li)
        if self.list.count():
            self.list.setCurrentRow(0)

    def _current(self):
        li = self.list.currentItem()
        return self._versions[li.data(Qt.ItemDataRole.UserRole)] if li else None

    def _show(self, *_):
        ver = self._current()
        self.prev.setPlainText(ver["text"] if ver else "")
        self.restore_btn.setEnabled(self.list.currentRow() > 0)   # newest = current, nothing to restore

    def _restore(self):
        ver = self._current()
        if ver:
            self.store.restore(self.item_id, ver)
            self.restored_text = ver["text"]
            self.accept()


# --------------------------------------------------------------------------- #
# Historial
# --------------------------------------------------------------------------- #

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
        self.list.currentItemChanged.connect(self._select)
        self.editor = TranscriptEditor(store, show_delete=True)
        self.editor.deleted.connect(self.refresh)
        split.addWidget(self.list); split.addWidget(self.editor)
        split.setSizes([320, 440])
        root.addWidget(split, 1)

        self.refresh()

    def _filtered(self):
        q = self.search.text().strip().lower()
        return [i for i in self.store.items if not q or q in i.text.lower()]

    def refresh(self):
        self.list.blockSignals(True)
        self.list.clear()
        for it in self._filtered():
            li = QListWidgetItem(f"{it.title}\n{it.text[:60]}\n{it.date_display()} · "
                                 f"{it.duration_display()} · {it.words} palabras")
            li.setFlags(li.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            li.setCheckState(Qt.CheckState.Unchecked)
            li.setData(Qt.ItemDataRole.UserRole, it.id)
            self.list.addItem(li)
        self.list.blockSignals(False)
        if not self.store.items:
            self.editor.clear()

    def _select(self, cur, _prev=None):
        if cur:
            self.editor.load(cur.data(Qt.ItemDataRole.UserRole))

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
            self.store.delete_many(ids)
            self.refresh()

    def _clear(self):
        self.store.clear(); self.refresh(); self.editor.clear()

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


# --------------------------------------------------------------------------- #
# Transcribir archivos
# --------------------------------------------------------------------------- #

class _DropList(QListWidget):
    files_dropped = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        paths = [u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()]
        if paths:
            self.files_dropped.emit(paths)
        e.acceptProposedAction()


class FilesTab(QWidget):
    _progress = pyqtSignal(str)
    _done = pyqtSignal(str, float)
    _err = pyqtSignal(str)

    def __init__(self, store: store_mod.Store, ctrl):
        super().__init__()
        self.store = store
        self.ctrl = ctrl
        self.queue: list[str] = []
        self.saved_id: str | None = None
        self._running = False

        root = QVBoxLayout(self)

        hint = QLabel("Arrastra aquí tus audios (uno o varios). Se transcriben en el "
                      "orden que los sueltes y se unen en una sola transcripción.")
        hint.setWordWrap(True); hint.setStyleSheet("color:#888;")
        root.addWidget(hint)

        self.droplist = _DropList()
        self.droplist.files_dropped.connect(self._add_paths)
        self.droplist.setFixedHeight(150)
        root.addWidget(self.droplist)

        tools = QHBoxLayout()
        self.pick_btn = QPushButton("Elegir archivos…"); self.pick_btn.clicked.connect(self._pick)
        self.up_btn = QPushButton("↑"); self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = QPushButton("↓"); self.down_btn.clicked.connect(lambda: self._move(1))
        self.rm_btn = QPushButton("Quitar"); self.rm_btn.clicked.connect(self._remove_sel)
        for w in (self.pick_btn, self.up_btn, self.down_btn, self.rm_btn):
            tools.addWidget(w)
        tools.addStretch(1)
        self.transcribe_btn = QPushButton("Transcribir"); self.transcribe_btn.clicked.connect(self._run)
        self.transcribe_btn.setProperty("accent", "true")
        self.transcribe_btn.setEnabled(False)
        self.clear_btn = QPushButton("Limpiar"); self.clear_btn.clicked.connect(self._clear)
        tools.addWidget(self.transcribe_btn); tools.addWidget(self.clear_btn)
        root.addLayout(tools)

        self.progress = QLabel(""); self.progress.setStyleSheet("color:#888;")
        self.err_label = QLabel(""); self.err_label.setStyleSheet("color:#c0392b;")
        root.addWidget(self.progress); root.addWidget(self.err_label)

        self.result_label = QLabel("")
        self.result_label.setStyleSheet("color:#888; font-size:11px;")
        root.addWidget(self.result_label)
        self.result_editor = TranscriptEditor(store, show_delete=False)
        root.addWidget(self.result_editor, 1)

        self._progress.connect(self.progress.setText)
        self._done.connect(self._on_done)
        self._err.connect(self._on_err)

    # ---- queue ----
    def _add_paths(self, paths):
        for p in paths:
            ext = os.path.splitext(p)[1].lower().lstrip(".")
            if p and p not in self.queue and ext in AUDIO_EXTS:
                self.queue.append(p)
        self._render()

    def _render(self):
        self.droplist.clear()
        for i, p in enumerate(self.queue):
            self.droplist.addItem(f"{i + 1}.   {os.path.basename(p)}")
        self.transcribe_btn.setEnabled(bool(self.queue) and not self._running)

    def _move(self, delta):
        r = self.droplist.currentRow()
        nr = r + delta
        if r >= 0 and 0 <= nr < len(self.queue):
            self.queue[r], self.queue[nr] = self.queue[nr], self.queue[r]
            self._render(); self.droplist.setCurrentRow(nr)

    def _remove_sel(self):
        r = self.droplist.currentRow()
        if 0 <= r < len(self.queue):
            del self.queue[r]; self._render()

    def _clear(self):
        self.queue = []; self.saved_id = None
        self.err_label.setText(""); self.progress.setText(""); self.result_label.setText("")
        self.result_editor.clear()
        self._render()

    def _pick(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Elegir audios", "",
            "Audio (*.m4a *.mp3 *.wav *.mp4 *.mov *.ogg *.oga *.opus *.flac *.webm *.aiff *.aif *.amr *.3gp);;Todos (*.*)")
        if paths:
            self._add_paths(paths)

    # ---- run ----
    def _run(self):
        if self._running or not self.queue:
            return
        if not config.has_api_key():
            self.err_label.setText("Falta la API key. Agrégala en la pestaña Ajustes.")
            return
        self.err_label.setText("")
        self._running = True
        self.transcribe_btn.setEnabled(False)
        q = list(self.queue)
        threading.Thread(target=self._work, args=(q,), daemon=True).start()

    def _work(self, q):
        import transcriber
        parts, total = [], 0.0
        try:
            for i, p in enumerate(q):
                self._progress.emit(f"Transcribiendo {i + 1} de {len(q)}: {os.path.basename(p)}")
                parts.append(transcriber.transcribe_path(p))
                total += transcriber.file_duration(p)
        except Exception as e:
            self._err.emit(f"Error: {e}")
            return
        combined = "\n\n".join(x for x in parts if x).strip()
        self._done.emit(combined, total)

    def _on_done(self, combined, total):
        self._running = False
        self.transcribe_btn.setEnabled(bool(self.queue))
        self.progress.setText("")
        if not combined:
            self.err_label.setText("No se obtuvo texto de los archivos.")
            return
        model = config.get("model") or "gpt-4o-mini-transcribe"
        _id = self.store.add(combined, total, model)
        self.saved_id = _id
        self.queue = []; self._render()
        self.result_label.setText("Resultado — ya está en el Historial. Edítalo aquí si quieres.")
        self.result_editor.load(_id)
        self.ctrl.history_changed.emit()
        threading.Thread(target=self._title_work, args=(_id, combined), daemon=True).start()

    def _title_work(self, _id, text):
        t = ai.make_title(text)
        if t:
            self.store.set_title(_id, t)
            self.ctrl.history_changed.emit()

    def _on_err(self, msg):
        self._running = False
        self.transcribe_btn.setEnabled(bool(self.queue))
        self.progress.setText("")
        self.err_label.setText(msg)


# --------------------------------------------------------------------------- #
# Ajustes
# --------------------------------------------------------------------------- #

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
        win = self.window()
        if hasattr(win, "apply_theme"):            # restyle the window with the new accent
            win.apply_theme()

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
