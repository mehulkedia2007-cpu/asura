"""Cloud connection, filesystem, readiness and browser-origin regressions."""

import ssl
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import make_url
from starlette.websockets import WebSocketDisconnect

from daari import main
from daari.config import Settings, cache_root, settings
from daari.db import _connect_args, _to_asyncpg_url


@pytest.mark.parametrize("scheme", ["postgres", "postgresql", "postgresql+asyncpg"])
def test_cloud_url_preserves_encoded_password_and_verifies_tls(scheme):
    url = f"{scheme}://user:p%40ss@cloud.example/db?sslmode=require&channel_binding=require"
    parsed = make_url(_to_asyncpg_url(url))
    assert parsed.drivername == "postgresql+asyncpg"
    assert parsed.password == "p@ss"
    assert parsed.query == {"ssl": "verify-full"}
    tls = _connect_args(url)["ssl"]
    assert tls.check_hostname and tls.verify_mode == ssl.CERT_REQUIRED


def test_neon_direct_url_takes_precedence():
    config = Settings(DATABASE_URL="postgresql://pooled/db", DATABASE_URL_UNPOOLED="postgresql://direct/db")
    assert config.database_url == "postgresql://direct/db"


def test_upstash_integration_url_alias_is_supported():
    config = Settings.model_validate({"KV_URL": "rediss://default:synthetic@cache.example:6379"})
    assert config.REDIS_URL == "rediss://default:synthetic@cache.example:6379"


def test_cache_uses_tmp_on_vercel_but_keeps_local_rehearsal(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "CACHE_ROOT", None)
    monkeypatch.setattr(settings, "VERCEL", False)
    assert cache_root(tmp_path) == tmp_path / ".cache"
    monkeypatch.setattr(settings, "VERCEL", True)
    assert cache_root(tmp_path) == Path("/tmp/daari-cache")


def test_readiness_fails_closed_without_leaking_driver_error(monkeypatch):
    async def broken():
        raise RuntimeError("credential-that-must-not-leak")

    monkeypatch.setattr(main, "_probe_schema", broken)
    monkeypatch.setattr(main, "_probe_redis", broken)
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 503
    assert response.json()["ok"] is False
    assert "credential-that-must-not-leak" not in response.text


def test_readiness_succeeds_with_schema_and_cache(monkeypatch):
    async def healthy():
        return {"status": "ok", "detail": "ready"}

    monkeypatch.setattr(main, "_probe_schema", healthy)
    monkeypatch.setattr(main, "_probe_redis", healthy)
    response = TestClient(main.app).get("/ready")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert response.headers["cache-control"] == "no-store"


def test_production_voice_rejects_unapproved_browser_origin(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with TestClient(main.app) as client:
        with pytest.raises(WebSocketDisconnect), client.websocket_connect(
            "/ws/voice", headers={"origin": "https://unapproved.example"},
        ):
            pass
        with client.websocket_connect("/ws/voice", headers={"origin": settings.cors_origins[0]}) as socket:
            socket.send_json({"type": "interim", "text": "hello"})
            assert socket.receive_json() == {"type": "interim", "text": "hello"}
