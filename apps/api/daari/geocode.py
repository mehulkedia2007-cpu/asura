"""User-triggered Nominatim lookup with a persistent cache and one request per second."""

import asyncio
import time
from datetime import UTC, datetime

import httpx
from daari_core.geo import haversine
from sqlalchemy import text

from daari.db import engine
from daari.source_cache import source

_lock = asyncio.Lock()
_last_request = 0.0
_UA = "DAARI/0.1 (student and rural career guidance; https://github.com/dmrk22/asura)"


async def lookup(place: str, client: httpx.AsyncClient) -> tuple[float, float] | None:
    global _last_request
    key = " ".join(place.casefold().split())
    if not key:
        return None
    async with engine.connect() as conn:
        row = (await conn.execute(text(
            "SELECT latitude, longitude FROM geocodes WHERE place_key=:key"
        ), {"key": key})).first()
    if row is not None:
        return (row[0], row[1]) if row[0] is not None else None
    async with _lock:
        # Re-check after acquiring the lock: concurrent lookups for a place share one call.
        async with engine.connect() as conn:
            row = (await conn.execute(text(
                "SELECT latitude, longitude FROM geocodes WHERE place_key=:key"
            ), {"key": key})).first()
        if row is not None:
            return (row[0], row[1]) if row[0] is not None else None
        await asyncio.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        response = await client.get(source("nominatim")["url_template"], params={
            "q": place, "format": "jsonv2", "limit": 1, "countrycodes": "in",
        }, headers={"User-Agent": _UA})
        response.raise_for_status()
        results = response.json()
        coords = (float(results[0]["lat"]), float(results[0]["lon"])) if results else None
        async with engine.begin() as conn:
            await conn.execute(text("""
                INSERT INTO geocodes(place_key, latitude, longitude, fetched_at)
                VALUES (:key, :lat, :lon, :now) ON CONFLICT(place_key) DO NOTHING
            """), {"key": key, "lat": coords[0] if coords else None,
                    "lon": coords[1] if coords else None, "now": datetime.now(UTC)})
        return coords


__all__ = ["haversine", "lookup"]


async def lookup_ap(place: str, client: httpx.AsyncClient) -> tuple[float, float] | None:
    """Resolve a real AP address; old unscoped geocode caches cannot bypass it."""
    from daari.source_cache import read, write

    if place.strip().casefold() in {"", "india", "andhra pradesh", "ap"}:
        return None
    key = "geocode-ap-v1:" + " ".join(place.casefold().split())
    cached = await read(key, 6)
    if cached and cached["fresh"]:
        coords = cached["payload"].get("coords")
        return (float(coords[0]), float(coords[1])) if isinstance(coords, list) and len(coords) == 2 else None
    global _last_request
    async with _lock:
        await asyncio.sleep(max(0, 1.05 - (time.monotonic() - _last_request)))
        _last_request = time.monotonic()
        query = place if "andhra pradesh" in place.casefold() else f"{place}, Andhra Pradesh"
        response = await client.get(source("nominatim")["url_template"], params={
            "q": query, "format": "jsonv2", "limit": 5, "countrycodes": "in",
            "addressdetails": 1, "accept-language": "en",
        }, headers={"User-Agent": _UA})
        response.raise_for_status()
        coords = None
        for item in response.json():
            address = item.get("address") or {}
            if address.get("state", "").casefold() == "andhra pradesh" and address.get("country_code") == "in":
                coords = (float(item["lat"]), float(item["lon"]))
                break
        await write(key, "geo", {"coords": coords})
        return coords
