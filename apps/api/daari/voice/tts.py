"""Sentence audio from Edge; caller can fall back to browser synthesis."""

import asyncio
import hashlib
from pathlib import Path

import edge_tts

from daari.config import REPO_ROOT, settings
from daari.voice.lang import Locale


def _cache_path(sentence: str, locale: Locale, voice: str) -> Path:
    digest = hashlib.sha256(f"{locale}\n{voice}\n{sentence}".encode()).hexdigest()
    return REPO_ROOT / ".cache/voice/tts" / f"{digest}.mp3"


async def synthesize(sentence: str, locale: Locale, *, use_cache: bool = True) -> bytes | None:
    voice = {"en": settings.TTS_VOICE_EN, "te": settings.TTS_VOICE_TE,
             "hi": settings.TTS_VOICE_HI}[locale]
    path = _cache_path(sentence, locale, voice)
    if use_cache:
        try:
            cached = path.read_bytes()
            if cached:
                return cached
        except OSError:
            pass
    try:
        chunks = []
        async with asyncio.timeout(12):
            async for chunk in edge_tts.Communicate(sentence, voice).stream():
                data = chunk.get("data")
                if chunk["type"] == "audio" and isinstance(data, bytes):
                    chunks.append(data)
        audio = b"".join(chunks) or None
        if audio and use_cache:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".tmp")
                temporary.write_bytes(audio)
                temporary.replace(path)
            except OSError:
                pass
        return audio
    except Exception:  # noqa: BLE001 — any provider failure must permit browser TTS.
        return None
