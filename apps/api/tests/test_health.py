"""GET /health — every required key present, `ok` is a bool, 200 even when
every outbound probe raises, and Settings never leaks a secret through
repr/str.
"""

from typing import cast

import httpx
import pytest
from fastapi.testclient import TestClient

import daari.main as main_module
from daari.config import Settings

client = TestClient(main_module.app)

EXPECTED_KEYS = {
    "sha",
    "db",
    "redis",
    "llm",
    "tools",
    "asr",
    "tts",
    "adzuna",
    "myscheme",
    "nominatim",
    "serpapi_budget_left",
    "ok",
    "checked_at",
    "ms",
}

_PROBE_NAMES = [
    "_probe_db",
    "_probe_redis",
    "_probe_gemini",
    "_probe_groq_models",
    "_probe_ollama",
    "_probe_tts",
    "_probe_adzuna",
    "_probe_nominatim",
    "_probe_myscheme",
    "_probe_serpapi",
]


async def _raise(*_args, **_kwargs):
    raise RuntimeError("simulated probe failure")


def test_health_has_every_required_key_and_sane_types():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()

    assert EXPECTED_KEYS <= set(body.keys())
    assert isinstance(body["ok"], bool)
    assert isinstance(body["ms"], int)
    assert body["ms"] >= 0
    assert isinstance(body["checked_at"], str)
    assert isinstance(body["llm"], list)
    assert len(body["llm"]) == 3
    for entry in body["llm"]:
        assert {"provider", "model", "status", "detail"} <= set(entry.keys())
    assert body["tools"] == {"status": "ok", "count": 10}


def test_health_returns_200_with_error_statuses_when_every_probe_raises(monkeypatch):
    for name in _PROBE_NAMES:
        monkeypatch.setattr(main_module, name, _raise)

    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()

    assert body["ok"] is False
    assert body["db"]["status"] == "error"
    assert body["redis"]["status"] == "error"
    assert body["tts"]["status"] == "error"
    assert body["adzuna"]["status"] == "error"
    assert body["nominatim"]["status"] == "error"
    assert body["myscheme"]["status"] == "error"
    assert body["asr"]["status"] == "error"
    assert body["serpapi_budget_left"]["status"] == "error"
    for entry in body["llm"]:
        assert entry["status"] == "error"
        assert entry["provider"] and entry["model"]  # still a complete entry, not dropped


def test_settings_repr_and_str_never_leak_a_secret():
    secret = "sk-super-secret-value-zzz"
    s = Settings(GEMINI_API_KEY=secret, GROQ_API_KEY=secret)
    assert secret not in repr(s)
    assert secret not in str(s)


# --- regression: a reachable Ollama daemon with no model pulled is NOT a usable provider ---


class _FakeTagsResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, response) -> None:
        self._response = response

    async def get(self, *_args, **_kwargs):
        return self._response


@pytest.mark.asyncio
async def test_ollama_with_no_model_pulled_is_skipped_not_ok():
    """The daemon answers 200 with an empty list when nothing is pulled.

    Reporting `ok` there promises the provider chain a third link that fails on
    its first real call.
    """
    probe = await main_module._probe_ollama(
        cast(httpx.AsyncClient, _FakeClient(_FakeTagsResponse({"models": []})))
    )
    assert probe["status"] == "skipped"
    assert probe["detail"] == "model_not_pulled"


@pytest.mark.asyncio
async def test_ollama_with_the_configured_model_pulled_is_ok():
    payload = {"models": [{"name": f"{main_module.OLLAMA_MODEL}"}]}
    probe = await main_module._probe_ollama(
        cast(httpx.AsyncClient, _FakeClient(_FakeTagsResponse(payload)))
    )
    assert probe["status"] == "ok"
    assert probe["detail"] == "model_present"


@pytest.mark.asyncio
async def test_ollama_accepts_a_bare_tag_pull_of_the_same_model():
    """`ollama pull llama3.1` lands as `llama3.1:latest` — still the usable model."""
    payload = {"models": [{"name": "llama3.1:latest"}]}
    probe = await main_module._probe_ollama(
        cast(httpx.AsyncClient, _FakeClient(_FakeTagsResponse(payload)))
    )
    assert probe["status"] == "ok"
