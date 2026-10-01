"""daari.main — FastAPI app with health probes and the P2 engine router.

Every probe is best-effort and never raises past its own function: a bad
network, a missing key or a down provider degrades that one field to
`{"status": "error", "detail": ...}` (or "skipped" for genuinely optional
providers) and the endpoint still answers 200. `detail` is always a short,
sanitized token — an exception class name or `http_<code>` — never
`str(exc)`, because several of these requests carry an API key in the URL
query string and httpx error messages can embed the full request URL.
"""

import asyncio
import subprocess
import time
from collections.abc import Coroutine
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import redis.asyncio as redis_async
from fastapi import FastAPI
from sqlalchemy import text

from daari.agent.loop import _TOOLS as TOOLS
from daari.config import settings
from daari.db import engine
from daari.evidence import evidence as evidence_endpoint
from daari.evidence import router as evidence_router
from daari.p2 import router as p2_router
from daari.p3 import router as p3_router
from daari.p4 import router as p4_router
from daari.p5 import router as p5_router
from daari.source_cache import source

_APP_DIR = Path(__file__).resolve().parent
_PROBE_TIMEOUT_S = 6.0

GEMINI_MODEL = "gemini-3.1-flash-lite"
GROQ_CHAT_MODEL = "openai/gpt-oss-120b"
GROQ_ASR_MODEL = "whisper-large-v3"
OLLAMA_MODEL = "llama3.1:8b"

_MYSCHEME_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
# Project-identifying UA for polite scraping — deliberately not a personal email address.
_CONTACT_UA = "daari-health/0.1 (SYNORA Track1 hackathon demo; https://github.com/dmrk22/asura)"


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_APP_DIR,
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


# Captured once at import — never re-read per request.
_SHA = _git_sha()

app = FastAPI(title="daari-api")
app.include_router(p2_router)
app.include_router(p3_router)
app.include_router(p4_router)
app.include_router(p5_router)
app.include_router(evidence_router)


@app.get("/evidence", tags=["P6 evidence"])
async def public_evidence() -> dict:
    """Stable top-level alias for the evidence board and external checks."""
    return await evidence_endpoint()


async def _safe(coro: Coroutine[Any, Any, dict]) -> dict:
    """Run one probe under a hard timeout; never let it raise past this point."""
    try:
        return await asyncio.wait_for(coro, timeout=_PROBE_TIMEOUT_S)
    except TimeoutError:
        return {"status": "error", "detail": "timeout"}
    except Exception as exc:  # noqa: BLE001 — a probe may raise anything (httpx, redis,
        # sqlalchemy, edge_tts, ...); the contract of /health is that none of them may
        # turn into a 500, so this catch is deliberately unbounded.
        return {"status": "error", "detail": type(exc).__name__}


# --- individual probes ------------------------------------------------------
# Each returns the smallest honest shape; main() decorates llm entries with
# provider/model afterwards so a raised exception still produces a complete entry.


async def _probe_db() -> dict:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
        row = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'vector'"))
        has_vector = row.first() is not None
    return {"status": "ok", "detail": "vector_ext_present" if has_vector else "vector_ext_missing"}


async def _probe_redis() -> dict:
    client = redis_async.from_url(settings.REDIS_URL)
    try:
        pong = await client.ping()
    finally:
        await client.aclose()
    return {"status": "ok" if pong else "error", "detail": "pong" if pong else "no_pong"}


async def _probe_gemini(client: httpx.AsyncClient) -> dict:
    if not settings.GEMINI_API_KEY:
        return {"status": "skipped", "detail": "no_api_key"}
    resp = await client.get(
        "https://generativelanguage.googleapis.com/v1beta/models",
        params={"key": settings.GEMINI_API_KEY},
    )
    if resp.status_code == 200:
        return {"status": "ok", "detail": "reachable"}
    return {"status": "error", "detail": f"http_{resp.status_code}"}


async def _probe_groq_models(client: httpx.AsyncClient) -> dict:
    """Backs both the `groq` llm entry and the `asr` entry — one call, reused."""
    if not settings.GROQ_API_KEY:
        return {"status": "skipped", "detail": "no_api_key"}
    resp = await client.get(
        "https://api.groq.com/openai/v1/models",
        headers={
            "Authorization": f"Bearer {settings.GROQ_API_KEY}",
            # Groq answers 403 without a User-Agent.
            "User-Agent": _CONTACT_UA,
        },
    )
    if resp.status_code == 200:
        return {"status": "ok", "detail": "reachable"}
    return {"status": "error", "detail": f"http_{resp.status_code}"}


async def _probe_ollama(client: httpx.AsyncClient) -> dict:
    """Optional: unreachable is `skipped`, not `error`.

    A reachable daemon is not a usable provider. Ollama here has no models pulled,
    so `/api/tags` returns 200 with an empty list — reporting that as `ok` would
    promise the chain a third link that fails on the first call.
    """
    try:
        resp = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
    except httpx.RequestError:
        return {"status": "skipped", "detail": "unreachable"}
    if resp.status_code != 200:
        return {"status": "skipped", "detail": f"http_{resp.status_code}"}
    try:
        tags = resp.json().get("models") or []
    except ValueError:
        return {"status": "skipped", "detail": "unparseable_tags"}
    # Ollama reports "llama3.1:8b"; a bare "llama3.1" pull answers as "llama3.1:latest".
    wanted = OLLAMA_MODEL.split(":")[0]
    if any(str(t.get("name", "")).split(":")[0] == wanted for t in tags):
        return {"status": "ok", "detail": "model_present"}
    return {"status": "skipped", "detail": "model_not_pulled"}


