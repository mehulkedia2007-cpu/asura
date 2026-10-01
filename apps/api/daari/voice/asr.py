"""Groq Whisper final transcript with an explicit browser-final fallback."""

import hashlib
import json
from pathlib import Path

import httpx

from daari.config import REPO_ROOT, settings
from daari.voice.lang import Locale


def _cache_path(audio: bytes) -> Path:
    digest = hashlib.sha256(audio).hexdigest()
    return REPO_ROOT / ".cache/voice/asr" / f"{digest}.json"


def register_rehearsal(audio: bytes, transcript: str, locale: Locale) -> None:
    """Opt in a reviewed clip for offline replay; never cache arbitrary speech."""
    if not audio or not transcript.strip():
        raise ValueError("audio and reviewed transcript are required")
    path = _cache_path(audio)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"locale": locale, "text": transcript.strip()}, ensure_ascii=False))
    temporary.replace(path)


async def transcribe(
    audio: bytes,
    mime: str,
    locale: Locale,
    browser_final: str = "",
    *,
    allow_rehearsal_cache: bool = True,
) -> tuple[str, str]:
    if audio and allow_rehearsal_cache:
        try:
            cached = json.loads(_cache_path(audio).read_text())
            if cached.get("locale") == locale and isinstance(cached.get("text"), str) and cached["text"].strip():
                return cached["text"].strip(), "rehearsal_cache"
        except (OSError, ValueError, TypeError):
            pass
    if not audio or not settings.GROQ_API_KEY:
        return browser_final.strip(), "browser" if browser_final.strip() else "unavailable"
    extension = "webm" if "webm" in mime else "mp4" if "mp4" in mime else "mp3" if "mpeg" in mime else "wav"
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}",
                         "User-Agent": "DAARI/0.1 (https://github.com/dmrk22/asura)"},
                data={"model": "whisper-large-v3", "response_format": "json",
                      **({"language": locale} if locale != "en" else {})},
                files={"file": (f"speech.{extension}", audio, mime)},
            )
            response.raise_for_status()
            transcript = str(response.json().get("text") or "").strip()
            if transcript:
                return transcript, "groq"
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    return browser_final.strip(), "browser" if browser_final.strip() else "unavailable"
