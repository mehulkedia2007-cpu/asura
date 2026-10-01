from datetime import UTC, datetime

from fastapi.testclient import TestClient

from daari.ap_portal import _CARD
from daari.grounding.verifier import Evidence, verify
from daari.leads import normalize_adzuna, normalize_remotive
from daari.main import app
from daari.portal_sources import extract_links
from daari.scam_llm import validate as validate_scam_llm
from daari.scheme_rules import validate
from daari.schemes import _items, extract_rules, normalize


def test_leads_require_real_source_and_compute_distance():
    stamp = datetime.now(UTC).isoformat()
    raw = {"id": 42, "title": "SQL analyst", "description": "No application fee",
           "company": {"display_name": "Employer"},
           "location": {"display_name": "Guntur"}, "latitude": 16.3067, "longitude": 80.4365,
           "redirect_url": "https://www.adzuna.com/jobs/land/ad/42"}
    lead = normalize_adzuna(raw, stamp, (16.3067, 80.4365))
    assert lead is not None
    assert lead["distance_km"] == 0
    assert "sql_querying" in lead["required_skills"]
    assert normalize_adzuna({**raw, "redirect_url": "https://evil.example/42"}, stamp, None) is None
    remote = normalize_remotive({"id": 1, "url": "https://remotive.com/remote-jobs/1"}, stamp)
    assert remote is not None and remote["distance_km"] is None


def test_scheme_qualification_requires_complete_source_rules():
    stamp = datetime.now(UTC).isoformat()
    raw = {"slug": "sample", "scheme_name": "Sample scheme", "level": "State",
           "beneficiary_states": ["Andhra Pradesh"], "eligibility": "Applicant must be a resident of Andhra Pradesh"}
    scheme = normalize(raw, stamp)
    assert scheme is not None and scheme["rules_complete"]
    assert normalize({**raw, "beneficiary_states": ["Kerala"]}, stamp) is None
    _, complete = extract_rules("Applicant must be a resident of Andhra Pradesh. Other conditions apply")
    assert not complete
    historical_shape = {"data": {"hits": {"items": [{"fields": {
        "slug": "sample", "schemeName": "Sample scheme", "level": "Central",
        "briefDescription": "A sourced summary"}}]}}}
    assert _items(historical_shape)[0]["schemeName"] == "Sample scheme"


def test_verifier_strikes_unsupported_and_returns_no_data():
    evidence = [Evidence("s1", "The scheme pays ₹1000.", "https://gov.in/s1", datetime.now(UTC))]
    result = verify("The scheme pays ₹1000. Guaranteed placement.", evidence)
    assert result["sentences"][0]["citation_ids"] == ["s1"]
    assert result["struck"][0]["reason"] == "forbidden_claim"
    assert verify("The scheme pays ₹2000.", evidence)["no_data"]


def test_p3_routes_validate_before_network():
    client = TestClient(app)
    assert client.post("/engine/leads/search", json={"query": "driver", "place": "Guntur",
                                                     "held": {"invented": 3}}).status_code == 422
    assert client.post("/engine/schemes/search", json={"query": ""}).status_code == 422


def test_llm_rules_require_exact_source_snippets_and_coverage():
    text = "The applicant must be a resident of Andhra Pradesh.\nAnnual income must be below Rs.200000"
    raw = {"all": [
        {"field": "state", "op": "eq", "value": "Andhra Pradesh", "snippet": "The applicant must be a resident of Andhra Pradesh."},
        {"field": "annual_income", "op": "lte", "value": 200000, "snippet": "Annual income must be below Rs.200000"},
    ], "any": [], "complete": True}
    assert validate(raw, text)[1]
    assert not validate({**raw, "all": raw["all"][:1]}, text)[1]
    assert not validate({**raw, "all": [{**raw["all"][0], "snippet": "A guessed condition"}]}, text)[1]
    assert not validate({**raw, "all": [{**raw["all"][0], "value": "Kerala"}, raw["all"][1]]}, text)[1]
    assert not validate({**raw, "all": [raw["all"][0], {**raw["all"][1], "value": 300000}]}, text)[1]


def test_ap_directory_card_parser_requires_sourced_summary():
    card = "{id:`ESDP`,name:`Entrepreneurship and Skill Development Programme`,shortName:`ESDP`," \
           "benefitSummary:`Training through public institutions`,tags:[`skills`],status:`active`}"
    match = _CARD.search(card)
    assert match is not None
    assert match["id"] == "ESDP" and match["summary"] == "Training through public institutions"
    assert _CARD.search(card.replace("status:`active`", "status:`inactive`")) is None


def test_registered_portal_links_stay_on_official_host():
    links = extract_links(
        '<a href="/schemes/one">Skill training scheme</a>'
        '<a href="https://outside.example/scheme">Loan scheme</a>',
        "https://government.example/schemes",
    )
    assert links == [{"label": "Skill training scheme",
                      "url": "https://government.example/schemes/one"}]


def test_scam_second_opinion_requires_exact_non_negated_quote():
    source = "A processing fee of Rs 500 is required before the interview."
    candidate = {"risky": True, "reason": "Payment pressure", "quote": "processing fee of Rs 500"}
    assert validate_scam_llm(candidate, source)[0] == 0.2
    assert validate_scam_llm({**candidate, "quote": "pay a fee"}, source)[0] == 0
    assert validate_scam_llm({**candidate, "reason": "Guaranteed scam"}, source)[0] == 0
    assert validate_scam_llm({**candidate, "quote": "No processing fee is charged"},
                             "No processing fee is charged")[0] == 0
