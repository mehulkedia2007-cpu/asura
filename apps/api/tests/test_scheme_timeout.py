"""Cold refresh and embedding failures still return honest, bounded results."""

import asyncio

import pytest

from daari import schemes


@pytest.mark.asyncio
async def test_cold_scheme_refresh_returns_cached_evidence_on_timeout(monkeypatch):
    async def slow_pages(*args, **kwargs):
        await asyncio.sleep(10)

    async def cached_retrieval(*args, **kwargs):
        return {"records": [{
            "id": "synthetic-cache-fixture", "state": "Andhra Pradesh",
            "retrieval_score": 1.0,
            "name_en": "Synthetic test scheme", "url": "https://example.org/test-source",
            "fetched_at": "2026-09-01T00:00:00+00:00", "rules_complete": False,
            "rules": {"all": [], "any": []},
        }], "kind": "lexical", "embedding_kind": None}

    async def empty_coverage():
        return {"indexed": 1}

    monkeypatch.setattr(schemes, "REFRESH_TIMEOUT_S", 0.01)
    monkeypatch.setattr(schemes, "search_pages", slow_pages)
    monkeypatch.setattr(schemes, "retrieve", cached_retrieval)
    monkeypatch.setattr(schemes, "coverage", empty_coverage)
    result = await asyncio.wait_for(schemes.search("skill", {}), timeout=2)
    assert len(result["schemes"]) == 1
    assert result["schemes"][0]["url"] == "https://example.org/test-source"
    assert result["schemes"][0]["fetched_at"] == "2026-09-01T00:00:00+00:00"
    assert result["schemes"][0]["eligibility"]["status"] == "unknown"
    assert result["stale"] is True
    assert result["truncated"] is True
    assert result["source_errors"] == ["refresh_timeout"]
    assert result["next_question"] is None
