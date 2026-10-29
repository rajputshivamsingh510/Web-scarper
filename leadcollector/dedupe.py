"""Duplicate detection and merging.

Philosophy: it is better to keep a rare duplicate than to merge two different branches.
Two records are merged only when the evidence agrees:
  * same source + source id, or
  * same phone and a similar name, or
  * very similar name PLUS corroboration (same domain, same phone, <=200 m apart, or similar address), or
  * same website domain and a fairly similar name.
Records with conflicting phones, addresses or locations (>500 m) are never merged.
"""
from __future__ import annotations

import copy
import math
from collections import defaultdict

from rapidfuzz import fuzz

from .models import Lead
from .normalize import domain_of, is_aggregator, is_social, normalize_name


def _dist_m(a: Lead, b: Lead) -> float | None:
    if None in (a.lat, a.lon, b.lat, b.lon):
        return None
    r = 6371000.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _join(a: str, b: str) -> str:
    seen = []
    for part in (a.split(";") if a else []) + (b.split(";") if b else []):
        if part and part not in seen:
            seen.append(part)
    return ";".join(seen)


def merge_group(group: list[Lead]) -> Lead:
    group = sorted(group, key=lambda l: -l.completeness())
    base = copy.copy(group[0])
    for other in group[1:]:
        for f in ("phone", "website", "address", "category", "source_url", "phone_source",
                  "lat", "lon", "confidence"):
            if not getattr(base, f) and getattr(other, f):
                setattr(base, f, getattr(other, f))
        base.source = _join(base.source, other.source)
        base.source_id = _join(base.source_id, other.source_id)
        base.attribution = _join(base.attribution, other.attribution)
        base.extra_phones = _join(base.extra_phones, other.extra_phones)
        if other.phone and other.phone != base.phone:
            base.extra_phones = _join(base.extra_phones, other.phone)
    base.extra_phones = ";".join(p for p in base.extra_phones.split(";") if p and p != base.phone)
    return base


def dedupe(leads: list[Lead], name_threshold: int = 90) -> tuple[list[Lead], int]:
    n = len(leads)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    names = [normalize_name(l.business_name) for l in leads]
    addrs = [normalize_name(l.address) for l in leads]
    doms = [d if d and not is_social(l.website) and not is_aggregator(l.website) else ""
            for l, d in ((l, domain_of(l.website)) for l in leads)]

    def compatible(i: int, j: int) -> bool:
        a, b = leads[i], leads[j]
        if a.phone and b.phone and a.phone != b.phone:
            return False
        if addrs[i] and addrs[j] and fuzz.partial_ratio(addrs[i], addrs[j]) < 60:
            return False
        d = _dist_m(a, b)
        return not (d is not None and d > 500)

    def corroborated(i: int, j: int) -> bool:
        a, b = leads[i], leads[j]
        if a.phone and a.phone == b.phone:
            return True
        if doms[i] and doms[i] == doms[j]:
            return True
        d = _dist_m(a, b)
        if d is not None and d <= 200:
            return True
        return bool(addrs[i] and addrs[j] and fuzz.partial_ratio(addrs[i], addrs[j]) >= 80)

    def should_merge(i: int, j: int) -> bool:
        a, b = leads[i], leads[j]
        if a.source and a.source == b.source and a.source_id and a.source_id == b.source_id:
            return True
        r = fuzz.token_sort_ratio(names[i], names[j])
        if a.phone and a.phone == b.phone and r >= 50:
            return True
        if not compatible(i, j):
            return False
        if r >= name_threshold and corroborated(i, j):
            return True
        return bool(doms[i] and doms[i] == doms[j] and r >= 70)

    blocks: dict[tuple, list[int]] = defaultdict(list)
    for i in range(n):
        blocks[("sid", leads[i].source, leads[i].source_id)].append(i) if leads[i].source_id else None
        if leads[i].phone:
            blocks[("phone", leads[i].phone)].append(i)
        if doms[i]:
            blocks[("dom", doms[i])].append(i)
        if names[i]:
            blocks[("name", names[i][:4])].append(i)

    for members in blocks.values():
        for x in range(len(members)):
            for y in range(x + 1, len(members)):
                i, j = members[x], members[y]
                ri, rj = find(i), find(j)
                if ri != rj and should_merge(i, j):
                    parent[rj] = ri

    groups: dict[int, list[Lead]] = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(leads[i])
    out = [merge_group(g) if len(g) > 1 else g[0] for g in groups.values()]
    return out, n - len(out)
