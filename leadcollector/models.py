"""The Lead record shared by every stage."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field, asdict, fields
from datetime import datetime, timezone

from .normalize import domain_of, normalize_name, is_social, is_aggregator

CSV_COLUMNS = [
    "business_name", "phone", "website", "category", "city", "address",
    "source", "source_id", "source_url", "attribution",
    "phone_status", "website_status", "verification_status",
    "phone_source", "extra_phones", "collected_at", "lead_key",
]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Lead:
    business_name: str = ""
    phone: str = ""
    website: str = ""
    category: str = ""
    city: str = ""
    address: str = ""
    source: str = ""
    source_id: str = ""
    source_url: str = ""
    attribution: str = ""
    phone_status: str = ""
    website_status: str = ""
    verification_status: str = ""
    phone_source: str = ""
    extra_phones: str = ""
    collected_at: str = field(default_factory=_now)
    lead_key: str = ""
    # internal only (not exported to CSV)
    confidence: float | None = None
    lat: float | None = None
    lon: float | None = None

    def completeness(self) -> int:
        return sum(bool(x) for x in (self.phone, self.website, self.address, self.category))

    def compute_key(self) -> str:
        dom = domain_of(self.website)
        name = normalize_name(self.business_name)
        if self.phone:
            raw = f"p:{self.phone}"
        elif dom and not is_social(self.website) and not is_aggregator(self.website):
            raw = f"d:{dom}|{name}"
        else:
            raw = f"n:{name}|{normalize_name(self.address)}|{self.source}{self.source_id}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_row(self) -> dict:
        d = asdict(self)
        return {c: d.get(c, "") for c in CSV_COLUMNS}

    @classmethod
    def from_dict(cls, d: dict) -> "Lead":
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in d.items() if k in names})
