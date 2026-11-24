"""Microphone recording to a mono 16kHz WAV via sounddevice. No time limit.

Keeps frames in memory and reports a 0..1 level for the orb animation.
"""
from __future__ import annotations
import time
import wave

import numpy as np
import sounddevice as sd

import paths

SAMPLE_RATE = 16000
CHANNELS = 1


class Recorder:
    def __init__(self, on_level=None):
        self.on_level = on_level           # callback(float 0..1)
        self._stream = None
        self._frames: list[np.ndarray] = []
        self._recording = False

    @property
    def is_recording(self) -> bool:
        return self._recording

    def _callback(self, indata, frames, time_info, status):
        self._frames.append(indata.copy())
        if self.on_level is not None:
            rms = float(np.sqrt(np.mean(np.square(indata.astype(np.float32) / 32768.0))))
            # gentle curve, clamp
            lvl = max(0.0, min(1.0, rms * 8.0))
            self.on_level(lvl)

    def start(self) -> None:
        self._frames = []
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
            callback=self._callback,
        )
        self._stream.start()
        self._recording = True

    def stop(self) -> str | None:
        """Stop and write a WAV; return its path (or None if nothing recorded)."""
        if not self._recording:
            return None
        self._recording = False
        try:
            self._stream.stop()
            self._stream.close()
        except Exception:
            pass
        self._stream = None
        if not self._frames:
            return None
        data = np.concatenate(self._frames, axis=0)
        out = paths.temp_dir() / f"rec-{int(time.time())}.wav"
        with wave.open(str(out), "wb") as w:
            w.setnchannels(CHANNELS)
            w.setsampwidth(2)            # int16
            w.setframerate(SAMPLE_RATE)
            w.writeframes(data.tobytes())
        return str(out)

    def cancel(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
        self._stream = None
        self._frames = []
        self._recording = False
