"""City -> bounding box via OpenStreetMap Nominatim (1 request, cached on disk).

Nominatim policy: max 1 request/second, identify yourself, no bulk geocoding.
https://operations.osmfoundation.org/policies/nominatim/
"""
from __future__ import annotations

import json
from pathlib import Path

from .http import HttpClient

NOMINATIM = "https://nominatim.openstreetmap.org/search"


def bbox_for(client: HttpClient, city: str, state: str, cache_dir: Path) -> tuple[float, float, float, float]:
    """Return (south, west, north, east)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = cache_dir / "geocode.json"
    data = json.loads(cache.read_text("utf-8")) if cache.exists() else {}
    key = f"{city}|{state}".lower()
    if key not in data:
        q = ", ".join(x for x in (city, state, "India") if x)
        resp = client.get(NOMINATIM, params={"q": q, "format": "jsonv2", "limit": 1}, rate_key="nominatim")
        if resp.status_code != 200:
            raise ValueError(f"Nominatim returned HTTP {resp.status_code} for '{q}'. Check CONTACT_EMAIL in .env, "
                             "wait a minute, or pass --bbox south,west,north,east.")
        results = resp.json()
        if not results:
            raise ValueError(f"Nominatim found nothing for '{q}'. Pass --bbox south,west,north,east instead.")
        s, n, w, e = (float(x) for x in results[0]["boundingbox"])
        data[key] = [s, w, n, e]
        cache.write_text(json.dumps(data), "utf-8")
    s, w, n, e = data[key]
    return s, w, n, e
