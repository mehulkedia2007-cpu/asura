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


@pytest.mark.asyncio
async def test_detail_precedes_broad_indexing_and_defers_document_embeddings(monkeypatch):
    calls = []
    raw = {"slug": "synthetic-detail", "scheme_name": "Skill training fixture",
           "level": "Central", "eligibility": "Applicant age between 18 and 30 years"}

    async def pages(*args, **kwargs):
        return [(raw, "2026-10-01T00:00:00+00:00")], [], False

    async def portal(*args, **kwargs):
        return [], []

    async def detail(*args, **kwargs):
        calls.append("detail")
        return None, []

    async def upsert(record, **kwargs):
        if kwargs.get("summary_only"):
            calls.append("summary")
            await asyncio.sleep(10)
        else:
            calls.append("detail_saved")
            assert kwargs["embed_documents"] is False

    async def retrieval(*args, **kwargs):
        return {"records": [], "kind": "lexical", "embedding_kind": None}

    async def coverage():
        return {"indexed": 1}

    monkeypatch.setattr(schemes, "REFRESH_TIMEOUT_S", 0.05)
    monkeypatch.setattr(schemes, "search_pages", pages)
    monkeypatch.setattr(schemes, "search_ap_portal", portal)
    monkeypatch.setattr(schemes, "detail", detail)
    monkeypatch.setattr(schemes, "upsert", upsert)
    monkeypatch.setattr(schemes, "retrieve", retrieval)
    monkeypatch.setattr(schemes, "coverage", coverage)
    result = await asyncio.wait_for(schemes.search("skill training", {}), timeout=2)
    assert calls == ["detail", "detail_saved", "summary"]
    assert result["next_question"]["field"] == "age"
    assert result["schemes"][0]["eligibility"]["status"] == "unknown"
    assert result["source_errors"] == ["refresh_timeout"]
