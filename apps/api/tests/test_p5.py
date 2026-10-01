import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from daari.agent import loop
from daari.intel.corpus import companies, seed, select, stats
from daari.intel.extract_questions import dedupe, extract
from daari.intel.fetchers import allowed_url
from daari.interview.feedback import feedback
from daari.interview.guard import guarded_draft, validate
from daari.interview.session import bank
from daari.main import app
from daari.prep.notice import extract as extract_notice

client = TestClient(app)


def test_company_roles_never_leak_to_another_goal():
    assert len(companies()) == 60
    data = select(seed(), "Tata Consultancy Services", "prime")
    assert data["stats"]["coverage"] == "available"
    assert data["stats"]["sources"] == 2
    assert not select(seed(), "TCS", "data analyst")["questions"]
    assert select(seed(), "TCS", "data analyst")["nearest_roles"] == ["Prime"]
    assert not select(seed(), "unknown", "Prime")["questions"]
    assert not select(seed(), "TCS", "prime", year=2026)["questions"]
    assert stats(seed()[:1])["coverage"] == "thin"
    assert stats([])["coverage"] == "none"


@pytest.mark.parametrize("url", ["http://www.geeksforgeeks.org/interview-experiences/x/", "https://www.geeksforgeeks.org.evil.test/interview-experiences/x/", "https://localhost/foo", "https://user@www.geeksforgeeks.org/interview-experiences/x/", "https://www.geeksforgeeks.org:8080/interview-experiences/x/"])
def test_source_allowlist(url):
    assert not allowed_url(url)


def test_dedupe_is_scoped_to_company_and_role():
    one = seed()[0]
    rows = dedupe([one, {**one, "id": "other", "source_url": seed()[-1]["source_url"]}, {**one, "company": "other", "id": "separate"}])
    assert len(rows) == 2
    assert len(rows[0]["similar"]) == 1


def test_notice_privacy_ambiguity_and_source_spans():
    raw = "Company: TCS\nRole: Prime\nInterview date: 2026-10-04\nCTC: 7 LPA\nEligibility: BTech; Contact: Mr Ravi Kumar 9876543210\nRounds: Coding, Technical, HR\nMode: Online\nCoordinator: Rani Devi\nEmail: person@example.test"
    result = extract_notice(raw)
    assert result["fields"]["interview_date"]["value"] == "2026-10-04"
    assert result["fields"]["rounds"]["value"] == ["Coding", "Technical", "HR"]
    assert result["fields"]["eligibility"]["value"] == "BTech"
    stored = json.dumps(result)
    for value in ("Ravi", "Rani", "9876543210", "person@example.test"):
        assert value not in stored
    assert result["confirmation_required"]
    assert extract_notice("Date: 04/10/2026")["fields"]["interview_date"]["value"] is None
    assert extract_notice("Company: TCS\nCompany: Infosys")["fields"]["company"]["status"] == "conflicting"


def test_prep_requires_user_confirmation():
    body = {"company": "TCS", "role": "Prime", "interview_date": "2026-10-04"}
    assert client.post("/engine/prep/pack", json=body).status_code == 422


@pytest.mark.parametrize("locale", ["en", "te", "hi"])
def test_practice_bank_and_feedback_are_localized_and_guarded(locale):
    assert len(bank("data_analyst", locale)) >= 5
    assert len(bank("delivery_executive", locale)) >= 5
    transcript = "um I worked with a team but could not explain it."
    result = feedback(transcript, locale, 45)
    assert 3 <= len(result["feedback"]) <= 6
    assert all(row["quote"] in transcript for row in result["feedback"])
    assert result["followup"]
    allowed = result["feedback"]
    assert not validate([{**allowed[0], "quote": "invented quote"}], transcript, allowed)
    assert not validate([{**allowed[0], "point": "You will be hired"}], transcript, allowed)
    assert not validate([{**allowed[0], "code": "invented_claim"}], transcript, allowed)


@pytest.mark.asyncio
async def test_feedback_rewrites_once_then_falls_back(monkeypatch):
    from daari.interview import guard
    fake = AsyncMock(return_value=({"content": '{"items":[{"point":"perfect"}]}'}, "fake", False))
    monkeypatch.setattr(guard, "complete", fake)
    allowed = feedback("I wrote a report")["feedback"]
    rows, mode = await guarded_draft("I wrote a report", allowed)
    assert mode == "metrics_template" and len(rows) >= 3
    assert fake.await_count == 2


