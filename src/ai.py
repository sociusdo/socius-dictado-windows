"""Optional LLM post-processing: AI modes (clean/bullets/email/translate) and the
short AI title for the history — via chat completions (gpt-4o-mini)."""
from __future__ import annotations
import requests

import config

ENDPOINT = "https://api.openai.com/v1/chat/completions"

MODE_PROMPTS = {
    "none": None,
    "clean": "Eres un editor. Corrige puntuación, mayúsculas y errores obvios del dictado, sin cambiar el significado ni el idioma. Devuelve SOLO el texto corregido, sin comillas ni comentarios.",
    "bullets": "Convierte el dictado en una lista de bullets claros y concisos, conservando el idioma. Devuelve SOLO los bullets (uno por línea con '- '), sin encabezados.",
    "email": "Reescribe el dictado como un correo profesional y cordial en el mismo idioma. Mantén el fondo. Devuelve SOLO el cuerpo del correo, sin asunto ni firma.",
    "translate_en": "Translate the dictation into natural English. Return ONLY the translation, no quotes or notes.",
}

MODE_TITLES = {
    "none": "Ninguno (texto tal cual)",
    "clean": "Limpiar y puntuar",
    "bullets": "Convertir en bullets",
    "email": "Redactar como correo",
    "translate_en": "Traducir a inglés",
}


def _chat(system: str, user: str, max_tokens: int | None = None) -> str | None:
    key = config.get_api_key()
    if not key or not user.strip():
        return None
    payload = {
        "model": "gpt-4o-mini",
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens
    try:
        resp = requests.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=60,
        )
        if not (200 <= resp.status_code < 300):
            return None
        out = resp.json()["choices"][0]["message"]["content"].strip()
        return out or None
    except Exception:
        return None


def apply_mode(mode: str, text: str) -> str:
    """Return transformed text, or the original on any failure/none."""
    system = MODE_PROMPTS.get(mode)
    if not system or not text.strip():
        return text
    return _chat(system, text) or text


def make_title(text: str) -> str | None:
    system = ("Genera un título muy corto (3 a 6 palabras) que resuma de qué trata el texto, "
              "en su mismo idioma. Sin comillas, sin punto final, sin prefijos como 'Título:'. "
              "Devuelve SOLO el título.")
    out = _chat(system, text, max_tokens=24)
    if not out:
        return None
    out = out.strip().strip('"\'.“”')
    return out[:60] if out else None
