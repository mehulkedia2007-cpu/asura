from daari_core.eligibility import evaluate
from daari_core.geo import haversine
from daari_core.match import Candidate, match
from daari_core.scam import score
from daari_core.taxonomy import load


def test_haversine_and_coordinates():
    assert haversine(16.3067, 80.4365, 16.3067, 80.4365) == 0
    assert 28 < haversine(16.3067, 80.4365, 16.5062, 80.6480) < 35


def test_scam_payment_flagged_before_display():
    result = score("Registration fee required; contact only via WhatsApp", "Unknown",
                   "recruiter@gmail.com")
    assert result.badge == "red"
    assert result.score >= 0.8
    assert score("Interview details on employer site", "Example Ltd").badge == "none"
    assert score("No application fee", "Example Ltd").badge == "none"
    assert score("No application fee. Registration fee required", "Example Ltd").badge == "red"


def test_scam_signal_catches_telugu_and_hindi_payment_phrases():
    assert score("రిజిస్ట్రేషన్ ఫీజు చెల్లించండి", "Example Ltd").badge == "red"
    assert score("पंजीकरण शुल्क भुगतान करें", "Example Ltd").badge == "red"
    assert score("ఫీజు లేదు. దరఖాస్తు సమర్పించండి", "Example Ltd").badge == "none"


def test_scam_signal_catches_localized_whatsapp_only_contact():
    result = score("వాట్సాప్ ద్వారా మాత్రమే సంప్రదించండి", "Example Ltd")
    assert "WhatsApp" in " ".join(result.reasons)


def test_eligibility_is_three_valued_and_snippet_backed():
    rules = {"all": [
        {"field": "state", "op": "eq", "value": "Andhra Pradesh", "snippet": "Resident of Andhra Pradesh"},
        {"field": "annual_income", "op": "lte", "value": 200000, "snippet": "Income up to 200000"},
    ]}
    assert evaluate({"state": "Andhra Pradesh"}, rules).status == "unknown"
    assert evaluate({"state": "Telangana"}, rules).status == "false"
    result = evaluate({"state": "Andhra Pradesh", "annual_income": 100000}, rules)
    assert result.status == "true"
    assert len(result.reasons) == 2


def test_match_uses_measured_distance(skills_data, roles_data):
    taxonomy = load(skills_data, roles_data)
    candidate = Candidate("near", "Job", "Employer", "Other district", {}, "Adzuna",
                          "https://adzuna.in/job", "2026-09-25", extra={"distance_km": 18.0})
    nearby = match(taxonomy, {}, [candidate], radius_km=25)[0]
    outside = match(taxonomy, {}, [candidate], radius_km=10)[0]
    assert nearby.components["constraint_fit"] == 1.0
    assert outside.components["constraint_fit"] == 0.0
