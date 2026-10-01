"""Validated frozen fallback and filtered PostgreSQL corpus. No author fields."""

import hashlib
import json
from collections import Counter
from datetime import datetime
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from daari.config import REPO_ROOT
from daari.db import engine


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    company: str
    role: str
    text: str = Field(min_length=3, max_length=500)
    text_te: str | None = None
    text_hi: str | None = None
    round: str
    topic: str
    skill_ids: list[str]
    year: int = Field(ge=2000, le=2100)
    as_of: str
    date_kind: Literal["source_updated", "reported_date"] = "source_updated"
    source_url: str
    fetched_at: datetime
    source_span: str = Field(min_length=2, max_length=500)
    wording: Literal["adapted_from_report", "verbatim"] = "verbatim"
    similar: list[dict] = Field(default_factory=list)

    @field_validator("source_url")
    @classmethod
    def allowed_source(cls, value: str) -> str:
        from daari.intel.fetchers import allowed_url
        if not allowed_url(value):
            raise ValueError("source is not allow-listed")
        return value

    @field_validator("fetched_at")
    @classmethod
    def timezone_required(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("fetch timestamp needs timezone")
        return value


@lru_cache
def companies() -> list[dict]:
    return json.loads((REPO_ROOT / "data/companies.yaml").read_text())["companies"]


def resolve(company: str, role: str) -> tuple[str, str]:
    folded = company.strip().casefold()
    record = next((c for c in companies() if folded in [c["id"].casefold(), c["name"].casefold(),
                                                      *(a.casefold() for a in c["aliases"])]), None)
    return (record["id"], record["role_aliases"].get(role.casefold().strip(), role.strip())) if record else (folded, role.strip())


@lru_cache
def seed() -> list[dict]:
    return [Question.model_validate(row).model_dump(mode="json") for row in
            json.loads((REPO_ROOT / "data/interview/questions.json").read_text())]


def stats(rows: list[dict]) -> dict:
    sources = {row["source_url"] for row in rows}
    sources.update(similar["source_url"] for row in rows for similar in row.get("similar", []))
    years = [row["year"] for row in rows]
    return {"items": len(rows), "sources": len(sources),
            "coverage": "none" if not rows else "thin" if len(rows) < 5 or len(sources) < 2 else "available",
            "year_min": min(years) if years else None, "year_max": max(years) if years else None,
            "newest_evidence_date": max((r["as_of"] for r in rows), default=None),
            "round_mix": dict(Counter(r["round"] for r in rows)),
            "top_topics": dict(Counter(s for r in rows for s in r["skill_ids"]).most_common())}


def select(rows: list[dict], company: str, role: str, query: str = "", round_name: str = "",
           year: int | None = None, limit: int = 30) -> dict:
    company, role = resolve(company, role)
    matched = [r for r in rows if r["company"] == company and r["role"].casefold() == role.casefold()]
    coverage = stats(matched)
    from daari.intel.extract_questions import feature_vector
    from daari.taxonomy_loader import get_taxonomy
    normalized = query.casefold()
    for node in get_taxonomy().skills.values():
        if query and any(label and label.casefold() in normalized for label in (node.label_te, node.label_hi)):
            normalized += " " + node.label_en.casefold() + " " + node.id
    terms = normalized.split()
    query_vector = feature_vector(normalized)
    filtered = [r for r in matched if (not round_name or r["round"] == round_name)
                and (year is None or r["year"] == year)]
    def score(row: dict) -> tuple:
        haystack = (row["text"] + " " + row["topic"] + " " + " ".join(row["skill_ids"])).casefold()
        cosine = sum(a*b for a,b in zip(query_vector, feature_vector(haystack), strict=True))
        return (-sum(term in haystack for term in terms), -cosine, -row["year"], row["id"])
    if terms:
        filtered = [r for r in filtered if -score(r)[0] > 0]
    filtered.sort(key=score)
    return {"company": company, "role": role, "stats": coverage,
            "questions": [{**r, "coverage": coverage["coverage"], "kind": "reported"} for r in filtered[:limit]],
            "matched_items": len(filtered), "searched": {"company": company, "role": role, "query": query},
            "next_step": "practice_bank" if not filtered else "read_sources",
            "nearest_roles": sorted({r["role"] for r in rows if r["company"] == company and r["role"].casefold() != role.casefold()})}


async def search(company: str, role: str, query: str = "", round_name: str = "",
                 year: int | None = None) -> dict:
    from daari.intel.extract_questions import dedupe, feature_vector
    origin = "postgres"
    try:
        async with engine.connect() as conn:
            company_id, _ = resolve(company, role)
            raw = (await conn.execute(text("SELECT payload FROM interview_questions WHERE company=:company ORDER BY embedding <=> CAST(:query AS vector)"),
                                      {"company": company_id, "query": str(feature_vector(query or role))})).scalars().all()
        rows = [Question.model_validate(r).model_dump(mode="json") for r in raw]
        # The reviewed snapshot is always available, including before local seeding.
        merged = {r["id"]: r for r in seed()}
        for row in rows:
            reviewed = merged.get(row["id"], {})
            if reviewed.get("source_span") == row["source_span"] and reviewed.get("text") == row["text"]:
                row = {**row, "text_te": row.get("text_te") or reviewed.get("text_te"),
                       "text_hi": row.get("text_hi") or reviewed.get("text_hi")}
            merged[row["id"]] = row
        rows = list(merged.values())
    except Exception:  # noqa: BLE001 — database outage retains stamped evidence, never fabricated data.
        rows, origin = seed(), "reviewed_snapshot"
    return {**select(dedupe(rows), company, role, query, round_name, year), "storage": origin}


async def upsert(rows: list[dict]) -> None:
    from daari.intel.extract_questions import feature_vector
    async with engine.begin() as conn:
        for raw in rows:
            row = Question.model_validate(raw).model_dump(mode="json")
            vector = feature_vector(row["text"])
            await conn.execute(text("""
                INSERT INTO interview_questions(id, company, role, payload, embedding, content_hash)
                VALUES (:id, :company, :role, CAST(:payload AS jsonb), CAST(:vector AS vector), :hash)
                ON CONFLICT(id) DO UPDATE SET payload=EXCLUDED.payload, embedding=EXCLUDED.embedding,
                    content_hash=EXCLUDED.content_hash
            """), {"id": row["id"], "company": row["company"], "role": row["role"],
                   "payload": json.dumps(row), "vector": str(vector),
                   "hash": hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()})


async def prune_source(source_url: str, retained_ids: list[str]) -> None:
    """Replace the selected source's excerpt cache, keeping its reviewed quota bounded."""
    async with engine.begin() as conn:
        await conn.execute(text("DELETE FROM interview_questions WHERE payload->>'source_url'=:url AND NOT(id=ANY(:ids))"),
                           {"url": source_url, "ids": retained_ids})
