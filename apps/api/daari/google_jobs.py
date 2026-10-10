"""Budgeted Google Jobs feed, with independently verified AP locations."""
import hashlib
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse

import httpx
from daari_core.geo import haversine
from daari_core.scam import score
from redis.asyncio import Redis
from redis.exceptions import RedisError

from daari.config import settings
from daari.geocode import lookup_ap
from daari.job_filters import fresh, relevant
from daari.source_cache import read, write


def posted_date(label: str, stamp: str) -> str | None:
    match = re.fullmatch(r"(\d+) (hour|day|week|month)s? ago", label.strip(), re.IGNORECASE)
    base = datetime.fromisoformat(stamp)
    if label.casefold() in {"today", "just posted"}:
        return base.isoformat()
    if not match:
        return None
    amount = int(match[1])
    unit = match[2].casefold()
    delta = timedelta(hours=amount) if unit == "hour" else timedelta(days=amount * {"day": 1, "week": 7, "month": 30}[unit])
    return (base - delta).isoformat()


async def search(client: httpx.AsyncClient, query: str, place: str, origin: tuple[float, float],
                 refresh: bool = False) -> tuple[list[dict], str | None]:
    if not settings.SERPAPI_KEY:
        return [], "no_api_key"
    key = f"google-jobs:ap-v1:{query.casefold()}:{place.casefold()}"
    cached = await read(key, 6)
    if not cached or not cached["fresh"] or refresh:
        redis = Redis.from_url(settings.REDIS_URL, socket_timeout=5)
        try:
            account = await client.get("https://serpapi.com/account", params={"api_key": settings.SERPAPI_KEY})
            account.raise_for_status()
            quota = account.json()
            budget = min(100, max(0, settings.SERPAPI_MONTHLY_BUDGET))
            # Never use paid plans or extra purchased credits.
            if quota.get("plan_monthly_price") != 0 or int(quota.get("plan_searches_left") or 0) < 1:
                return [], "free_plan_unavailable"
            if int(quota.get("this_month_usage") or 0) >= budget:
                return [], "monthly_budget_exhausted"
            budget_key = "daari:google-jobs-budget:" + str(quota.get("plan_renewal_date"))
            used = await redis.incr(budget_key)
            await redis.expire(budget_key, 35 * 86400)
            if used > budget:
                return [], "monthly_budget_exhausted"
            response = await client.get("https://serpapi.com/search.json", params={
                "engine": "google_jobs", "q": f"{query} jobs in {place}", "location": place,
                "gl": "in", "hl": "en", "api_key": settings.SERPAPI_KEY,
            })
            response.raise_for_status()
            payload = response.json()
            if payload.get("error"):
                return [], "source_error"
            cached = await write(key, "jobs", payload)
        except (httpx.HTTPError, ValueError, TypeError, RedisError) as exc:
            # Include only the exception type, never URLs carrying private keys.
            return [], type(exc).__name__
        finally:
            await redis.aclose()
    found = []
    for raw in cached["payload"].get("jobs_results", [])[:10]:
        title = str(raw.get("title") or "")
        description = str(raw.get("description") or "")
        ext = raw.get("detected_extensions") or {}
        label = str(ext.get("posted_at") or "")
        date = posted_date(label, cached["fetched_at"])
        url = str(raw.get("share_link") or "")
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in {"www.google.com", "www.google.co.in"}:
            continue
        if ext.get("work_from_home") or not fresh(date) or not relevant(query, title, description):
            continue
        location = str(raw.get("location") or "").strip()
        if location.casefold() in {"", "india", "andhra pradesh", "remote", "anywhere", "worldwide"}:
            continue
        try:
            coords = await lookup_ap(location, client)
        except (httpx.HTTPError, ValueError):
            coords = None
        if not coords:
            continue
        org = str(raw.get("company_name") or "")
        from daari.leads import _skills
        found.append({
            "id": "google-jobs:" + hashlib.sha256(str(raw.get("job_id") or url).encode()).hexdigest()[:20],
            "title": title, "org": org, "location": str(raw.get("location") or ""),
            "lat": coords[0], "lon": coords[1], "distance_km": haversine(*origin, *coords),
            "source": "Google Jobs via SerpAPI", "source_url": url, "fetched_at": cached["fetched_at"],
            "published_at": date, "published_label": label, "pay": None, "description": description[:1200],
            "required_skills": _skills(title + " " + description), "scam": score(description, org).__dict__,
            "remote": False, "new_since_visit": False,
        })
    return found, None
