"""P6 evidence assembly.

The evidence screen is deliberately read-only and fail-closed. It reports
development regressions and cached rehearsals with their scope attached; it
does not turn a missing live sample into a made-up benchmark.
"""

from __future__ import annotations

import ast
import asyncio
import json
import time
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from daari_core import telemetry
from daari_core.graph import build as build_graph
from daari_core.match import Candidate, match
from daari_core.roadmap import compute
from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from daari.agent.loop import _safe_verify
from daari.config import settings
from daari.db import _to_asyncpg_url
from daari.embeddings import get_embeddings
from daari.grounding.verifier import Evidence, verify
from daari.prep.notice import extract as extract_notice
from daari.scheme_ranking import rank_records
from daari.taxonomy_loader import get_taxonomy
from daari.voice.latency import summary as voice_summary

router = APIRouter(prefix="/engine", tags=["P6 evidence"])
_LIVE_SCHEME_CACHE: tuple[float, dict[str, Any]] | None = None
_LIVE_SCHEME_LOCK = asyncio.Lock()

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "evals"
FORBIDDEN_CORE_IMPORTS = {
    "fastapi", "sqlalchemy", "httpx", "redis", "asyncpg", "alembic",
    "openai", "groq", "google", "anthropic", "ollama",
}
CONSTITUTION_ARTICLES = (
    ("I", "Sources of truth", "test_article_1_memory_is_not_a_source"),
    ("II", "Time", "test_article_2_dates"),
    ("III", "Numbers", "test_article_3_numbers"),
    ("IV", "Names and entities", "test_article_4_names"),
    ("V", "Unknowns are answers", "nodata_adversarial.jsonl"),
    ("VI", "Citations", "test_article_6_no_uncited_prose"),
    ("VII", "Determinism", "test_purity"),
    ("VIII", "Language", "test_article_8_translation_adds_no_entity"),
    ("IX", "Scope and seriousness", "test_article_9_forbidden_claims"),
    ("X", "Scams and safety", "scam_golden.jsonl"),
    ("XI", "Data hygiene", "test_article_11_no_personal_names_persisted"),
    ("XII", "Transparency", "test_article_12_trace_completeness"),
    ("XIII", "Failure mode", "test_article_13_degrades_to_cards"),
)


def _rows(filename: str) -> list[dict[str, Any]]:
    path = EVALS_DIR / filename
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _json(filename: str) -> dict[str, Any]:
    return json.loads((EVALS_DIR / filename).read_text(encoding="utf-8"))


def _scam_metrics() -> dict[str, Any]:
    from daari_core.scam import score

    cases = _rows("scam_golden.jsonl")
    tp = fp = fn = tn = 0
    failures: list[str] = []
    for case in cases:
        result = score(case["description"], case["org"], case.get("contact", ""),
                       case.get("pay"), case.get("median"))
        predicted = result.score >= 0.5
        expected = bool(case["label"])
        if predicted and expected:
            tp += 1
        elif predicted and not expected:
            fp += 1
        elif not predicted and expected:
            fn += 1
        else:
            tn += 1
        if predicted != expected:
            failures.append(case["id"])
    recall = tp / (tp + fn) if tp + fn else 0.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    return {
        "cases": len(cases), "true_positive": tp, "false_positive": fp,
        "false_negative": fn, "true_negative": tn,
        "recall": round(recall, 3), "precision": round(precision, 3),
        "failures": failures, "gate": "recall ≥ 0.90; precision ≥ 0.80",
        "passed": recall >= 0.9 and precision >= 0.8,
    }


def _fixture_evidence(text: str) -> list[Evidence]:
    stamp = datetime(2026, 9, 25, tzinfo=UTC)
    return [Evidence("fixture", text, "https://example.org/source", stamp)] if text else []


def _grounding_metrics() -> dict[str, Any]:
    cases = _rows("grounding_golden.jsonl")
    tp = fp = fn = 0
    failures: list[str] = []
    for case in cases:
        predicted = bool(verify(case["draft"], _fixture_evidence(case["evidence"]))["sentences"])
        expected = bool(case["supported"])
        tp += int(predicted and expected)
        fp += int(predicted and not expected)
        fn += int(not predicted and expected)
        if predicted != expected:
            failures.append(case["id"])
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    no_data_cases = _rows("nodata_adversarial.jsonl")
    no_data_failures = [
        case["id"] for case in no_data_cases
        if not verify(case["draft"], _fixture_evidence(case["evidence"]))["no_data"]
    ]
    return {
        "cases": len(cases), "f1": round(f1, 3), "precision": round(precision, 3),
        "recall": round(recall, 3), "failures": failures,
        "no_data": {"cases": len(no_data_cases), "violations": len(no_data_failures),
                     "failures": no_data_failures},
        "passed": f1 >= 0.85 and not no_data_failures,
    }


