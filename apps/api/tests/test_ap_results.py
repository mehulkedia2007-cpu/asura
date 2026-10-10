from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest

from daari import geocode, google_jobs, leads, source_cache
from daari.government_jobs import parse
from daari.job_filters import fresh, relevant
from daari.scheme_ranking import rank_records
from daari.scheme_scope import ap_or_national
from daari.schemes import normalize


def test_old_missing_and_future_job_dates_do_not_become_current_on_fetch():
    now = datetime.now(UTC)
    assert fresh((now - timedelta(days=2)).isoformat())
    assert not fresh((now - timedelta(days=61)).isoformat())
    assert not fresh((now + timedelta(days=2)).isoformat())
    assert not fresh(None)
    assert not fresh("unknown")


def test_query_incidental_mentions_do_not_return_unrelated_jobs():
    assert relevant("python", "Python developer")
    assert relevant("python", "AI Engineer", "Build services with Python")
    assert not relevant("python", "Freelance writer", "Topics include Python")
    assert not relevant("python", "Office assistant", "Python is an optional hobby")
    assert not relevant("driver", "Accountant", "Work alongside a driver")
    assert relevant("jobs", "Driver")
    assert leads.normalize_remotive({"url": "https://remotive.com/job/1", "candidate_required_location": "Central Asia"}, "stamp") is None
    assert leads.normalize_remotive({"url": "https://remotive.com/job/1", "candidate_required_location": "Worldwide excluding India"}, "stamp") is None


@pytest.mark.asyncio
async def test_nearby_jobs_exclude_remote_unverified_old_far_and_off_topic(monkeypatch):
    stamp = datetime.now(UTC).isoformat()
    raw = {"id": "near", "title": "Python engineer", "description": "Python services",
           "company": {"display_name": "Example"}, "location": {"display_name": "Guntur, Andhra Pradesh"},
           "latitude": 16.3067, "longitude": 80.4365, "created": stamp,
           "redirect_url": "https://www.adzuna.com/jobs/land/ad/123"}
    candidates = [raw,
                  {**raw, "id": "old", "created": (datetime.now(UTC) - timedelta(days=500)).isoformat()},
                  {**raw, "id": "missing", "latitude": None},
                  {**raw, "id": "far", "latitude": 28.6139, "longitude": 77.2090},
                  {**raw, "id": "offtopic", "title": "Freelance writer", "description": "Python topics"}]
    calls = []
    async def fetch(_client, key, _url, params, _refresh):
        calls.append((key, params))
        if key.startswith("remotive"):
            return {"fetched_at": stamp, "payload": {"jobs": [
                {"id": "remote", "title": "Python engineer", "url": "https://remotive.com/job/2",
                 "candidate_required_location": "India", "publication_date": stamp}]}}, None
        return {"fetched_at": stamp, "payload": {"results": candidates}}, None
    monkeypatch.setattr(leads, "lookup", AsyncMock(return_value=(16.3067, 80.4365)))
    monkeypatch.setattr(leads, "_fetch", fetch)
    monkeypatch.setattr(leads.settings, "ADZUNA_APP_ID", "test")
    monkeypatch.setattr(leads.settings, "ADZUNA_APP_KEY", "test")
    monkeypatch.setattr(google_jobs, "search", AsyncMock(return_value=([], None)))
    result = await leads.search("python", "Guntur", {})
    assert [r["id"] for r in result["leads"]] == ["adzuna:near"]
    assert result["leads"][0]["distance_km"] == 0
    assert not any(key.startswith("remotive") for key, _ in calls)
    assert calls[0][1]["max_days_old"] == 60
    remote = await leads.search("python", "Guntur", {}, include_remote=True)
    assert {r["id"] for r in remote["leads"]} == {"adzuna:near", "remotive:remote"}
    monkeypatch.setattr(leads, "lookup", AsyncMock(return_value=None))
    with pytest.raises(ValueError, match="apPlaceRequired"):
        await leads.search("python", "Mumbai", {})


