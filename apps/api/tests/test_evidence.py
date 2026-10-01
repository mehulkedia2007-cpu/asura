"""P6 evidence endpoint exposes measured, scoped product evidence."""

import ssl
from contextlib import asynccontextmanager

import pytest
from fastapi.testclient import TestClient

from daari import evidence
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


def test_packaged_evidence_without_frontend_catalogs(monkeypatch, tmp_path):
    expected = evidence._i18n()
    # Keep the real eval bundle but emulate the API's excluded apps/web tree.
    (tmp_path / "packages").symlink_to(evidence.REPO_ROOT / "packages", target_is_directory=True)
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps/api").symlink_to(evidence.REPO_ROOT / "apps/api", target_is_directory=True)
    monkeypatch.setattr(evidence, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("VERCEL_GIT_COMMIT_SHA", "123456789abcdef")
    response = client.get("/engine/evidence")
    assert response.status_code == 200
    body = response.json()
    assert body["i18n"] == expected
    assert body["i18n"]["keys"] == 363
    assert body["ci_sha"] == "123456789abc"
    assert body["constitution"][7]["status"] == "green"


def test_bundled_translation_report_matches_actual_catalogs():
    assert evidence._json("i18n_report.json") == evidence._i18n()


@pytest.mark.asyncio
async def test_live_metric_uses_direct_cloud_url_and_verified_tls(monkeypatch):
    captured = {}

    class Records:
        def scalars(self):
            return []

    class Connection:
        async def execute(self, query):
            return Records()

    class Engine:
        @asynccontextmanager
        async def connect(self):
            yield Connection()

        async def dispose(self):
            pass

    def create_engine(url, **kwargs):
        captured.update(url=url, **kwargs)
        return Engine()

    monkeypatch.setattr(evidence, "_LIVE_SCHEME_CACHE", None)
    monkeypatch.setattr(evidence.settings, "DATABASE_URL", "postgresql://fixture:fixture@pooled.example/test")
    monkeypatch.setattr(evidence.settings, "DATABASE_URL_UNPOOLED",
                        "postgresql://fixture:fixture@direct.example/test?sslmode=require&channel_binding=require")
    monkeypatch.setattr(evidence, "create_async_engine", create_engine)
    result = await evidence._live_scheme_metrics()
    assert result["available"] is True
    assert "direct.example" in captured["url"]
    assert "channel_binding" not in captured["url"]
    context = captured["connect_args"]["ssl"]
    assert isinstance(context, ssl.SSLContext)
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
