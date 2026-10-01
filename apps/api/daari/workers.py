"""Six-hour refresh of representative public live-source snapshots."""

import asyncio
from typing import ClassVar

from arq import cron
from arq.connections import RedisSettings

from daari.config import settings
from daari.leads import search as search_leads
from daari.portal_sources import probe_all
from daari.scheme_index import embed_missing
from daari.schemes import ingest_summaries
from daari.schemes import search as search_schemes


async def refresh_sources(ctx: dict) -> dict:
    del ctx
    results: dict[str, object] = {}
    for query in ("skill", "livelihood", "apprenticeship"):
        try:
            response = await search_schemes(query, {"state": "Andhra Pradesh"}, refresh=True)
            results[f"schemes:{query}"] = {"indexed": len(response["schemes"]),
                                            "errors": response["source_errors"]}
        except Exception as exc:  # noqa: BLE001 — isolate one source from the rest
            results[f"schemes:{query}"] = type(exc).__name__
    for query in ("loan", "rural", "entrepreneurship", "disability", "digital",
                  "handicraft", "PMKVY", "vocational"):
        try:
            results[f"scheme_index:{query}"] = await ingest_summaries(query, refresh=True)
        except Exception as exc:  # noqa: BLE001 — preserve the other source refreshes
            results[f"scheme_index:{query}"] = type(exc).__name__
    for query in ("technician", "data analyst"):
        try:
            response = await search_leads(query, "Guntur, Andhra Pradesh", {}, refresh=True)
            results[f"leads:{query}"] = {"found": len(response["leads"]),
                                          "errors": response["errors"]}
        except Exception as exc:  # noqa: BLE001 — isolate one source from the rest
            results[f"leads:{query}"] = type(exc).__name__
    results["government_portals"] = await probe_all(refresh=True)
    embedded = 0
    embedding_error = None
    for _ in range(20):
        batch = await embed_missing(5)
        embedded += batch["updated"]
        embedding_error = batch["error"]
        if embedding_error or batch["updated"] == 0:
            break
        await asyncio.sleep(6)
    results["scheme_embeddings"] = {"updated": embedded, "error": embedding_error}
    return results


class WorkerSettings:
    functions: ClassVar[list] = [refresh_sources]
    cron_jobs: ClassVar[list] = [cron(refresh_sources, hour={0, 6, 12, 18}, minute=0)]
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    job_timeout = 900