@lru_cache(maxsize=1)
def _scheme_metrics() -> dict[str, Any]:
    cases = _rows("schemes_golden.jsonl")
    corpus = _rows("schemes_corpus.jsonl")
    metrics = []
    weak: list[dict[str, Any]] = []
    for case in cases:
        ids = [item["id"] for item in rank_records(case["query"], corpus, 5)]
        expected = set(case["expected_ids"])
        found = [scheme_id for scheme_id in ids if scheme_id in expected]
        metrics.append({"locale": case["locale"], "precision": len(found) / 5,
                        "recall": len(found) / len(expected), "hit": bool(found)})
        if len(found) < min(4, len(expected)):
            weak.append({"id": case["id"], "top5": ids, "found": found})
    precision = sum(item["precision"] for item in metrics) / len(metrics)
    recall = sum(item["recall"] for item in metrics) / len(metrics)
    hit = sum(item["hit"] for item in metrics) / len(metrics)
    precision_en = sum(item["precision"] for item in metrics if item["locale"] == "en") / 20
    precision_te = sum(item["precision"] for item in metrics if item["locale"] == "te") / 20
    return {
        "cases": len(cases), "corpus_records": len(corpus),
        "precision_at_5": round(precision, 3), "recall_at_5": round(recall, 3),
        "hit_at_5": round(hit, 3), "precision_en": round(precision_en, 3),
        "precision_te": round(precision_te, 3), "weak_count": len(weak),
        "weak_cases": weak, "gate": "precision@5 ≥ 0.80", "passed": precision >= 0.8,
        "scope": "frozen public-source regression; not independent holdout validation",
    }


async def _live_scheme_metrics() -> dict[str, Any]:
    """Measure the current local index with the same labels as the snapshot gate."""
    global _LIVE_SCHEME_CACHE
    now = time.monotonic()
    if _LIVE_SCHEME_CACHE and now - _LIVE_SCHEME_CACHE[0] < 300:
        return _LIVE_SCHEME_CACHE[1]
    async with _LIVE_SCHEME_LOCK:
        now = time.monotonic()
        if _LIVE_SCHEME_CACHE and now - _LIVE_SCHEME_CACHE[0] < 300:
            return _LIVE_SCHEME_CACHE[1]
        try:
            cases = _rows("schemes_golden.jsonl")
            engine = create_async_engine(_to_asyncpg_url(settings.DATABASE_URL), pool_pre_ping=True)
            try:
                async with engine.connect() as conn:
                    records = list((await conn.execute(text("SELECT record FROM scheme_records"))).scalars())
            finally:
                await engine.dispose()
            total_found = total_recall = total_hits = 0.0
            by_locale = {"en": 0, "te": 0}
            counts = {"en": 0, "te": 0}
            for case in cases:
                ranked = rank_records(case["query"], records, 5, dedupe_duplicates=True)
                ids = [item["id"] for item in ranked]
                expected = set(case["expected_ids"])
                found = sum(item in expected for item in ids)
                total_found += found
                total_recall += found / max(1, len(expected))
                total_hits += bool(found)
                by_locale[case["locale"]] += found
                counts[case["locale"]] += 1
            precision = total_found / (5 * len(cases)) if cases else 0.0
            result = {
                "available": True,
                "cases": len(cases),
                "precision_at_5": round(precision, 3),
                "recall_at_5": round(total_recall / len(cases), 3) if cases else 0.0,
                "hit_at_5": round(total_hits / len(cases), 3) if cases else 0.0,
                "precision_en": round(by_locale["en"] / (5 * counts["en"]), 3) if counts["en"] else 0.0,
                "precision_te": round(by_locale["te"] / (5 * counts["te"]), 3) if counts["te"] else 0.0,
                "passed": precision >= 0.8,
                "scope": "current local index; lexical retrieval; same development labels, not independent holdout",
            }
        except Exception:  # noqa: BLE001 — missing DB/index must be reported as unavailable.
            result = {"available": False, "cases": 0, "passed": False,
                      "scope": "current local index could not be measured"}
        _LIVE_SCHEME_CACHE = (time.monotonic(), result)
        return result


