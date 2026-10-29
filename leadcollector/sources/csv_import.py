"""Import a CSV/Excel export - e.g. from a licensed data provider or your own list."""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from ..models import Lead
from .base import Source, SearchSpec

_GUESSES = {
    "business_name": ["business_name", "name", "company", "company_name", "title"],
    "phone": ["phone", "mobile", "telephone", "contact", "phone_number", "contact_number"],
    "website": ["website", "url", "site", "web", "website_url"],
    "category": ["category", "type", "industry"],
    "city": ["city", "town", "locality"],
    "address": ["address", "full_address", "street_address"],
}


class CsvSource(Source):
    name = "csv"

    def collect(self, spec: SearchSpec, limit: int) -> Iterable[Lead]:
        if not spec.csv_path:
            raise ValueError("--csv-file is required for --source csv")
        path = spec.csv_path
        df = pd.read_excel(path, dtype=str) if path.lower().endswith((".xlsx", ".xls")) \
            else pd.read_csv(path, dtype=str, keep_default_na=False)
        df = df.fillna("")
        lower = {c.lower().strip(): c for c in df.columns}
        mapping = {}
        for field, guesses in _GUESSES.items():
            explicit = spec.csv_map.get(field)
            col = lower.get(explicit.lower()) if explicit else next((lower[g] for g in guesses if g in lower), None)
            if col:
                mapping[field] = col
        if "business_name" not in mapping:
            raise ValueError(f"Could not find a name column. Columns: {list(df.columns)}. Use --csv-map business_name=<col>")
        for i, row in df.head(limit).iterrows():
            get = lambda f: str(row[mapping[f]]).strip() if f in mapping else ""
            if not get("business_name"):
                continue
            yield Lead(business_name=get("business_name"), phone=get("phone"), website=get("website"),
                       category=get("category") or spec.category.label, city=get("city") or spec.city,
                       address=get("address"), source="csv", source_id=str(i),
                       source_url=path, attribution="Imported file - check your provider's licence")
