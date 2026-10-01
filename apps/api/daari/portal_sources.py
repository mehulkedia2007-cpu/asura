"""Monitor the registered public government portals without inferring eligibility."""

import asyncio
import re
import time
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from sqlalchemy import text

from daari.db import engine
from daari.source_cache import REGISTRY, read, write

_USER_AGENT = "DAARI/0.1 (government scheme source monitor; https://github.com/dmrk22/asura)"
_lock = asyncio.Lock()
_last_request = 0.0


class _Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._label = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._label = ""

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._label += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._href:
            self.links.append((" ".join(self._label.split()), self._href))
            self._href = None


def extract_links(html: str, base: str) -> list[dict]:
    parser = _Links()
    parser.feed(html)
    host = urlparse(base).hostname
    found = []
    for label, href in parser.links:
        url = urljoin(base, href)
        parsed = urlparse(url)
        if (parsed.scheme == "https" and parsed.hostname == host and len(label) >= 8 and
                re.search(r"scheme|service|training|skill|loan|pension|yojana", label + " " + parsed.path,
                          re.IGNORECASE)):
            found.append({"label": label[:160], "url": url})
    return found[:100]


async def _save_check(result: dict) -> dict:
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO source_checks(source_id, status, error, links, checked_at)
            VALUES (:id, :status, :error, :links, :checked_at)
            ON CONFLICT(source_id) DO UPDATE SET status=EXCLUDED.status, error=EXCLUDED.error,
                links=EXCLUDED.links, checked_at=EXCLUDED.checked_at
        """), {"id": result["id"], "status": result["status"], "error": result.get("error"),
                "links": result["links"], "checked_at": datetime.now(UTC)})
    return result


async def probe(source: dict, client: httpx.AsyncClient, refresh: bool = False) -> dict:
    global _last_request
    key = f"portal:{source['id']}"
    cached = await read(key, source["refresh_hours"])
    if cached and cached["fresh"] and not refresh:
        return await _save_check({"id": source["id"], "status": "ok", "fetched_at": cached["fetched_at"],
                                  "links": len(cached["payload"].get("links", []))})
    try:
        async with _lock:
            await asyncio.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
            _last_request = time.monotonic()
            response = await client.get(source["url_template"], headers={"User-Agent": _USER_AGENT})
        response.raise_for_status()
        if len(response.content) > 2_000_000:
            raise ValueError("oversized page")
        links = extract_links(response.text, str(response.url))
        snapshot = await write(key, "portal", {"source_url": str(response.url), "links": links})
        return await _save_check({"id": source["id"], "status": "ok",
                                  "fetched_at": snapshot["fetched_at"], "links": len(links)})
    except (httpx.HTTPError, ValueError) as exc:
        return await _save_check({"id": source["id"],
                                  "status": "stale" if cached else "unavailable",
                                  "error": type(exc).__name__,
                                  "fetched_at": cached["fetched_at"] if cached else None,
                                  "links": len(cached["payload"].get("links", [])) if cached else 0})


async def probe_all(refresh: bool = False) -> list[dict]:
    sources = [entry for entry in REGISTRY["schemes"] if entry["kind"] == "html_list"]
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        return [await probe(entry, client, refresh) for entry in sources]
