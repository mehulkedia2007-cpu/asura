"""Deterministic geographic distance in kilometres."""

import math


def haversine(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    for lat, lon in ((a_lat, a_lon), (b_lat, b_lon)):
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError("invalid latitude or longitude")
    radius_km = 6371.0088
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    dlat, dlon = lat2 - lat1, math.radians(b_lon - a_lon)
    arc = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return round(2 * radius_km * math.asin(min(1.0, math.sqrt(arc))), 1)