@pytest.mark.asyncio
async def test_geocoder_accepts_only_an_actual_ap_address(monkeypatch):
    monkeypatch.setattr(source_cache, "read", AsyncMock(return_value=None))
    monkeypatch.setattr(source_cache, "write", AsyncMock())
    monkeypatch.setattr(geocode, "_last_request", 0)
    def response(request):
        assert request.url.params["addressdetails"] == "1"
        return httpx.Response(200, json=[
            {"lat": "17.3", "lon": "78.4", "address": {"state": "Telangana", "country_code": "in"}},
            {"lat": "16.3", "lon": "80.4", "address": {"state": "Andhra Pradesh", "country_code": "in"}}])
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as client:
        assert await geocode.lookup_ap("Guntur", client) == (16.3, 80.4)
        assert await geocode.lookup_ap("Andhra Pradesh", client) is None


def test_other_state_schemes_and_central_restricted_schemes_are_excluded():
    assert ap_or_national({"state": "Andhra Pradesh", "level": "State"})
    assert ap_or_national({"level": "Central"})
    assert not ap_or_national({"state": "Kerala", "level": "State"})
    assert not ap_or_national({"level": "Central", "beneficiary_states": "Kerala"})
    assert normalize({"slug": "test", "schemeName": "Training", "level": "Central",
                      "beneficiaryState": ["Kerala"]}, "stamp") is None


def test_specific_scheme_topic_cannot_be_filled_with_generic_training():
    records = [{"id": "generic", "name_en": "Vocational training", "benefit_text": "Learn skills"},
               {"id": "digital", "name_en": "Electronics training", "benefit_text": "Learn digital skills"}]
    assert [r["id"] for r in rank_records("IT training", records)] == ["digital"]
    unrelated = {"id": "research", "name_en": "Research Training Fellowship", "benefit_text": "Science research", "ministry_or_dept": "Ministry of Information Technology"}
    assert rank_records("IT training", [unrelated], prior={"research": 1.0}) == []
    assert not ap_or_national({"level": "Central", "benefit_text": "Support young researchers of ASEAN member countries"})


def test_government_parser_keeps_current_application_notices_not_exam_updates():
    date = datetime.now(UTC).strftime("%d/%m/%Y")
    html = f"<table><tr><td>{date}</td><td>Recruitment</td><td>Recruitment: Applications invited for Civil Judge</td></tr>" +           f"<tr><td>{date}</td><td>Recruitment</td><td>Recruitment: examination results for Civil Judge</td></tr></table>"
    entry = {"id": "court", "label": "Court", "parser": "aphc_recruitment", "url_template": "https://aphc.gov.in/recruitment.php"}
    rows = parse(html, entry, datetime.now(UTC).isoformat(), "judge")
    assert len(rows) == 1
    assert rows[0]["application_status"] == "verify_on_source"
    assert rows[0]["distance_km"] is None
    assert parse(html, entry, datetime.now(UTC).isoformat(), "nurse") == []


def test_google_relative_dates_are_anchored_to_source_fetch_not_latest_request():
    stamp = datetime.now(UTC).isoformat()
    assert fresh(google_jobs.posted_date("3 days ago", stamp))
    assert not fresh(google_jobs.posted_date("3 months ago", stamp))
    assert google_jobs.posted_date("unknown", stamp) is None


@pytest.mark.asyncio
async def test_google_jobs_never_spends_on_paid_plan_or_exhausted_free_quota(monkeypatch):
    monkeypatch.setattr(google_jobs.settings, "SERPAPI_KEY", "test-private-key")
    monkeypatch.setattr(google_jobs.settings, "SERPAPI_MONTHLY_BUDGET", 100)
    monkeypatch.setattr(google_jobs, "read", AsyncMock(return_value=None))
    for price, usage, expected in [(25, 0, "free_plan_unavailable"), (0, 100, "monthly_budget_exhausted")]:
        requested = []
        def respond(request, requested=requested, price=price, usage=usage):
            requested.append(request.url.path)
            return httpx.Response(200, json={"plan_monthly_price": price, "plan_searches_left": 20, "this_month_usage": usage})
        async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
            found, error = await google_jobs.search(client, "python", "Guntur", (16.3, 80.4))
        assert found == []
        assert error == expected
        assert requested == ["/account"]


def test_invalid_coordinates_never_create_nearby_distance():
    raw = {"redirect_url": "https://www.adzuna.com/jobs/1", "latitude": "nan", "longitude": 80.4}
    record = leads.normalize_adzuna(raw, "stamp", (16.3, 80.4))
    assert record is not None
    assert record["distance_km"] is None
