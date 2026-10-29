"""Google Places API (New) - OPTIONAL, capped, and not recommended as your lead database.

Why optional: Google's Maps Platform terms restrict caching/storing Places content
and using it outside Google's services (see docs/SOURCES.md). Phone and website are
Enterprise-tier fields (billed per request after a small monthly free cap).
This source is therefore off by default: you must pass --accept-google-terms, it stops
at GOOGLE_MAX_REQUESTS, and it exports the Google place ID so records can be refreshed.
You are responsible for confirming your intended use is allowed under your agreement.
"""
from __future__ import annotations

import logging
import time
from typing import Iterable

from ..models import Lead
from .base import Source, SearchSpec

log = logging.getLogger("leadcollector.google")
URL = "https://places.googleapis.com/v1/places:searchText"
FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.nationalPhoneNumber",
    "places.websiteUri", "places.googleMapsUri", "places.businessStatus", "nextPageToken",
])
ATTRIBUTION = "Google Maps Platform content - subject to Google Maps Platform Terms of Service"


class GooglePlacesSource(Source):
    name = "google"

    def collect(self, spec: SearchSpec, limit: int) -> Iterable[Lead]:
        if not spec.accept_google_terms:
            raise PermissionError("Pass --accept-google-terms after reading docs/SOURCES.md (Google section).")
        if not self.cfg.google_key:
            raise RuntimeError("Set GOOGLE_PLACES_API_KEY in .env (never in code).")
        headers = {"X-Goog-Api-Key": self.cfg.google_key, "X-Goog-FieldMask": FIELD_MASK}
        areas = spec.localities or [""]
        seen: set[str] = set()
        produced = 0
        for q in spec.category.google:
            for area in areas:
                text = f"{q} in {area + ', ' if area else ''}{spec.city}"
                token = None
                for _page in range(3):  # a query returns at most 60 places (3 pages of 20)
                    if self.stats.google_requests >= self.cfg.google_max_requests:
                        log.warning("GOOGLE_MAX_REQUESTS (%d) reached - stopping to avoid charges",
                                    self.cfg.google_max_requests)
                        return
                    body = {"textQuery": text, "pageSize": 20, "regionCode": "IN"}
                    if token:
                        body["pageToken"] = token
                    self.stats.add("google_requests")
                    resp = self.client.post(URL, headers=headers, json=body, rate_key="google")
                    if resp.status_code != 200:
                        log.warning("Google returned HTTP %s for %r", resp.status_code, text)
                        break
                    data = resp.json()
                    for p in data.get("places", []):
                        if p.get("id") in seen or p.get("businessStatus") not in (None, "OPERATIONAL"):
                            continue
                        seen.add(p["id"])
                        yield Lead(
                            business_name=(p.get("displayName") or {}).get("text", "").strip(),
                            phone=p.get("nationalPhoneNumber", ""), website=p.get("websiteUri", ""),
                            category=spec.category.label, city=spec.city,
                            address=p.get("formattedAddress", ""), source=self.name,
                            source_id=p["id"], source_url=p.get("googleMapsUri", ""),
                            attribution=ATTRIBUTION, phone_source=self.name if p.get("nationalPhoneNumber") else "",
                        )
                        produced += 1
                        if produced >= limit:
                            return
                    token = data.get("nextPageToken")
                    if not token:
                        break
                    time.sleep(0.5)