def _import_graph() -> dict[str, Any]:
    core_dir = REPO_ROOT / "packages/core/daari_core"
    violations: dict[str, list[str]] = {}
    for path in sorted(core_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        hit = sorted(imported & FORBIDDEN_CORE_IMPORTS)
        if hit:
            violations[str(path.relative_to(core_dir))] = hit

    persona_dir = REPO_ROOT / "apps/api/daari/personas"
    persona_violations: list[str] = []
    for path in sorted(persona_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name in {
                "match", "roadmap", "eligibility", "assess", "scam", "schedule",
            }:
                persona_violations.append(path.name)
    return {
        "status": "green" if not violations and not persona_violations else "red",
        "core_package": "packages/core/daari_core",
        "forbidden_imports": violations,
        "persona_engine_violations": persona_violations,
        "shared_by": ["student", "rural"],
    }


def _match_ablations() -> dict[str, Any]:
    taxonomy = get_taxonomy()
    embeddings = get_embeddings()
    graph = build_graph(taxonomy, embeddings)
    role = taxonomy.roles["data_analyst"]
    candidate = Candidate(
        id="data_analyst", title=role.label_en, org="DAARI role taxonomy", location="Guntur",
        required_skills=role.required_skills, source="taxonomy-seed",
        source_url="https://example.org/taxonomy", fetched_at="taxonomy-seed",
    )
    # Use the role skill where graph edges measurably reduce the prerequisite
    # gap. A first-item fixture can accidentally make graph-on and graph-off
    # identical, which would hide a broken graph behind a passing >= check.
    graph_deltas = {
        skill: match(
            taxonomy, {skill: taxonomy.skills[skill].level}, [candidate],
            graph=graph, embeddings=embeddings,
        )[0].score - match(
            taxonomy, {skill: taxonomy.skills[skill].level}, [candidate],
            graph=None, embeddings=embeddings,
        )[0].score
        for skill in role.required_skills
    }
    held_skill = max(graph_deltas, key=lambda skill: (graph_deltas[skill], skill))
    held = {held_skill: taxonomy.skills[held_skill].level}
    full = match(taxonomy, held, [candidate], graph=graph, embeddings=embeddings)[0]
    graph_off = match(taxonomy, held, [candidate], graph=None, embeddings=embeddings)[0]
    vector_off = match(taxonomy, held, [candidate], graph=graph, embeddings=None)[0]
    return {
        "graph_on": full.score, "graph_off": graph_off.score,
        "vector_on": full.score, "vector_off": vector_off.score,
        "graph_delta": round(full.score - graph_off.score, 4),
        "vector_delta": round(full.score - vector_off.score, 4),
        "passed": full.score >= graph_off.score and full.score >= vector_off.score,
        "fixture": f"data_analyst role with held {held_skill}",
    }


def _roadmap_invariants() -> dict[str, Any]:
    taxonomy = get_taxonomy()
    goal = "data_analyst"
    held: dict[str, int] = {}
    before = compute(taxonomy, held, goal, {})
    learned = before.steps[0].skill if before.steps else next(iter(taxonomy.skills))
    after = compute(taxonomy, {learned: 5}, goal, {})
    demand = {before.steps[-1].skill: 2.0} if before.steps else {}
    shocked = compute(taxonomy, held, goal, demand)
    checks = {
        "learning_never_lengthens": after.total_hours <= before.total_hours,
        "market_shock_computes": shocked.goal == goal,
        "deterministic_replay": shocked == compute(taxonomy, held, goal, demand),
    }
    return {"checks": checks, "passed": all(checks.values()),
            "baseline_hours": before.total_hours, "after_learning_hours": after.total_hours}


def _flatten_catalog(value: dict[str, Any], flat: dict[str, str], prefix: str = "") -> None:
    for key, child in value.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(child, dict):
            _flatten_catalog(child, flat, path)
        else:
            flat[path] = str(child)


def _i18n() -> dict[str, Any]:
    catalogs = {}
    for locale in ("en", "te", "hi"):
        data = json.loads((REPO_ROOT / "apps/web/messages" / f"{locale}.json").read_text())
        flat: dict[str, str] = {}
        _flatten_catalog(data, flat)
        catalogs[locale] = flat
    reference = set(catalogs["en"])
    missing = {locale: sorted(reference - set(values)) for locale, values in catalogs.items()}
    empty = {locale: sorted(key for key, value in values.items() if not value.strip())
             for locale, values in catalogs.items()}
    return {"keys": len(reference), "missing": missing, "empty": empty,
            "passed": all(not values for values in missing.values()) and all(not values for values in empty.values())}


def _trace_event_complete(event: dict[str, Any]) -> bool:
    required = {"tool", "args", "ms", "provider", "status"}
    return (required <= event.keys() and isinstance(event["tool"], str)
            and isinstance(event["args"], dict) and isinstance(event["ms"], (int, float))
            and isinstance(event["provider"], str) and isinstance(event["status"], str))


def _constitution() -> list[dict[str, str]]:
    stamp = datetime(2026, 9, 25, tzinfo=UTC)
    source = Evidence("e1", "Scheme updated 2026-09-25. Benefit is ₹500.",
                      "https://example.org/scheme", stamp)
    supported = verify("Scheme updated 2026-09-25.", [source])
    unsupported_date = verify("Scheme updated 2026-09-26.", [source])
    unsupported_number = verify("Scheme updated 2026-09-25. Benefit is ₹900.", [source])
    unsupported_name = verify("Acme scheme updated 2026-09-25.", [source])
    telugu_source = Evidence("te1", "నైపుణ్య మార్గం", "https://example.org/te", stamp)
    telugu = verify("నైపుణ్య మార్గం", [telugu_source])
    notice = extract_notice(
        "Company: TCS\nRole: Analyst\nContact: Ravi Kumar 9876543210\n"
        "Email: person@example.test",
    )
    notice_text = json.dumps(notice, ensure_ascii=False)
    try:
        def unavailable(*args, **kwargs):
            raise RuntimeError("verifier unavailable")
        fail_closed = _safe_verify("Unsupported sentence.", [], "the linked sources", verifier=unavailable)
    except Exception:  # noqa: BLE001 — a failed probe must remain visibly incomplete.
        fail_closed = {"sentences": ["unsafe"]}

    checks = {
        "I": verify("Unsupported claim.", [])["no_data"],
        "II": bool(not supported["no_data"] and unsupported_date["no_data"]),
        "III": bool(unsupported_number["struck"]),
        "IV": bool(unsupported_name["struck"]),
        "V": bool(verify("No evidence.", [])["no_data"] and _grounding_metrics()["no_data"]["violations"] == 0),
        "VI": bool(supported["sentences"] and supported["sentences"][0]["citation_ids"] == ["e1"]),
        "VII": bool(_roadmap_invariants()["passed"] and _import_graph()["status"] == "green"),
        "VIII": bool(_i18n()["passed"] and telugu["sentences"] and not verify("వేరే వాస్తవం", [telugu_source])["sentences"]),
        "IX": bool(verify("Guaranteed placement.", [])["struck"]),
        "X": bool(_scam_metrics()["passed"]),
        "XI": not any(value in notice_text for value in ("Ravi", "9876543210", "person@example.test")),
        "XII": _trace_event_complete({"tool": "search_jobs", "args": {"query": "jobs"},
                                      "ms": 1.0, "provider": "fixture", "status": "ok"}),
        "XIII": bool(fail_closed["no_data"] and not fail_closed["sentences"]),
    }
    return [
        {"article": number, "title": title, "test": test,
         "status": "green" if checks.get(number, False) else "scaffold"}
        for number, title, test in CONSTITUTION_ARTICLES
    ]


def _git_sha() -> str:
    import subprocess

    try:
        result = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO_ROOT,
                                capture_output=True, text=True, timeout=5, check=True)
        return result.stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def _build_evidence() -> dict[str, Any]:
    p4 = _json("p4_report.json")
    p5 = _json("p5_report.json")
    p5_browser = _json("p5_browser_report.json")
    scheme = _scheme_metrics()
    scam = _scam_metrics()
    grounding = _grounding_metrics()
    i18n = _i18n()
    live_voice = voice_summary()
    return {
        "phase": "P6", "generated_at": datetime.now(UTC).isoformat(),
        "ci_sha": _git_sha(),
        "scope": "Development regressions and cached rehearsals; not field validation.",
        "shared_engine": {"counters": telemetry.snapshot(), "import_graph": _import_graph()},
        "roadmap": _roadmap_invariants(), "match_ablations": _match_ablations(),
        "scheme_retrieval": scheme, "scam": scam, "grounding": grounding,
        "interview": {"intel": p5["intel"], "feedback": p5["feedback"]}, "notice": p5["notices"],
        "voice": {"live_samples": live_voice, "cached_browser": p4["cached_browser"],
                  "cached_server": p4["cached_server"], "browser_checks": p5_browser["checks"]},
        "i18n": i18n, "constitution": _constitution(),
        "sources": {"scheme_corpus": len(_rows("schemes_corpus.jsonl")),
                    "scheme_golden": len(_rows("schemes_golden.jsonl")),
                    "interview_report": p5["intel"]["cases"]},
    }


@router.get("/evidence")
async def evidence() -> dict[str, Any]:
    result = _build_evidence()
    result["live_scheme_retrieval"] = await _live_scheme_metrics()
    return result
