"""Daily scheme refresh: cron routes are locked, partial fetches never overwrite saved records."""

import pytest
from fastapi.testclient import TestClient

from daari import p3, schemes
from daari.main import app
from daari.schemes import merge_detail, normalize

client = TestClient(app)


def _detail(steps: list[dict]) -> dict:
    return {"en": {"applicationProcess": steps}, "te": {}, "documents": {}, "channels": [],
            "fetched_at": "2026-11-05T00:00:00+00:00", "stale": False}


def test_apply_link_is_kept_only_when_it_is_a_web_address():
    scheme = normalize({"slug": "synthetic-apply", "schemeName": "Synthetic", "level": "Central"},
                       "2026-11-01T00:00:00+00:00")
    assert scheme is not None
    merge_detail(scheme, _detail([
        {"mode": "Online", "process": "Register.", "url": "https://portal.example.gov.in/apply "},
        {"mode": "Offline", "process": "Visit the office.", "url": ""},
        {"mode": "Online", "process": "Bad link.", "url": "javascript:alert(1)"},
        {"mode": "Online", "process": "Broken link.", "url": "https://portal example.gov.in"},
    ]))
    assert [step["url"] for step in scheme["apply_steps"]] == ["https://portal.example.gov.in/apply", "", "", ""]


def test_cron_routes_refuse_without_the_secret(monkeypatch):
    async def fake_refresh():
        return {"checked": 0, "updated": 0, "errors": []}

    monkeypatch.setattr(schemes, "refresh_oldest", fake_refresh)
    monkeypatch.setattr(p3.settings, "CRON_SECRET", None)
    assert client.get("/engine/cron/schemes/1").status_code == 503
    monkeypatch.setattr(p3.settings, "CRON_SECRET", "test-secret-value-123")
    assert client.get("/engine/cron/schemes/1").status_code == 401
    assert client.get("/engine/cron/schemes/1", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/engine/cron/schemes/1", headers={"Authorization": "Bearer test-secret-value-123"})
    assert ok.status_code == 200 and ok.json()["batch"] == 1
    assert client.get("/engine/cron/schemes/9", headers={"Authorization": "Bearer test-secret-value-123"}).status_code == 422


@pytest.mark.asyncio
async def test_refresh_oldest_updates_oldest_first_and_skips_partial_fetches(monkeypatch):
    records = [normalize({"slug": slug, "schemeName": slug, "level": "Central"}, stamp)
               for slug, stamp in (("newer", "2026-10-09T00:00:00+00:00"), ("oldest", "2026-09-01T00:00:00+00:00"))]
    records.append({"id": "ap-msme:x", "source": "AP MSME directory", "fetched_at": "2026-01-01T00:00:00+00:00"})
    saved: list[str] = []

    async def fake_browse():
        return records

    async def fake_detail(client, slug, locale, refresh):
        if slug == "newer":
            return _detail([]), ["documents_unavailable"]
        return _detail([{"mode": "Online", "process": "Apply.", "url": "https://portal.example.gov.in"}]), []

    async def fake_upsert(record, **kwargs):
        saved.append(record["id"])

    monkeypatch.setattr(schemes, "browse", fake_browse)
    monkeypatch.setattr(schemes, "detail", fake_detail)
    monkeypatch.setattr(schemes, "upsert", fake_upsert)
    result = await schemes.refresh_oldest(limit=2)
    assert saved == ["oldest"]
    assert result == {"checked": 2, "updated": 1, "errors": ["documents_unavailable"]}
