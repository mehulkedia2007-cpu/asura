"""Polite, bounded allow-list fetches. A failed refresh retains the previous date."""

import asyncio
import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from daari.intel.extract_questions import extract

_LOCK = asyncio.Lock()


def allowed_url(url: str) -> bool:
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError:
        return False
    return (parsed.scheme == "https" and port in (None, 443) and not parsed.username
            and not parsed.password and not parsed.query and not parsed.fragment and (
                parsed.hostname == "www.geeksforgeeks.org" and parsed.path.startswith("/interview-experiences/")
                or parsed.hostname == "raw.githubusercontent.com" and parsed.path.endswith((".md", ".txt"))))


async def fetch(url: str) -> str:
    if not allowed_url(url):
        raise ValueError("source not allow-listed")
    async with _LOCK, httpx.AsyncClient(timeout=15, follow_redirects=False,
                                       headers={"User-Agent": "DAARI/0.1 (https://github.com/dmrk22/asura)"}) as client:
        host = urlparse(url).netloc
        robots_response = await client.get(f"https://{host}/robots.txt")
        if robots_response.status_code == 200:
            robots = RobotFileParser()
            robots.parse(robots_response.text.splitlines())
            if not robots.can_fetch("DAARI", url):
                raise ValueError("robots disallows source")
        elif robots_response.status_code != 404:
            raise ValueError("robots unavailable")
        await asyncio.sleep(1)
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > 2_000_000:
                    raise ValueError("source too large")
        await asyncio.sleep(1)
    html = chunks.decode("utf-8", errors="replace")
    html = re.sub(r"<(script|style)\b[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    plain = unescape(re.sub(r"<[^>]+>", "\n", html))
    # Drop author/contact lines before extraction or provider caching.
    lines = [line.strip() for line in plain.splitlines() if line.strip() and not re.search(
        r"@|\b(author|contribut|written by|my name|contact|phone)\b|\d[\d\s-]{8,}\d", line, re.IGNORECASE)]
    return "\n".join(lines)


async def refresh(company: str, role: str) -> dict:
    from daari.intel.corpus import prune_source, resolve, seed, upsert
    from daari.taxonomy_loader import get_taxonomy
    company, role = resolve(company, role)
    sources = {r["source_url"]: r for r in seed() if r["company"] == company and r["role"] == role}
    errors, count = [], 0
    for url, source in sources.items():
        try:
            content = await fetch(url)
            metadata = {k: source[k] for k in ("company", "role", "year", "as_of", "date_kind", "source_url")}
            metadata["fetched_at"] = datetime.now(UTC).isoformat()
            reviewed = [r for r in seed() if r["source_url"] == url]
            rows = [{**row, "fetched_at": metadata["fetched_at"]} for row in reviewed if row["source_span"] in content]
            budget = max(0, 25-sum(len(row["source_span"].split()) for row in reviewed))
            rows += await extract(content, metadata, list(get_taxonomy().skills), word_budget=budget)
            if rows:
                retained = {row["id"]: row for row in reviewed}
                retained.update({row["id"]: row for row in rows})
                await upsert(list(retained.values()))
                await prune_source(url, list(retained))
                count += len(rows)
            else:
                errors.append({"source_url": url, "status": "no_verified_questions"})
        except Exception as exc:  # noqa: BLE001 — fail closed and show sanitized source status.
            errors.append({"source_url": url, "status": type(exc).__name__})
    return {"updated_items": count, "checked_sources": len(sources), "errors": errors}
