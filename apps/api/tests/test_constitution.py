"""Named regression tests for the thirteen DAARI Constitution articles."""

from datetime import UTC, datetime

import pytest
from daari_core.roadmap import compute

from daari.agent import loop
from daari.evidence import _i18n, _scam_metrics, _trace_event_complete
from daari.grounding.verifier import Evidence, verify
from daari.prep.notice import extract
from daari.taxonomy_loader import get_taxonomy


def _evidence(text: str) -> Evidence:
    return Evidence("source-1", text, "https://example.org/evidence",
                    datetime(2026, 9, 25, tzinfo=UTC))


def test_article_1_memory_is_not_a_source():
    result = verify("A new policy applies.", [])
    assert result["no_data"] and result["struck"]


def test_article_2_dates():
    source = _evidence("Report updated 2026-09-25.")
    assert verify("Report updated 2026-09-25.", [source])["sentences"]
    assert verify("Report updated 2026-09-26.", [source])["no_data"]


def test_article_3_numbers():
    source = _evidence("The benefit is ₹500.")
    assert verify("The benefit is ₹500.", [source])["sentences"]
    assert verify("The benefit is ₹900.", [source])["struck"]


def test_article_4_names():
    source = _evidence("TCS opened applications.")
    assert verify("TCS opened applications.", [source])["sentences"]
    assert verify("Acme opened applications.", [source])["no_data"]


def test_article_5_unknowns_are_answers():
    result = verify("No answer is available.", [], searched="the official sources")
    assert result["no_data"]
    assert "official sources" in result["message"]


def test_article_6_no_uncited_prose():
    result = verify("TCS opened applications.", [_evidence("TCS opened applications.")])
    assert result["sentences"][0]["citation_ids"] == ["source-1"]


def test_article_7_deterministic_engine():
    taxonomy = get_taxonomy()
    first = compute(taxonomy, {"sql_querying": 2}, "data_analyst", {})
    replay = compute(taxonomy, {"sql_querying": 2}, "data_analyst", {})
    assert first == replay


def test_article_8_translation_adds_no_entity():
    source = _evidence("నైపుణ్య మార్గం")
    assert verify("నైపుణ్య మార్గం", [source])["sentences"]
    assert not verify("వేరే వాస్తవం", [source])["sentences"]
    assert _i18n()["passed"]


def test_article_9_forbidden_claims():
    assert verify("Guaranteed placement.", [_evidence("Guaranteed placement.")])["struck"]


def test_article_10_never_instructs_payment():
    assert _scam_metrics()["passed"]
    assert verify("Pay a fee to apply.", [_evidence("Pay a fee to apply.")])["struck"]


def test_article_11_no_personal_names_persisted():
    result = extract(
        "Company: TCS\nRole: Analyst\nContact: Ravi Kumar 9876543210\n"
        "Email: person@example.test",
    )
    serialized = str(result)
    assert all(value not in serialized for value in ("Ravi", "9876543210", "person@example.test"))


@pytest.mark.asyncio
async def test_article_12_trace_completeness(monkeypatch):
    async def no_provider(messages, tools):
        return None, "unavailable", False

    async def sourced_jobs(name, args, request):
        return {"leads": [{"title": "SQL analyst", "source_url": "https://example.org/job",
                           "fetched_at": datetime.now(UTC).isoformat()}]}

    monkeypatch.setattr(loop, "complete", no_provider)
    monkeypatch.setattr(loop, "_execute", sourced_jobs)
    result = await loop.run(loop.AgentRequest(text="Find a job near Guntur"))
    assert result["trace"] and _trace_event_complete(result["trace"][0])
    assert result["verification"]["sentences"][0]["citation_ids"]


@pytest.mark.asyncio
async def test_article_13_degrades_to_cards(monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("guard unavailable")

    async def no_provider(messages, tools):
        return None, "unavailable", False

    async def sourced_jobs(name, args, request):
        return {"leads": [{"title": "SQL analyst", "source_url": "https://example.org/job",
                           "fetched_at": datetime.now(UTC).isoformat()}]}

    monkeypatch.setattr(loop, "verify", broken)
    monkeypatch.setattr(loop, "complete", no_provider)
    monkeypatch.setattr(loop, "_execute", sourced_jobs)
    result = await loop.run(loop.AgentRequest(text="Find a job near Guntur"))
    assert result["cards"]
    assert result["verification"]["no_data"] is True
    assert result["verification"]["sentences"] == []
    assert result["verification"]["message"]
