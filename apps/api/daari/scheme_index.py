"""Hybrid pgvector/tsvector index for stamped government scheme records."""

import hashlib
import json
import math
from datetime import datetime
from typing import Any

import httpx
from sqlalchemy import text

from daari.config import settings
from daari.db import engine
from daari.scheme_ranking import rank_records, tokens

EMBEDDING_KIND = "gemini-embedding-001:768"
_MODEL = "models/gemini-embedding-001"


async def embed(content: str, task_type: str) -> list[float] | None:
    if not settings.GEMINI_API_KEY or not content.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY},
                json={"content": {"parts": [{"text": content[:6000]}]},
                      "taskType": task_type, "outputDimensionality": 768},
            )
            response.raise_for_status()
            values = response.json()["embedding"]["values"]
        if len(values) != 768 or not all(isinstance(v, (int, float)) and math.isfinite(v) for v in values):
            return None
        return [float(v) for v in values]
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None


def _content(record: dict, locale: str) -> str:
    if locale == "te":
        return "\n".join(str(record.get(key) or "") for key in ("name_te", "summary_te")).strip()
    return "\n".join(str(record.get(key) or "") for key in
                     ("name_en", "summary_en", "benefit_text", "eligibility_text", "documents_text", "apply_text")).strip()[:6000]


async def upsert(record: dict, *, summary_only: bool = False) -> dict:
    scheme_id = record["id"]
    if summary_only:
        async with engine.connect() as conn:
            existing = (await conn.execute(text(
                "SELECT record FROM scheme_records WHERE scheme_id=:id"
            ), {"id": scheme_id})).first()
        if existing:
            previous = existing[0]
            additions = {key: record[key] for key in ("name_te", "summary_te", "summary_en", "tags")
                         if record.get(key) and not previous.get(key)}
            if additions:
                merged = {**previous, **additions}
                async with engine.begin() as conn:
                    await conn.execute(text("""
                        UPDATE scheme_records SET record=CAST(:record AS jsonb) WHERE scheme_id=:id
                    """), {"id": scheme_id, "record": json.dumps(merged, ensure_ascii=False)})
                    for locale in ("en", "te"):
                        content = _content(merged, locale)
                        if not content:
                            continue
                        digest = hashlib.sha256(content.encode()).hexdigest()
                        await conn.execute(text("""
                            INSERT INTO scheme_chunks(scheme_id, locale, content, content_hash)
                            VALUES (:id, :locale, :content, :hash)
                            ON CONFLICT(scheme_id, locale) DO UPDATE SET
                              content=EXCLUDED.content, content_hash=EXCLUDED.content_hash,
                              embedding=NULL, embedding_kind=NULL
                            WHERE scheme_chunks.content_hash != EXCLUDED.content_hash
                        """), {"id": scheme_id, "locale": locale, "content": content, "hash": digest})
            return {"scheme_id": scheme_id, "locales": [], "skipped": "already_indexed"}
    stored = {key: value for key, value in record.items() if key != "eligibility"}
    encoded = json.dumps(stored, ensure_ascii=False)
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO scheme_records(scheme_id, record, content_hash, fetched_at)
            VALUES (:id, CAST(:record AS jsonb), :hash, :fetched_at)
            ON CONFLICT(scheme_id) DO UPDATE SET record=EXCLUDED.record,
                content_hash=EXCLUDED.content_hash, fetched_at=EXCLUDED.fetched_at
            WHERE :summary_only = false
        """), {"id": scheme_id, "record": encoded, "hash": record["content_hash"],
                "fetched_at": datetime.fromisoformat(record["fetched_at"]),
                "summary_only": summary_only})
    indexed = []
    for locale in ("en", "te"):
        content = _content(record, locale)
        if not content:
            continue
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        async with engine.connect() as conn:
            existing = (await conn.execute(text("""
                SELECT content_hash, embedding_kind FROM scheme_chunks
                WHERE scheme_id=:id AND locale=:locale
            """), {"id": scheme_id, "locale": locale})).first()
        if existing and existing[0] == content_hash and existing[1] == EMBEDDING_KIND:
            indexed.append(locale)
            continue
        vector = None if summary_only else await embed(content, "RETRIEVAL_DOCUMENT")
        async with engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO scheme_chunks(scheme_id, locale, content, content_hash, embedding, embedding_kind)
                VALUES (:id, :locale, :content, :hash, CAST(:vector AS vector), :kind)
                ON CONFLICT(scheme_id, locale) DO UPDATE SET content=EXCLUDED.content,
                    content_hash=EXCLUDED.content_hash, embedding=EXCLUDED.embedding,
                    embedding_kind=EXCLUDED.embedding_kind
            """), {"id": scheme_id, "locale": locale, "content": content,
                    "hash": content_hash, "vector": json.dumps(vector) if vector else None,
                    "kind": EMBEDDING_KIND if vector else None})
        indexed.append(locale)
    return {"scheme_id": scheme_id, "locales": indexed}


