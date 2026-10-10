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
async def test_no_saved_match_keeps_real_source_fallback_available(monkeypatch):
    monkeypatch.setattr(schemes, "browse", AsyncMock(return_value=[]))
    assert await schemes.search_saved("farmer", {}) is None


def test_named_scheme_library_excludes_foreign_student_targets():
    from daari.scheme_scope import ap_or_national

    assert not ap_or_national({"level": "Central", "name_en": "Awarding Teleeducation Scholarships To Afghan Students"})
    assert not ap_or_national({"level": "Central", "name_en": "Scholarship for International Students"})
    assert ap_or_national({"level": "Central", "name_en": "National Overseas Scholarship For Scheduled Caste Candidates"})