@pytest.mark.asyncio
async def test_extraction_rejects_invented_questions(monkeypatch):
    from daari.intel import extract_questions
    question = seed()[0]
    result = {"tool_calls": [{"function": {"name": "extract_questions", "arguments": json.dumps({"questions": [
        {"text": "Invented question?", "round": "technical", "skill_ids": []},
        {"text": "What is SQL?", "round": "technical", "skill_ids": ["sql_querying", "fake_skill"]}]})}}]}
    monkeypatch.setattr(extract_questions, "complete", AsyncMock(return_value=(result, "fake", False)))
    metadata = {k: question[k] for k in ("company", "role", "year", "as_of", "date_kind", "source_url", "fetched_at")}
    rows = await extract("What is SQL?", metadata, ["sql_querying"])
    assert len(rows) == 1 and rows[0]["skill_ids"] == ["sql_querying"]


@pytest.mark.asyncio
async def test_agent_cannot_invent_notice_confirmation():
    result = await loop._execute("build_prep_pack", {}, loop.AgentRequest(text="prepare me"))
    assert result == {"confirmation_required": True}
    assert {"get_company_questions", "build_prep_pack", "start_interview", "interview_feedback"} <= set(loop._ARG_MODELS)


@pytest.mark.asyncio
async def test_short_prep_window_preserves_shortfall(monkeypatch):
    from daari.prep import pack
    monkeypatch.setattr(pack, "search", AsyncMock(return_value=select(seed(), "TCS", "Prime")))
    result = await pack.build(pack.PackArgs(confirmed=True, company="TCS", role="Prime", interview_date=datetime.now(ZoneInfo("Asia/Kolkata")).date()+timedelta(days=1)))
    assert not result["plan"]["feasible"]
    assert result["plan"]["capacity_hours"] == 2
    assert result["plan"]["shortfall_hours"] > 0


@pytest.mark.asyncio
async def test_agent_question_tool_keeps_citations_and_rejects_invented_prose(monkeypatch):
    from daari import p5
    calls = iter([
        ({"role": "assistant", "content": "", "tool_calls": [{"id": "q", "function": {
            "name": "get_company_questions", "arguments": '{"company":"tcs","role":"Prime"}'}}]}, "fake", False),
        ({"role": "assistant", "content": "You will be hired tomorrow.", "tool_calls": []}, "fake", False),
    ])
    async def complete(*args, **kwargs):
        return next(calls)
    monkeypatch.setattr(loop, "complete", complete)
    monkeypatch.setattr(p5, "get_company_questions", AsyncMock(return_value=select(seed(), "tcs", "Prime")))
    result = await loop.run(loop.AgentRequest(text="TCS Prime questions"))
    assert result["trace"][0]["tool"] == "get_company_questions"
    assert result["trace"][0]["status"] == "ok"
    assert result["cards"] and result["verification"]["citations"]
    assert result["verification"]["struck"]
    assert all("will be hired" not in row["text"] for row in result["verification"]["sentences"])


@pytest.mark.asyncio
async def test_live_jd_anchors_fifth_question_and_skips_flagged_leads(monkeypatch):
    from daari import p5
    lead = {"title": "Analyst", "description": "Use SQL to clean data.", "required_skills": {"sql_querying": 3},
            "source_url": "https://example.org/job", "fetched_at": "2026-09-25T00:00:00+00:00", "scam": {"score": 0}}
    monkeypatch.setattr(p5.leads, "search", AsyncMock(return_value={"leads": [lead]}))
    starter = AsyncMock(return_value={"questions": []})
    monkeypatch.setattr(p5.session, "start", starter)
    await p5.start_interview(p5.StartArgs(job_query="analyst"))
    assert starter.call_args.args[-1]["source_span"] == lead["description"]
    lead["scam"]["score"] = .8
    await p5.start_interview(p5.StartArgs(job_query="analyst"))
    assert starter.call_args.args[-1] is None


def test_invalid_feedback_and_dates_are_rejected():
    assert client.post("/engine/interview/feedback", json={"transcript": "   "}).status_code == 422
    assert client.post("/engine/interview/feedback", json={"transcript": "okay", "duration_seconds": -1}).status_code == 422
    assert client.post("/engine/interview/transcribe", json={"audio": "%%%"}).status_code == 422