async def _probe_tts() -> dict:
    try:
        import edge_tts
    except ImportError as exc:
        return {"status": "error", "detail": f"import_{type(exc).__name__}"}

    voices = await edge_tts.list_voices()
    names = {v["ShortName"] for v in voices}
    wanted = {settings.TTS_VOICE_TE, settings.TTS_VOICE_HI, settings.TTS_VOICE_EN}
    missing = wanted - names
    if missing:
        return {"status": "error", "detail": f"missing_{len(missing)}_voices"}
    return {"status": "ok", "detail": "voices_present"}


async def _probe_adzuna(client: httpx.AsyncClient) -> dict:
    if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
        return {"status": "skipped", "detail": "no_api_key"}
    resp = await client.get(
        "https://api.adzuna.com/v1/api/jobs/in/search/1",
        params={
            "app_id": settings.ADZUNA_APP_ID,
            "app_key": settings.ADZUNA_APP_KEY,
            "results_per_page": 1,
        },
    )
    if resp.status_code == 200:
        return {"status": "ok", "detail": "reachable"}
    return {"status": "error", "detail": f"http_{resp.status_code}"}


async def _probe_nominatim(client: httpx.AsyncClient) -> dict:
    resp = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": "Guntur, Andhra Pradesh", "format": "jsonv2", "limit": 1},
        headers={"User-Agent": _CONTACT_UA},
    )
    if resp.status_code == 200:
        return {"status": "ok", "detail": "reachable"}
    return {"status": "error", "detail": f"http_{resp.status_code}"}


async def _probe_myscheme(client: httpx.AsyncClient) -> dict:
    resp = await client.get(
        "https://api.myscheme.gov.in/search/v6/schemes",
        params={"lang": "en", "q": "[]", "keyword": "income", "sort": "", "from": 0, "size": 1},
        headers={
            "x-api-key": source("myscheme_ap")["public_api_key"],
            "User-Agent": _MYSCHEME_UA,
            "Referer": "https://www.myscheme.gov.in/",
        },
    )
    if resp.status_code == 200:
        return {"status": "ok", "detail": "reachable"}
    return {"status": "error", "detail": f"http_{resp.status_code}"}


async def _probe_serpapi(client: httpx.AsyncClient) -> dict:
    if not settings.SERPAPI_KEY:
        return {"status": "skipped", "value": None}
    resp = await client.get("https://serpapi.com/account", params={"api_key": settings.SERPAPI_KEY})
    if resp.status_code == 200:
        return {"status": "ok", "value": resp.json().get("total_searches_left")}
    return {"status": "error", "value": None}


@app.get("/health")
async def health() -> dict:
    # One clock per measurement: checked_at is a single wall-clock read, stamped once and
    # carried; ms is the elapsed duration between two monotonic reads of the SAME clock
    # around the SAME block of work — not two different reads mislabeled as one instant.
    t0 = time.monotonic()
    checked_at = datetime.now(UTC)

    async with httpx.AsyncClient(timeout=_PROBE_TIMEOUT_S) as client:
        (
            db_result,
            redis_result,
            gemini_probe,
            groq_probe,
            ollama_probe,
            tts_result,
            adzuna_result,
            nominatim_result,
            myscheme_result,
            serpapi_probe,
        ) = await asyncio.gather(
            _safe(_probe_db()),
            _safe(_probe_redis()),
            _safe(_probe_gemini(client)),
            _safe(_probe_groq_models(client)),
            _safe(_probe_ollama(client)),
            _safe(_probe_tts()),
            _safe(_probe_adzuna(client)),
            _safe(_probe_nominatim(client)),
            _safe(_probe_myscheme(client)),
            _safe(_probe_serpapi(client)),
        )

    gemini_result = {"provider": "gemini", "model": GEMINI_MODEL, **gemini_probe}
    groq_result = {"provider": "groq", "model": GROQ_CHAT_MODEL, **groq_probe}
    ollama_result = {"provider": "ollama", "model": OLLAMA_MODEL, **ollama_probe}
    llm = [gemini_result, groq_result, ollama_result]

    # asr reuses the groq probe outcome — no second network call.
    asr_result = {
        "provider": "groq",
        "model": GROQ_ASR_MODEL,
        "status": groq_probe["status"],
        "detail": groq_probe.get("detail", ""),
    }

    serpapi_result = {"value": None, **serpapi_probe}

    ok = (
        db_result.get("status") == "ok"
        and redis_result.get("status") == "ok"
        and tts_result.get("status") == "ok"
        and any(entry.get("status") == "ok" for entry in llm)
    )

    ms = round((time.monotonic() - t0) * 1000)

    return {
        "sha": _SHA,
        "db": db_result,
        "redis": redis_result,
        "llm": llm,
        "tools": {"status": "ok", "count": len(TOOLS)},
        "asr": asr_result,
        "tts": tts_result,
        "adzuna": adzuna_result,
        "myscheme": myscheme_result,
        "nominatim": nominatim_result,
        "serpapi_budget_left": serpapi_result,
        "ok": ok,
        "checked_at": checked_at.isoformat(),
        "ms": ms,
    }
