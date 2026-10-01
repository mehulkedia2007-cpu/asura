"""P6 evidence endpoint exposes measured, scoped product evidence."""

from fastapi.testclient import TestClient

from daari.main import app

client = TestClient(app)


def test_evidence_contains_real_gates_and_honest_limits():
    response = client.get("/engine/evidence")
    assert response.status_code == 200
    body = response.json()

    assert body["phase"] == "P6"
    assert "not field validation" in body["scope"]
    assert body["scheme_retrieval"]["precision_at_5"] >= 0.8
    assert "live_scheme_retrieval" in body
    assert "scope" in body["live_scheme_retrieval"]
    assert body["scam"]["passed"] is True
    assert body["grounding"]["no_data"]["violations"] == 0
    assert body["match_ablations"]["passed"] is True
    assert body["match_ablations"]["graph_delta"] > 0
    assert body["shared_engine"]["import_graph"]["status"] == "green"
    assert len(body["constitution"]) == 13
    assert all(row["status"] == "green" for row in body["constitution"])
    assert body["i18n"]["passed"] is True


def test_evidence_has_a_stable_top_level_alias():
    response = client.get("/evidence")
    assert response.status_code == 200
    assert response.json()["phase"] == "P6"
