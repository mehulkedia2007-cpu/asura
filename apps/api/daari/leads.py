"""Stamped job leads from Adzuna and Remotive, with computed local distance."""

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from daari_core.demand import weights
from daari_core.geo import haversine
from daari_core.graph import build as build_graph
from daari_core.match import Candidate, match
from daari_core.scam import score as scam_score

from daari.config import settings
from daari.embeddings import get_embeddings
from daari.geocode import lookup
from daari.scam_llm import second_opinion
from daari.source_cache import read, source, write
from daari.taxonomy_loader import get_taxonomy


def _skills(text: str) -> dict[str, int]:
    found = {}
    lowered = text.casefold()
    for skill in get_taxonomy().skills.values():
        terms = [skill.label_en, *skill.aliases]
        if any(len(term) >= 3 and re.search(r"(?<!\w)" + re.escape(term.casefold()) + r"(?!\w)", lowered)
               for term in terms):
            found[skill.id] = skill.level
    return found


def _url(value: Any, host: str) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    return value if parsed.scheme == "https" and (parsed.hostname == host or parsed.hostname and parsed.hostname.endswith("." + host)) else None


def normalize_adzuna(raw: dict, fetched_at: str, origin: tuple[float, float] | None) -> dict | None:
    url = _url(raw.get("redirect_url"), "adzuna.com") or _url(raw.get("redirect_url"), "adzuna.in")
    if not url:
        return None
    raw_lat, raw_lon = raw.get("latitude"), raw.get("longitude")
    try:
        if raw_lat is None or raw_lon is None:
            raise ValueError("no coordinates")
        lat, lon = float(raw_lat), float(raw_lon)
        distance = haversine(*origin, lat, lon) if origin else None
    except (TypeError, ValueError):
        lat = lon = distance = None
    description = re.sub(r"<[^>]+>", " ", str(raw.get("description") or ""))
    org = str((raw.get("company") or {}).get("display_name") or "")
    pay_min = raw.get("salary_min")
    return {
        "id": f"adzuna:{raw.get('id')}", "source": "Adzuna", "source_url": url,
        "fetched_at": fetched_at, "published_at": raw.get("created"),
        "title": str(raw.get("title") or ""), "org": org,
        "location": str((raw.get("location") or {}).get("display_name") or ""),
        "lat": lat, "lon": lon, "distance_km": distance,
        "pay": f"₹{pay_min:,.0f}+" if isinstance(pay_min, (float, int)) and pay_min > 0 else None,
        "description": description[:1200], "required_skills": _skills(f"{raw.get('title', '')} {description}"),
        "scam": scam_score(description, org).__dict__, "remote": False,
    }


def normalize_remotive(raw: dict, fetched_at: str) -> dict | None:
    url = _url(raw.get("url"), "remotive.com")
    if not url:
        return None
    location = str(raw.get("candidate_required_location") or "Remote")
    if location.casefold() not in {"remote", "worldwide", "anywhere"} and not any(
        term in location.casefold() for term in ("india", "asia", "global")
    ):
        return None
    description = re.sub(r"<[^>]+>", " ", str(raw.get("description") or ""))
    org = str(raw.get("company_name") or "")
    return {
        "id": f"remotive:{raw.get('id')}", "source": "Remotive", "source_url": url,
        "fetched_at": fetched_at, "published_at": raw.get("publication_date"),
        "title": str(raw.get("title") or ""), "org": org,
        "location": location,
        "lat": None, "lon": None, "distance_km": None,
        "pay": str(raw.get("salary") or "") or None, "description": description[:1200],
        "required_skills": _skills(f"{raw.get('title', '')} {description}"),
        "scam": scam_score(description, org).__dict__, "remote": True,
    }


async def _fetch(client: httpx.AsyncClient, key: str, url: str, params: dict,
                 refresh: bool) -> tuple[dict | None, str | None]:
    cached = await read(key, 6)
    if cached and cached["fresh"] and not refresh:
        return cached, None
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise TypeError("source did not return an object")
        return await write(key, "jobs", payload), None
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        return (cached or await read(key)), type(exc).__name__


