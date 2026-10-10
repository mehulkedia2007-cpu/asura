"""Official AP recruitment notices, never assumed to be open vacancies."""
import asyncio
import hashlib
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx
from daari_core.scam import score as scam_score

from daari.geocode import lookup_ap
from daari.job_filters import fresh, relevant
from daari.portal_sources import _Links
from daari.source_cache import REGISTRY, read, write


class Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows: list[list[str]] = []
        self.cells: list[str] | None = None
        self.cell: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.cells = []
        elif tag == "td" and self.cells is not None:
            self.cell = []

    def handle_data(self, data):
        if self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if tag == "td" and self.cell is not None and self.cells is not None:
            self.cells.append(" ".join(" ".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.cells is not None:
            self.rows.append(self.cells)
            self.cells = self.cell = None


def parse(html: str, entry: dict, stamp: str, query: str) -> list[dict]:
    rows = Rows()
    rows.feed(html)
    links = _Links()
    links.feed(html)
    candidates = []
    if entry["parser"] == "aphc_recruitment":
        candidates = [(row[2], row[0], entry["url_template"]) for row in rows.rows if len(row) >= 3]
    elif entry["parser"] == "district_recruitment":
        for row in rows.rows:
            if len(row) < 4:
                continue
            try:
                closes = datetime.strptime(row[3], "%d/%m/%Y").replace(tzinfo=UTC).date()
                if closes < datetime.now(UTC).date():
                    continue
            except ValueError:
                continue
            candidates.append((row[0], row[2], entry["url_template"]))
    else:
        for label, href in links.links:
            url = urljoin(entry["url_template"], href)
            host = urlparse(url).hostname or ""
            if host in {"psc.ap.gov.in", urlparse(entry["url_template"]).hostname} or host.endswith(".psc.ap.gov.in"):
                date = re.search(r"\b\d{2}[./-]\d{2}[./-]\d{4}\b", label)
                if date:
                    candidates.append((label, date.group(), url))
    output = []
    seen = set()
    for title, date_text, url in candidates:
        # Exam logistics, results and merit lists are not new recruitment.
        if not re.search(r"recruitment|applications? (?:are )?invit|vacan", title, re.IGNORECASE):
            continue
        if re.search(r"examination|hall.?ticket|merit|selection list|results?|interaction|verification|cancelled|canceled", title, re.IGNORECASE):
            continue
        try:
            date = datetime.strptime(re.sub(r"[.-]", "/", date_text), "%d/%m/%Y").replace(tzinfo=UTC).isoformat()
        except ValueError:
            continue
        if not fresh(date) or not relevant(query, title):
            continue
        key = re.sub(r"\W+", " ", title.casefold())
        if key in seen:
            continue
        seen.add(key)
        output.append({
            "id": entry["id"] + ":" + hashlib.sha256(title.encode()).hexdigest()[:16],
            "title": title, "org": entry["label"], "location": entry.get("district") or "Andhra Pradesh",
            "source": entry["label"], "source_url": url, "fetched_at": stamp,
            "published_at": date, "distance_km": None, "pay": None, "required_skills": {},
            "scam": scam_score(title, entry["label"]).__dict__, "remote": False,
            "new_since_visit": False, "description": title, "government": True,
            "application_status": "verify_on_source",
        })
    return output


async def search(query: str, place: str, refresh: bool = False) -> dict:
    found = []
    errors = {}
    sources = [e for e in REGISTRY["jobs"] if e.get("government") and (
        not e.get("district") or e["district"].casefold() in place.casefold())]
    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        try:
            origin = await lookup_ap(place, client)
        except (httpx.HTTPError, ValueError):
            origin = None
        if origin is None:
            raise ValueError("apPlaceRequired")
        for entry in sources:
            key = "government-jobs:v1:" + entry["id"]
            cached = await read(key, 6)
            if refresh or not cached or not cached["fresh"]:
                try:
                    await asyncio.sleep(1.05)
                    response = await client.get(entry["url_template"])
                    response.raise_for_status()
                    if len(response.content) > 2_000_000:
                        raise ValueError("oversized source")
                    if urlparse(str(response.url)).hostname != urlparse(entry["url_template"]).hostname:
                        raise ValueError("unexpected source redirect")
                    cached = await write(key, "jobs", {"html": response.text})
                except (httpx.HTTPError, ValueError) as exc:
                    errors[entry["id"]] = type(exc).__name__
            if cached:
                found.extend(parse(cached["payload"]["html"], entry, cached["fetched_at"], query))
    found.sort(key=lambda item: (item["published_at"], item["id"]), reverse=True)
    return {"leads": found[:25], "errors": errors, "region": "Andhra Pradesh",
            "job_type": "government", "origin": origin, "radius_km": None,
            "max_age_days": 60, "demand": {}, "new_count": 0,
            "refreshed_at": datetime.now(UTC).isoformat()}
