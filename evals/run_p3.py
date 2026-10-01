"""Run P3 safety and retrieval gates; --snapshot needs no services/providers."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from daari_core.scam import score

from daari.grounding.verifier import Evidence, verify
from daari.scheme_index import retrieve
from daari.scheme_ranking import rank_records

HERE = Path(__file__).resolve().parent
STAMP = datetime(2026, 9, 25, tzinfo=UTC)


def rows(name: str) -> list[dict]:
    return [json.loads(line) for line in (HERE / name).read_text().splitlines() if line.strip()]


def measure_scam() -> dict:
    cases = rows("scam_golden.jsonl")
    if len(cases) != 30:
        raise ValueError("scam golden set must contain 30 cases")
    tp = fp = fn = 0
    failures = []
    for case in cases:
        result = score(case["description"], case["org"], case.get("contact", ""),
                       case.get("pay"), case.get("median"))
        predicted = result.score >= 0.5
        expected = case["label"]
        tp += bool(predicted and expected)
        fp += bool(predicted and not expected)
        fn += bool(not predicted and expected)
        if predicted != expected:
            failures.append(case["id"])
    recall = tp / (tp + fn) if tp + fn else 0
    precision = tp / (tp + fp) if tp + fp else 0
    return {"cases": len(cases), "recall": round(recall, 3),
            "precision": round(precision, 3), "failures": failures}


def _evidence(text: str) -> list[Evidence]:
    return [Evidence("fixture", text, "https://example.org/source", STAMP)] if text else []


def measure_grounding() -> dict:
    cases = rows("grounding_golden.jsonl")
    if len(cases) < 20:
        raise ValueError("grounding golden set must contain at least 20 cases")
    tp = fp = fn = 0
    failures = []
    for case in cases:
        response = verify(case["draft"], _evidence(case["evidence"]))
        predicted = bool(response["sentences"])
        expected = case["supported"]
        tp += bool(predicted and expected)
        fp += bool(predicted and not expected)
        fn += bool(not predicted and expected)
        if predicted != expected:
            failures.append(case["id"])
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return {"cases": len(cases), "f1": round(f1, 3), "failures": failures}


def measure_nodata() -> dict:
    cases = rows("nodata_adversarial.jsonl")
    if len(cases) < 10:
        raise ValueError("no-data set must contain at least 10 cases")
    failures = [case["id"] for case in cases
                if not verify(case["draft"], _evidence(case["evidence"]))["no_data"]]
    return {"cases": len(cases), "violations": len(failures), "failures": failures}


async def measure_schemes(*, snapshot: bool = False, lexical: bool = False) -> dict:
    """Evaluate the local indexed corpus; provider query embeddings may be used."""
    cases = rows("schemes_golden.jsonl")
    if len(cases) != 40 or sum(case["locale"] == "te" for case in cases) != 20:
        raise ValueError("scheme set must contain 40 cases, half in Telugu")
    corpus = rows("schemes_corpus.jsonl") if snapshot else None
    metrics = []
    failures = []
    for case in cases:
        result = ({"records": rank_records(case["query"], corpus, 5)} if corpus is not None
                  else await retrieve(case["query"], 5, use_embeddings=not lexical))
        ids = [item["id"] for item in result["records"]]
        expected = set(case["expected_ids"])
        found = [scheme_id for scheme_id in ids if scheme_id in expected]
        metrics.append({"locale": case["locale"], "precision": len(found) / 5,
                        "recall": len(found) / len(expected), "hit": bool(found)})
        if len(found) < min(4, len(expected)):
            failures.append({"id": case["id"], "found": found, "top5": ids})
    return {"cases": len(cases), "mode": "snapshot" if snapshot else "lexical" if lexical else "hybrid",
            "precision_ceiling": sum(min(5, len(set(c["expected_ids"]))) for c in cases) / (5 * len(cases)),
            "precision_at_5": round(sum(item["precision"] for item in metrics) / 40, 3),
            "recall_at_5": round(sum(item["recall"] for item in metrics) / 40, 3),
            "hit_at_5": round(sum(item["hit"] for item in metrics) / 40, 3),
            "precision_en": round(sum(item["precision"] for item in metrics if item["locale"] == "en") / 20, 3),
            "precision_te": round(sum(item["precision"] for item in metrics if item["locale"] == "te") / 20, 3),
            "weak_count": len(failures), "weak_cases": failures}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--schemes", action="store_true", help="also evaluate the local live scheme index")
    parser.add_argument("--snapshot", action="store_true", help="evaluate the frozen public-source corpus without network")
    parser.add_argument("--lexical", action="store_true", help="disable provider embeddings for the live index")
    args = parser.parse_args()
    results = {"scam": measure_scam(), "grounding": measure_grounding(),
               "nodata": measure_nodata()}
    if args.schemes or args.snapshot:
        results["schemes"] = asyncio.run(measure_schemes(snapshot=args.snapshot, lexical=args.lexical))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    return int(results["scam"]["recall"] < 0.9 or results["scam"]["precision"] < 0.8 or
               results["grounding"]["f1"] < 0.85 or results["nodata"]["violations"] != 0 or
               ((args.schemes or args.snapshot) and results["schemes"]["precision_at_5"] < 0.8))


if __name__ == "__main__":
    raise SystemExit(main())
