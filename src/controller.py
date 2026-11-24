"""Dictation state machine. Record -> transcribe -> (AI mode) -> paste at cursor.

Background work runs on threads; UI updates are delivered through Qt signals so
the orb/window always update on the main thread.
"""
from __future__ import annotations
import logging
import threading
import time

log = logging.getLogger("controller")

from PyQt6.QtCore import QObject, pyqtSignal

import ai
import config
import paster
import store as store_mod
from recorder import Recorder
from transcriber import transcribe, TranscribeError

# States
IDLE = "idle"
RECORDING = "recording"
TRANSCRIBING = "transcribing"
DONE = "done"            # pasted -> green
COPIED_ONLY = "copied"   # amber
ERROR = "error"
NEEDS_KEY = "needs_key"


class Controller(QObject):
    state_changed = pyqtSignal(str)
    level_changed = pyqtSignal(float)
    history_changed = pyqtSignal()
    # emitted from the hotkey thread; connected queued -> runs on main thread
    trigger_primary = pyqtSignal()
    trigger_toggle_window = pyqtSignal()
    need_key_signal = pyqtSignal()

    def __init__(self, store: store_mod.Store) -> None:
        super().__init__()
        self.store = store
        self._state = IDLE
        self.last_transcript = ""
        self._last_wav: str | None = None
        self._last_duration = 0.0
        self._recording_started = 0.0
        self._cancelled = False
        self.open_window = None   # set by main: callable to open the window
        self.recorder = Recorder(on_level=lambda lv: self.level_changed.emit(lv))
        self.trigger_primary.connect(self.primary_tap)

    @property
    def state(self) -> str:
        return self._state

    def _set_state(self, s: str) -> None:
        self._state = s
        self.state_changed.emit(s)

    # ---- primary action (orb click / dictate hotkey) ----
    def primary_tap(self) -> None:
        if self._state in (IDLE, DONE, COPIED_ONLY, ERROR):
            self._begin()
        elif self._state == RECORDING:
            self._finish_and_transcribe()
        # transcribing / needs_key: ignore

    def _begin(self) -> None:
        if not config.has_api_key():
            self._set_state(NEEDS_KEY)
            self.need_key_signal.emit()
            return
        try:
            self.recorder.start()
            self._recording_started = time.time()
            self._cancelled = False
            self._beep(880)
            self._set_state(RECORDING)
        except Exception as e:
            log.exception("recorder start failed")
            self.last_error = str(e)
            self._set_state(ERROR)

    def _finish_and_transcribe(self) -> None:
        wav = self.recorder.stop()
        self._last_duration = time.time() - self._recording_started
        log.info("recording stopped: %.1fs wav=%s", self._last_duration, wav)
        self._beep(660)
        if not wav:
            self._set_state(IDLE)
            return
        self._last_wav = wav
        self._run_transcription(wav, save=True)

    def _run_transcription(self, wav: str, save: bool) -> None:
        self._set_state(TRANSCRIBING)
        self._cancelled = False
        threading.Thread(target=self._worker, args=(wav, save), daemon=True).start()

    def _worker(self, wav: str, save: bool) -> None:
        try:
            raw = transcribe(wav)
            if self._cancelled:
                return
            mode = config.get("ai_mode") or "none"
            text = ai.apply_mode(mode, raw)
            if self._cancelled:
                return
            self.last_transcript = text
            if save:
                item_id = self.store.add(text, self._last_duration, config.get("model"))
                self.history_changed.emit()
                threading.Thread(target=self._title_worker, args=(item_id, text), daemon=True).start()
            self._deliver(text)
        except TranscribeError as e:
            log.error("transcribe failed: %s", e)
            if not self._cancelled:
                self.last_error = str(e)
                self._set_state(ERROR)
                self._flash_back()
        except Exception as e:
            log.exception("worker failed")
            if not self._cancelled:
                self.last_error = str(e)
                self._set_state(ERROR)
                self._flash_back()

    def _title_worker(self, item_id: str, text: str) -> None:
        t = ai.make_title(text)
        if t:
            self.store.set_title(item_id, t)
            self.history_changed.emit()

    def _deliver(self, text: str) -> None:
        ok = paster.paste_at_cursor(text)   # Windows: no permission needed
        log.info("delivered %d chars, pasted=%s", len(text), ok)
        self._set_state(DONE if ok else COPIED_ONLY)
        self._flash_back()

    def _flash_back(self) -> None:
        def go():
            time.sleep(1.0)
            if self._state in (DONE, COPIED_ONLY, ERROR):
                self._set_state(IDLE)
        threading.Thread(target=go, daemon=True).start()

    # ---- menu actions ----
    def menu_action(self) -> None:
        if self._state in (RECORDING, TRANSCRIBING):
            self.cancel()
        elif self.open_window:
            self.open_window()

    def cancel(self) -> None:
        self._cancelled = True
        if self.recorder.is_recording:
            self.recorder.cancel()
        self._set_state(IDLE)

    def retry(self) -> None:
        if self._last_wav:
            self._run_transcription(self._last_wav, save=False)

    # ---- helpers ----
    def _beep(self, freq: int) -> None:
        if not config.get("sound"):
            return
        def go():
            try:
                import winsound
                winsound.Beep(freq, 90)
            except Exception:
                pass
        threading.Thread(target=go, daemon=True).start()
