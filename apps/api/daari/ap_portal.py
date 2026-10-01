"""AP MSME public directory adapter; summary-only records remain eligibility unknown."""

import asyncio
import hashlib
import re
import time
from urllib.parse import urljoin, urlparse

import httpx

from daari.source_cache import read, source, write

_ENTRY = re.compile(r'/assets/index-[\w-]+\.js')
_ASSET = re.compile(r'/?assets/schemes-[\w-]+\.js')
_CARD = re.compile(
    r'id:`(?P<id>[A-Za-z0-9_-]+)`,name:`(?P<name>[^`]+)`,'
    r'.{0,350}?benefitSummary:`(?P<summary>[^`]+)`,'
    r'.{0,250}?tags:\[(?P<tags>[^]]*)\],status:`active`'
)
_lock = asyncio.Lock()
_last_request = 0.0


async def _fetch(client: httpx.AsyncClient, key: str, url: str, refresh: bool) -> tuple[dict | None, str | None]:
    cached = await read(key, 6)
    if cached and cached["fresh"] and not refresh:
        return cached, None
    try:
        global _last_request
        async with _lock:
            await asyncio.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
            response = await client.get(url)
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("oversized page")
        return await write(key, "schemes", {"html": response.text}), None
    except (httpx.HTTPError, ValueError) as exc:
        return cached, type(exc).__name__


async def search(client: httpx.AsyncClient, query: str, refresh: bool) -> tuple[list[dict], list[str]]:
    base = source("ap_msme")["url_template"]
    page, error = await _fetch(client, "ap-msme:page", base, refresh)
    errors = [error] if error else []
    if not page:
        return [], errors
    entry_match = _ENTRY.search(page["payload"]["html"])
    if not entry_match:
        return [], [*errors, "directory_entry_missing"]
    entry_url = urljoin(base, entry_match.group())
    entry, error = await _fetch(client, f"ap-msme:entry:{entry_match.group()}", entry_url, refresh)
    if error:
        errors.append(error)
    if not entry:
        return [], errors
    asset_match = _ASSET.search(entry["payload"]["html"])
    if not asset_match:
        return [], [*errors, "directory_asset_missing"]
    asset_url = urljoin(base, asset_match.group())
    if urlparse(asset_url).hostname != "apmsmeone.ap.gov.in":
        return [], [*errors, "directory_asset_host"]
    asset, error = await _fetch(client, f"ap-msme:asset:{asset_match.group()}", asset_url, refresh)
    if error:
        errors.append(error)
    if not asset:
        return [], errors
    found = []
    for match in _CARD.finditer(asset["payload"]["html"]):
        name, summary = match["name"], match["summary"]
        if query.casefold() not in f"{name} {summary}".casefold():
            continue
        tags = match["tags"].casefold()
        content_hash = hashlib.sha256(f"{name}\n{summary}".encode()).hexdigest()
        found.append({
            "id": f"ap-msme:{match['id']}", "name_en": name, "name_te": None,
            "summary_te": None, "level": "Andhra Pradesh directory",
            "state": "Andhra Pradesh" if "ap-state" in tags else None,
            "ministry_or_dept": "AP MSME", "benefit_text": summary,
            "eligibility_text": "", "documents_text": "", "apply_text": "",
            "apply_steps": [], "application_channels": [],
            "url": urljoin(base, f"/schemes/{match['id']}"),
            "fetched_at": asset["fetched_at"], "as_of": None,
            "content_hash": content_hash, "rules": {"all": [], "any": []},
            "rules_complete": False, "stale": not asset["fresh"],
            "source": "AP MSME directory",
        })
    return found, errors