async def search(query: str, place: str, held: dict[str, int], refresh: bool = False,
                 since: datetime | None = None) -> dict:
    query, place = query.strip()[:100], place.strip()[:150]
    if since is not None and since.tzinfo is None:
        since = since.replace(tzinfo=UTC)
    if not query or not place:
        raise ValueError("query and place are required")
    leads: list[dict] = []
    errors: dict[str, str] = {}
    async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (compatible; DAARI/0.1; https://github.com/dmrk22/asura)"
    }) as client:
        try:
            origin = await lookup(place, client)
        except (httpx.HTTPError, ValueError):
            origin = None
            errors["nominatim"] = "unavailable"
        if settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY:
            cache, error = await _fetch(client, f"adzuna:{query.casefold()}:{place.casefold()}",
                source("adzuna")["url_template"].format(page=1), {
                    "app_id": settings.ADZUNA_APP_ID, "app_key": settings.ADZUNA_APP_KEY,
                    "what": query, "where": place, "results_per_page": 50,
                    "content-type": "application/json",
                }, refresh)
            if error:
                errors["adzuna"] = error
            if cache:
                leads.extend(item for raw in cache["payload"].get("results", [])
                             if (item := normalize_adzuna(raw, cache["fetched_at"], origin)))
        else:
            errors["adzuna"] = "no_api_key"
        cache, error = await _fetch(client, f"remotive:{query.casefold()}",
            source("remotive")["url_template"], {"search": query, "limit": 25}, refresh)
        if error:
            errors["remotive"] = error
        if cache:
            leads.extend(item for raw in cache["payload"].get("jobs", [])
                         if (item := normalize_remotive(raw, cache["fetched_at"])))
    for item in leads:
        try:
            published = datetime.fromisoformat(str(item["published_at"]))
            if published.tzinfo is None:
                published = published.replace(tzinfo=UTC)
            item["new_since_visit"] = since is not None and published > since
        except (TypeError, ValueError):
            item["new_since_visit"] = False
    local = [item for item in leads if item["distance_km"] is not None]
    selected_radius = next((radius for radius in (25, 50, 100)
                            if sum(item["distance_km"] <= radius for item in local) >= 5), 100)
    visible = [item for item in leads if item["remote"] or item["distance_km"] is None
               or item["distance_km"] <= selected_radius]
    for item in visible[:5]:
        base = item["scam"]
        if 0.1 <= base["score"] < 0.5 and len(item["description"]) >= 30:
            delta, reason, error = await second_opinion(item["description"])
            if error:
                errors["scam_llm"] = error
            if delta and reason:
                value = min(1.0, round(base["score"] + min(delta, 0.2), 2))
                base["score"] = value
                base["badge"] = "red" if value >= 0.5 else "amber" if value >= 0.3 else "none"
                base["reasons"] = [*base["reasons"], reason]
    # Unknown-distance local listings remain visible but clearly carry no km value.
    visible.sort(key=lambda item: (item["remote"], item["distance_km"] if item["distance_km"] is not None else float("inf"), item["id"]))
    taxonomy = get_taxonomy()
    district_listings = [set(item["required_skills"]) for item in local if item["distance_km"] <= 100]
    demand = weights(district_listings, set(taxonomy.skills))
    if held:
        embeddings = get_embeddings()
        candidates = [Candidate(id=item["id"], title=item["title"], org=item["org"],
            location=item["location"], required_skills=item["required_skills"],
            source=item["source"], source_url=item["source_url"], fetched_at=item["fetched_at"],
            extra={"distance_km": item["distance_km"]}) for item in visible]
        ranked = match(taxonomy, held, candidates, demand=demand,
                       graph=build_graph(taxonomy, embeddings), embeddings=embeddings,
                       radius_km=selected_radius)
        by_id = {item.candidate_id: item for item in ranked}
        for item in visible:
            item["match"] = by_id[item["id"]].__dict__
        visible.sort(key=lambda item: (-item["match"]["score"], item["id"]))
    return {"leads": visible, "demand": demand,
            "radius_km": selected_radius, "origin": origin, "errors": errors,
            "new_count": sum(item["new_since_visit"] for item in visible),
            "refreshed_at": datetime.now(UTC).isoformat()}
