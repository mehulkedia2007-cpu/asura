"""Persistent timestamped snapshots for live source responses."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import text

from daari.db import engine

REGISTRY = json.loads((Path(__file__).resolve().parents[3] / "data/sources.yaml").read_text())


def source(source_id: str) -> dict:
    entries = [*REGISTRY["jobs"], *REGISTRY["schemes"], REGISTRY["geo"]]
    return next(entry for entry in entries if entry["id"] == source_id)


async def read(key: str, max_age_hours: int | None = None) -> dict[str, Any] | None:
    async with engine.connect() as conn:
        row = (await conn.execute(text(
            "SELECT payload, content_hash, fetched_at FROM source_snapshots WHERE cache_key=:key"
        ), {"key": key})).mappings().first()
    if row is None:
        return None
    fresh = max_age_hours is None or datetime.now(UTC) - row["fetched_at"] < timedelta(hours=max_age_hours)
    return {"payload": row["payload"], "content_hash": row["content_hash"],
            "fetched_at": row["fetched_at"].isoformat(), "fresh": fresh}


async def write(key: str, kind: str, payload: Any) -> dict[str, Any]:
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    now = datetime.now(UTC)
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO source_snapshots(cache_key, kind, payload, content_hash, fetched_at)
            VALUES (:key, :kind, CAST(:payload AS jsonb), :hash, :now)
            ON CONFLICT(cache_key) DO UPDATE SET payload=EXCLUDED.payload,
                content_hash=EXCLUDED.content_hash, fetched_at=EXCLUDED.fetched_at
        """), {"key": key, "kind": kind, "payload": encoded, "hash": digest, "now": now})
    return {"payload": payload, "content_hash": digest, "fetched_at": now.isoformat(), "fresh": True}