async def embed_missing(limit: int = 32) -> dict:
    """Fill summary vectors in small batches outside the user-facing request."""
    if not settings.GEMINI_API_KEY:
        return {"updated": 0, "error": "no_api_key"}
    async with engine.connect() as conn:
        rows = (await conn.execute(text("""
            SELECT scheme_id, locale, content FROM scheme_chunks
            WHERE embedding IS NULL AND length(content) > 0
            ORDER BY scheme_id, locale LIMIT :limit
        """), {"limit": max(1, min(limit, 100))})).all()
    if not rows:
        return {"updated": 0, "error": None}
    body = {"requests": [{"model": _MODEL,
                          "content": {"parts": [{"text": row[2][:6000]}]},
                          "taskType": "RETRIEVAL_DOCUMENT", "outputDimensionality": 768}
                         for row in rows]}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents",
                headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=body,
            )
            response.raise_for_status()
            vectors = response.json()["embeddings"]
        if len(vectors) != len(rows):
            raise ValueError("embedding count mismatch")
        updated = 0
        async with engine.begin() as conn:
            for row, vector in zip(rows, vectors, strict=True):
                values = vector.get("values")
                if not isinstance(values, list) or len(values) != 768 or not all(
                    isinstance(value, (int, float)) and math.isfinite(value) for value in values
                ):
                    continue
                await conn.execute(text("""
                    UPDATE scheme_chunks SET embedding=CAST(:vector AS vector), embedding_kind=:kind
                    WHERE scheme_id=:id AND locale=:locale AND embedding IS NULL
                """), {"vector": json.dumps(values), "kind": EMBEDDING_KIND,
                        "id": row[0], "locale": row[1]})
                updated += 1
        return {"updated": updated, "error": None}
    except httpx.HTTPStatusError as exc:
        return {"updated": 0, "error": f"http_{exc.response.status_code}"}
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return {"updated": 0, "error": "embedding_failed"}


async def retrieve(query: str, limit: int = 8, *, use_embeddings: bool = True) -> dict[str, Any]:
    if not query.strip() or limit <= 0:
        return {"records": [], "kind": "lexical", "embedding_kind": None}
    vector = await embed(" ".join([query, *tokens(query)]), "RETRIEVAL_QUERY") if use_embeddings else None
    async with engine.connect() as conn:
        # The AP/central catalog is small. Rank all source purposes rather than
        # irreversibly truncating candidates on generic OR matches at top 20.
        records = list((await conn.execute(text("SELECT record FROM scheme_records"))).scalars())
        prior = {}
        if vector is not None:
            semantic = (await conn.execute(text("""
                SELECT scheme_id, MIN(embedding <=> CAST(:vector AS vector)) AS distance
                FROM scheme_chunks WHERE embedding IS NOT NULL AND embedding_kind=:kind
                GROUP BY scheme_id ORDER BY distance, scheme_id LIMIT 20
            """), {"vector": json.dumps(vector), "kind": EMBEDDING_KIND})).all()
            prior = {scheme_id: 1 / (60 + rank) for rank, (scheme_id, _) in enumerate(semantic, 1)}
        ranked = rank_records(query, records, limit, prior, dedupe_duplicates=True)
    return {"records": [{**r, "source": r.get("source") or "myScheme"} for r in ranked],
            "kind": "hybrid" if vector is not None else "lexical",
            "embedding_kind": EMBEDDING_KIND if vector is not None else None}


async def coverage() -> dict[str, Any]:
    """Counts from indexed source records, including the newest refresh stamp."""
    async with engine.connect() as conn:
        rows = (await conn.execute(text("SELECT record, fetched_at FROM scheme_records"))).all()
        checks = (await conn.execute(text("""
            SELECT source_id, status, error, links, checked_at FROM source_checks ORDER BY source_id
        """))).mappings().all()
    records = [row[0] for row in rows]
    return {
        "indexed": len(records),
        "ap": sum(record.get("state") == "Andhra Pradesh" for record in records),
        "central": sum("central" in str(record.get("level", "")).casefold() for record in records),
        "other": sum(record.get("state") != "Andhra Pradesh" and
                     "central" not in str(record.get("level", "")).casefold() for record in records),
        "latest_refresh": max((row[1] for row in rows), default=None),
        "sources": [dict(row) for row in checks],
    }
