"""Polite, cached access to the public myScheme search and detail endpoints."""

import asyncio
import time
from typing import Any

import httpx

from daari.source_cache import read, source, write

HEADERS = {
    "x-api-key": source("myscheme_ap")["public_api_key"],
    "Referer": "https://www.myscheme.gov.in/",
    "User-Agent": "Mozilla/5.0 (compatible; DAARI/0.1; https://github.com/dmrk22/asura)",
}
DETAIL_URL = "https://api.myscheme.gov.in/schemes/v6/public/schemes"
_lock = asyncio.Lock()
_last_request = 0.0


async def _get(client: httpx.AsyncClient, url: str, params: dict | None = None) -> dict:
    global _last_request
    async with _lock:
        await asyncio.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        response = await client.get(url, params=params, headers=HEADERS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("statusCode") != 200:
        raise ValueError("myScheme returned an invalid response")
    return payload


async def cached_get(client: httpx.AsyncClient, key: str, url: str,
                     params: dict | None = None, refresh: bool = False) -> tuple[dict | None, str | None]:
    cached = await read(key, 6)
    if cached and cached["fresh"] and not refresh:
        return cached, None
    try:
        payload = await _get(client, url, params)
        return await write(key, "schemes", payload), None
    except (httpx.HTTPError, ValueError) as exc:
        return cached, type(exc).__name__


async def search_pages(client: httpx.AsyncClient, query: str, refresh: bool,
                       locale: str = "en") -> tuple[list[tuple[dict, str]], list[str], bool]:
    """Page up to 1,000 matches; return raw records, source stamps and truncation."""
    from daari.schemes import _items

    results: list[tuple[dict, str]] = []
    errors: list[str] = []
    total = 0
    for offset in range(0, 1000, 100):
        cache, error = await cached_get(client, f"myscheme:{locale}:{query.casefold()}:{offset}",
            source("myscheme_ap")["url_template"],
            {"lang": locale, "q": "[]", "keyword": query, "sort": "", "from": offset, "size": 100},
            refresh)
        if error:
            errors.append(error)
        if not cache:
            break
        payload = cache["payload"]
        items = _items(payload)
        results.extend((item, cache["fetched_at"]) for item in items)
        summary = payload.get("data", {}).get("summary", {})
        total = int(summary.get("total") or len(results))
        if not items or len(results) >= total:
            break
    return results, errors, total > len(results)


async def detail(client: httpx.AsyncClient, slug: str, locale: str,
                 refresh: bool) -> tuple[dict[str, Any] | None, list[str]]:
    """Fetch English detail plus documents, channels and optional Telugu record."""
    errors: list[str] = []
    base, error = await cached_get(client, f"myscheme-detail:{slug}:en", DETAIL_URL,
                                   {"slug": slug, "lang": "en"}, refresh)
    if error:
        errors.append(error)
    if not base or not isinstance(base["payload"].get("data"), dict):
        return None, errors
    data = base["payload"]["data"]
    scheme_id = data.get("_id")
    if not isinstance(scheme_id, str) or not scheme_id.isalnum():
        return None, [*errors, "missing_scheme_id"]
    documents, error = await cached_get(client, f"myscheme-documents:{slug}",
        f"{DETAIL_URL}/{scheme_id}/documents", {"lang": "en"}, refresh)
    if error:
        errors.append(error)
    channels, error = await cached_get(client, f"myscheme-channels:{slug}",
        f"{DETAIL_URL}/{scheme_id}/applicationchannel", None, refresh)
    if error:
        errors.append(error)
    telugu = None
    if locale == "te":
        telugu, error = await cached_get(client, f"myscheme-detail:{slug}:te", DETAIL_URL,
                                          {"slug": slug, "lang": "te"}, refresh)
        if error:
            errors.append(error)
    te_data = ((telugu or {}).get("payload") or {}).get("data") or {}
    doc_data = ((documents or {}).get("payload") or {}).get("data") or {}
    channel_data = ((channels or {}).get("payload") or {}).get("data") or {}
    return {
        "en": data.get("en") or {},
        "te": te_data.get("te") or {},
        "documents": doc_data.get("en") or {},
        "channels": channel_data.get("applicationChannel") or [],
        "fetched_at": base["fetched_at"],
        "stale": not base["fresh"],
    }, errors
