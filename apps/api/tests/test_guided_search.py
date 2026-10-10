from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from daari import schemes


@pytest.mark.asyncio
async def test_named_scheme_returns_only_selected_source_without_network(monkeypatch):
    record = {"id": "source-a", "name_en": "Training support", "state": "Andhra Pradesh",
              "level": "State", "fetched_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
              "url": "https://example.gov.in/a", "rules": {"all": [], "any": []}, "rules_complete": False}
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[record, {**record, "id": "source-b"}]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 2}))
    fetch = AsyncMock(side_effect=AssertionError("saved selection must not wait for a provider"))
    monkeypatch.setattr(schemes, "search_pages", fetch)
    result = await schemes.search_saved("Training", {}, "source-a")
    assert result is not None
    assert [r["id"] for r in result["schemes"]] == ["source-a"]
    assert result["schemes"][0]["eligibility"]["status"] == "unknown"
    assert result["stale"] is True
    fetch.assert_not_awaited()
    with pytest.raises(ValueError):
        await schemes.search_saved("Training", {}, "missing-source")


@pytest.mark.asyncio
async def test_no_saved_match_is_an_empty_saved_response(monkeypatch):
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 0}))
    assert (await schemes.search_saved("farmer", {}))["schemes"] == []


def test_named_scheme_library_excludes_foreign_student_targets():
    from daari.scheme_scope import ap_or_national

    assert not ap_or_national({"level": "Central", "name_en": "Awarding Teleeducation Scholarships To Afghan Students"})
    assert not ap_or_national({"level": "Central", "name_en": "Scholarship for International Students"})
    assert ap_or_national({"level": "Central", "name_en": "National Overseas Scholarship For Scheduled Caste Candidates"})

@pytest.mark.asyncio
async def test_empty_search_returns_promptly_without_provider_calls(monkeypatch):
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 0}))
    pages = AsyncMock(side_effect=AssertionError("ordinary search must not fetch sources"))
    monkeypatch.setattr(schemes, "search_pages", pages)
    result = await schemes.search_interactive("no matching source", {})
    assert result["schemes"] == []
    assert result["refresh_status"] == "not_requested"
    pages.assert_not_awaited()


@pytest.mark.asyncio
async def test_refresh_timeout_keeps_selected_record_and_original_date(monkeypatch):
    import asyncio

    record = {"id": "source-a", "name_en": "Training support", "source": "myScheme",
              "level": "Central", "state": None, "fetched_at": "2026-09-01T00:00:00+00:00",
              "url": "https://www.myscheme.gov.in/schemes/source-a",
              "rules_complete": False, "rules": {"all": [], "any": []}}
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[record]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 1}))
    monkeypatch.setattr(schemes, "INTERACTIVE_REFRESH_TIMEOUT_S", .01)

    async def slow_detail(*args):
        await asyncio.sleep(10)

    monkeypatch.setattr(schemes, "detail", slow_detail)
    result = await asyncio.wait_for(schemes.search_interactive("Training support", {}, True, scheme_id="source-a"), .5)
    assert [row["id"] for row in result["schemes"]] == ["source-a"]
    assert result["schemes"][0]["fetched_at"] == record["fetched_at"]
    assert result["source_errors"] == ["refresh_timeout"]
    assert result["refresh_status"] == "unavailable"


@pytest.mark.asyncio
async def test_selected_scheme_stays_visible_when_rules_do_not_match(monkeypatch):
    record = {"id": "age-rule", "name_en": "Age-specific training", "state": "Andhra Pradesh",
              "level": "State", "fetched_at": "2026-09-01T00:00:00+00:00",
              "url": "https://example.gov.in/a", "rules_complete": True,
              "rules": {"all": [{"field": "age", "op": "gte", "value": 21, "snippet": "age 21 or above"}], "any": []}}
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[record]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 1}))
    selected = await schemes.search_interactive("Age-specific training", {"age": 19}, scheme_id="age-rule")
    assert selected["schemes"][0]["eligibility"]["status"] == "false"
    assert (await schemes.search_interactive("training", {"age": 19}))["schemes"] == []


@pytest.mark.asyncio
async def test_refresh_retains_fast_source_results_when_other_source_is_slow(monkeypatch):
    import asyncio

    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 0}))
    monkeypatch.setattr(schemes, "INTERACTIVE_REFRESH_TIMEOUT_S", .03)
    raw = {"slug": "real-source-shape", "scheme_name": "Training source fixture", "level": "Central"}
    pages = AsyncMock(return_value=([(raw, "2026-10-10T00:00:00+00:00")], [], False))
    monkeypatch.setattr(schemes, "search_pages", pages)
    monkeypatch.setattr(schemes, "upsert", AsyncMock())

    async def slow_portal(*args):
        await asyncio.sleep(10)

    monkeypatch.setattr(schemes, "search_ap_portal", slow_portal)
    result = await asyncio.wait_for(schemes.search_interactive("training", {}, True), .5)
    assert len(result["schemes"]) == 1
    assert result["schemes"][0]["id"] == "real-source-shape"
    assert result["schemes"][0]["eligibility"]["status"] == "unknown"
    assert pages.call_args.kwargs["max_results"] == 100

@pytest.mark.asyncio
async def test_selected_refresh_displays_actual_new_details_without_embeddings(monkeypatch):
    old = "2026-09-01T00:00:00+00:00"
    now = datetime.now(UTC).isoformat()
    record = schemes.normalize({"slug": "source-a", "scheme_name": "Training support", "level": "Central",
                                "briefDescription": "Previous source details"}, old)
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[record]))
    monkeypatch.setattr(schemes, "coverage", AsyncMock(return_value={"indexed": 1}))
    payload = {"en": {"schemeContent": {"benefits_md": "New source benefit text"}}, "te": {},
               "documents": {}, "channels": [], "fetched_at": now, "stale": False}
    detail = AsyncMock(return_value=(payload, []))
    monkeypatch.setattr(schemes, "detail", detail)
    save = AsyncMock()
    monkeypatch.setattr(schemes, "upsert", save)
    result = await schemes.search_interactive("Training support", {}, True, scheme_id="source-a")
    assert result["schemes"][0]["benefit_text"] == "New source benefit text"
    assert result["schemes"][0]["fetched_at"] == now
    assert result["refresh_status"] == "updated"
    assert result["stale"] is False
    assert save.call_args.kwargs["embed_documents"] is False
    assert detail.call_args.args[1] == "source-a"

@pytest.mark.asyncio
async def test_whitespace_search_is_rejected_before_catalog_access(monkeypatch):
    browse = AsyncMock(side_effect=AssertionError("invalid query must not load catalog"))
    monkeypatch.setattr(schemes, "browse", browse)
    with pytest.raises(ValueError, match="Enter a scheme name"):
        await schemes.search_interactive("   ", {})
    browse.assert_not_awaited()
