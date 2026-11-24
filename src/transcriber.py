"""OpenAI audio transcription via the REST API (requests), with chunking for
long recordings and retry/backoff — mirrors the macOS app.

Input is a mono 16kHz WAV file written by recorder.py.
"""
from __future__ import annotations
import io
import os
import time
import wave
from concurrent.futures import ThreadPoolExecutor

import requests

import config
import paths

CHUNK_SECONDS = 480        # 8 min per chunk
CHUNK_THRESHOLD = 600      # only split if longer than 10 min
MAX_CONCURRENT = 4
ENDPOINT = "https://api.openai.com/v1/audio/transcriptions"


class TranscribeError(Exception):
    pass


def _dictionary_prompt() -> str | None:
    raw = config.get("dictionary") or ""
    terms = [t.strip() for t in raw.replace(",", "\n").splitlines() if t.strip()]
    if not terms:
        return None
    return "Términos y nombres propios: " + ", ".join(terms)


_MIME = {
    ".mp3": "audio/mpeg", ".mpga": "audio/mpeg", ".mpeg": "audio/mpeg", ".mpg": "audio/mpeg",
    ".wav": "audio/wav", ".flac": "audio/flac", ".ogg": "audio/ogg", ".oga": "audio/ogg",
    ".opus": "audio/ogg", ".webm": "audio/webm", ".mov": "video/quicktime",
    ".m4a": "audio/mp4", ".m4b": "audio/mp4", ".mp4": "audio/mp4",
    ".aiff": "audio/aiff", ".aif": "audio/aiff", ".caf": "audio/aiff",
    ".amr": "audio/amr", ".3gp": "audio/3gpp",
}


def _mime_for(path: str) -> str:
    return _MIME.get(os.path.splitext(path)[1].lower(), "audio/m4a")


def _post_once(wav_path: str, key: str, model: str, mime: str | None = None) -> str:
    if mime is None:
        mime = _mime_for(wav_path)
    data = {"model": model, "response_format": "text"}
    prompt = _dictionary_prompt()
    if prompt:
        data["prompt"] = prompt
    lang = config.get("language")
    if lang in ("es", "en"):
        data["language"] = lang

    # WhatsApp voice notes are Ogg/Opus saved as ".opus", which OpenAI rejects by
    # extension. The bytes are a valid Ogg, so upload them under an ".ogg" name.
    upload_name = os.path.basename(wav_path)
    if os.path.splitext(upload_name)[1].lower() == ".opus":
        upload_name = os.path.splitext(upload_name)[0] + ".ogg"

    for attempt in range(6):
        try:
            with open(wav_path, "rb") as fh:
                files = {"file": (upload_name, fh, mime)}
                resp = requests.post(
                    ENDPOINT,
                    headers={"Authorization": f"Bearer {key}"},
                    data=data, files=files, timeout=300,
                )
            if resp.status_code in (429,) or resp.status_code >= 500:
                time.sleep(min(20.0, 2 ** attempt + 0.25))
                continue
            if not (200 <= resp.status_code < 300):
                raise TranscribeError(f"OpenAI {resp.status_code}: {resp.text[:300]}")
            text = resp.text.strip()
            if not text:
                raise TranscribeError("Transcripción vacía")
            return text
        except requests.RequestException:
            time.sleep(min(20.0, 2 ** attempt + 0.25))
    raise TranscribeError("No se pudo transcribir tras varios intentos")


def _read_wav(path: str):
    with wave.open(path, "rb") as w:
        n = w.getnframes()
        fr = w.getframerate()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        frames = w.readframes(n)
    return frames, fr, ch, sw


def _write_wav_bytes(frames: bytes, fr: int, ch: int, sw: int) -> str:
    out = paths.temp_dir() / f"chunk-{int(time.time()*1000)}-{os.getpid()}-{len(frames)}.wav"
    with wave.open(str(out), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(sw)
        w.setframerate(fr)
        w.writeframes(frames)
    return str(out)


def transcribe(wav_path: str) -> str:
    key = config.get_api_key()
    if not key:
        raise TranscribeError("No hay API key de OpenAI")
    model = config.get("model") or "gpt-4o-mini-transcribe"

    frames, fr, ch, sw = _read_wav(wav_path)
    duration = len(frames) / (fr * ch * sw) if fr and ch and sw else 0

    if duration <= CHUNK_THRESHOLD:
        return _post_once(wav_path, key, model)

    # Split into time chunks, transcribe in parallel, keep order.
    bytes_per_sec = fr * ch * sw
    step = CHUNK_SECONDS * bytes_per_sec
    pieces = [frames[i:i + step] for i in range(0, len(frames), step)]
    chunk_paths = [_write_wav_bytes(p, fr, ch, sw) for p in pieces]
    try:
        results: list[str] = [""] * len(chunk_paths)
        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as ex:
            futs = {ex.submit(_post_once, cp, key, model): idx for idx, cp in enumerate(chunk_paths)}
            for fut in futs:
                idx = futs[fut]
                results[idx] = fut.result()
        return "\n\n".join(r for r in results if r).strip()
    finally:
        for cp in chunk_paths:
            try:
                os.remove(cp)
            except OSError:
                pass


def transcribe_path(path: str) -> str:
    """Transcribe any audio file (drag-and-drop). WAV goes through the chunking
    path; other formats are posted directly to OpenAI (<=25MB)."""
    key = config.get_api_key()
    if not key:
        raise TranscribeError("No hay API key de OpenAI")
    model = config.get("model") or "gpt-4o-mini-transcribe"
    if os.path.splitext(path)[1].lower() == ".wav":
        return transcribe(path)
    return _post_once(path, key, model)


def file_duration(path: str) -> float:
    """Seconds of audio, best-effort (exact for WAV, 0 otherwise)."""
    try:
        if os.path.splitext(path)[1].lower() == ".wav":
            with wave.open(path, "rb") as w:
                return w.getnframes() / float(w.getframerate())
    except Exception:
        pass
    return 0.0
