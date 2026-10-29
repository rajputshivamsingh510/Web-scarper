"""OpenStreetMap via the Overpass API.

Free, but: (1) phone/website coverage in India is often thin - measure it in the pilot;
(2) the public server is shared: keep it to a handful of queries, never loop over
many small areas; (3) data is ODbL - keep the attribution and read the share-alike rules.
https://wiki.openstreetmap.org/wiki/Overpass_API  |  https://www.openstreetmap.org/copyright
"""
from __future__ import annotations

import logging
import re
from typing import Iterable

from ..geocode import bbox_for
from ..models import Lead
from ..normalize import normalize_phones
from .base import Source, SearchSpec

log = logging.getLogger("leadcollector.osm")
ATTRIBUTION = "(c) OpenStreetMap contributors, ODbL 1.0"


def _selector(flt: str) -> str:
    if "=" in flt:
        k, v = flt.split("=", 1)
        return f'["{k.strip()}"="{v.strip()}"]'
    return f'["{flt.strip()}"]'


def build_query(filters: list[str], city: str | None = None, bbox=None, timeout: int = 120) -> str:
    if not filters:
        raise ValueError("No OSM filters for this category. Use --osm-filter key=value.")
    if city:
        if '"' in city or "\\" in city:
            raise ValueError("Invalid city name")
        head = f'area["name"="{city}"]["boundary"="administrative"]->.a;\n'
        body = "\n".join(f'  nwr(area.a){_selector(f)}["name"];' for f in filters)
    else:
        s, w, n, e = bbox
        head = ""
        body = "\n".join(f'  nwr{_selector(f)}["name"]({s},{w},{n},{e});' for f in filters)
    return f"[out:json][timeout:{timeout}];\n{head}(\n{body}\n);\nout tags center;"


def _address(tags: dict) -> str:
    if tags.get("addr:full"):
        return tags["addr:full"]
    parts = [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb"),
             tags.get("addr:city"), tags.get("addr:postcode")]
    return ", ".join(p for p in parts if p)


def parse_elements(elements: list[dict], category_label: str, city: str) -> list[Lead]:
    leads = []
    for el in elements:
        tags = el.get("tags") or {}
        name = (tags.get("name") or "").strip()
        if not name:
            continue
        phones = normalize_phones(";".join(filter(None, [tags.get("phone"), tags.get("contact:phone"),
                                                         tags.get("contact:mobile"), tags.get("mobile")])))
        site = tags.get("website") or tags.get("contact:website") or tags.get("url") or ""
        center = el.get("center") or {}
        leads.append(Lead(
            business_name=name, phone=phones[0] if phones else "",
            extra_phones=";".join(phones[1:3]), website=site,
            category=category_label, city=tags.get("addr:city") or city, address=_address(tags),
            source="osm", source_id=f"{el.get('type')}/{el.get('id')}",
            source_url=f"https://www.openstreetmap.org/{el.get('type')}/{el.get('id')}",
            attribution=ATTRIBUTION, phone_source="osm" if phones else "",
            lat=el.get("lat", center.get("lat")), lon=el.get("lon", center.get("lon")),
        ))
    return leads


class OverpassSource(Source):
    name = "osm"

    def _run(self, query: str) -> list[dict]:
        resp = self.client.post(self.cfg.overpass_url, data={"data": query}, rate_key="overpass")
        if resp.status_code != 200:
            raise RuntimeError(f"Overpass returned HTTP {resp.status_code}: {resp.text[:200]}")
        return resp.json().get("elements", [])

    def collect(self, spec: SearchSpec, limit: int) -> Iterable[Lead]:
        filters = spec.category.osm
        elements: list[dict] = []
        if spec.bbox is None and spec.city:
            elements = self._run(build_query(filters, city=spec.city))
            if not elements:
                log.info("No elements in area '%s'; falling back to a Nominatim bounding box", spec.city)
        if not elements:
            bbox = spec.bbox or bbox_for(self.client, spec.city, spec.state, self.cfg.data_dir / "cache")
            elements = self._run(build_query(filters, bbox=bbox))
        leads = parse_elements(elements, spec.category.label, spec.city)
        yield from leads[:limit]
