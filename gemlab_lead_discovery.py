"""
GemLab lead discovery - starter MVP
-----------------------------------
Collects BUSINESS listings (clinics, hospitals, petrol pumps, etc.) through the
official Google Places API (Text Search, "Places API (New)"), cleans them,
removes duplicates, scores them and writes a CSV for the sales team to review.

Nothing is sent to TeleCRM automatically. Approve rows in the CSV first, then
run with --push (after you have filled in the TeleCRM section below).

Setup:
    pip install httpx pandas pydantic phonenumbers rapidfuzz
    export GOOGLE_PLACES_API_KEY="your-key"      # never hard-code keys

Run:
    python gemlab_lead_discovery.py --city "Ludhiana" --out leads_review.csv
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date

import httpx
import pandas as pd
import phonenumbers
from pydantic import BaseModel, field_validator
from rapidfuzz import fuzz

# ----------------------------------------------------------------------------
# 1. CONFIG - edit these, they are the "decisions needed" from the project doc
# ----------------------------------------------------------------------------

# Business categories used as a rough proxy for higher-income owners.
# Note: a listing is a BUSINESS, not proof of anyone's wealth. Scoring below
# only prioritises; a human decides who is actually a suitable lead.
SEARCH_QUERIES = {
    "Doctor / Clinic": ["multispecialty clinic", "private hospital", "dental clinic", "skin clinic"],
    "Petrol Pump": ["petrol pump", "fuel station"],
    "Business Owner": ["manufacturer", "factory", "wholesale trader", "builders and developers", "hotel"],
    "Other High-Ticket Business": ["car showroom", "jewellery showroom", "real estate developer"],
}

# Higher = more likely to be a decision-maker/owner with relevant budget.
CATEGORY_WEIGHT = {
    "Doctor / Clinic": 3,
    "Petrol Pump": 3,
    "Business Owner": 3,
    "Other High-Ticket Business": 2,
}

MAX_PAGES_PER_QUERY = 3          # each page = up to 20 results (API cost control)
REQUEST_PAUSE_SECONDS = 1.0      # polite rate limit
PLACES_URL = "https://places.googleapis.com/v1/places:searchText"

# Only request the fields we need (also keeps API cost lower).
FIELD_MASK = ",".join([
    "places.id",
    "places.displayName",
    "places.formattedAddress",
    "places.nationalPhoneNumber",
    "places.internationalPhoneNumber",
    "places.websiteUri",
    "places.googleMapsUri",
    "places.businessStatus",
    "places.rating",
    "places.userRatingCount",
    "nextPageToken",
])


# ----------------------------------------------------------------------------
# 2. Record schema + validation
# ----------------------------------------------------------------------------

class Lead(BaseModel):
    source: str = "Google Places API"
    source_id: str
    source_url: str | None = None
    collected_on: str = date.today().isoformat()
    business_name: str
    category: str
    city: str
    address: str | None = None
    business_phone: str | None = None   # business listing number only
    website: str | None = None
    rating: float | None = None
    rating_count: int | None = None
    score: int = 0
    review_status: str = "NEW"          # NEW / APPROVED / REJECTED (set by sales team)
    contact_permission: str = "UNKNOWN" # record the lawful basis before outreach
    opted_out: bool = False

    @field_validator("business_phone")
    @classmethod
    def normalise_phone(cls, v: str | None) -> str | None:
        if not v:
            return None
        try:
            num = phonenumbers.parse(v, "IN")
            if phonenumbers.is_valid_number(num):
                return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
        except phonenumbers.NumberParseException:
            pass
        return None  # invalid format -> blank, flagged in review


# ----------------------------------------------------------------------------
# 3. Collect (official API, no scraping of Google Maps pages)
# ----------------------------------------------------------------------------

def collect(city: str, api_key: str) -> list[Lead]:
    leads: list[Lead] = []
    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK}

    with httpx.Client(timeout=30) as client:
        for category, queries in SEARCH_QUERIES.items():
            for q in queries:
                page_token = None
                for _ in range(MAX_PAGES_PER_QUERY):
                    body = {"textQuery": f"{q} in {city}", "pageSize": 20, "regionCode": "IN"}
                    if page_token:
                        body["pageToken"] = page_token
                    resp = client.post(PLACES_URL, headers=headers, json=body)
                    if resp.status_code != 200:
                        print(f"[warn] {q!r}: HTTP {resp.status_code} {resp.text[:200]}", file=sys.stderr)
                        break
                    data = resp.json()
                    for p in data.get("places", []):
                        if p.get("businessStatus") not in (None, "OPERATIONAL"):
                            continue
                        leads.append(Lead(
                            source_id=p["id"],
                            source_url=p.get("googleMapsUri"),
                            business_name=p.get("displayName", {}).get("text", "").strip(),
                            category=category,
                            city=city,
                            address=p.get("formattedAddress"),
                            business_phone=p.get("nationalPhoneNumber") or p.get("internationalPhoneNumber"),
                            website=p.get("websiteUri"),
                            rating=p.get("rating"),
                            rating_count=p.get("userRatingCount"),
                        ))
                    page_token = data.get("nextPageToken")
                    time.sleep(REQUEST_PAUSE_SECONDS)
                    if not page_token:
                        break
    return leads


# ----------------------------------------------------------------------------
# 4. Clean, de-duplicate, score
# ----------------------------------------------------------------------------

def to_dataframe(leads: list[Lead]) -> pd.DataFrame:
    df = pd.DataFrame([l.model_dump() for l in leads])
    if df.empty:
        return df
    df = df[df["business_name"].str.len() > 0]
    df = df.drop_duplicates(subset="source_id")
    return df.reset_index(drop=True)


def flag_fuzzy_duplicates(df: pd.DataFrame, threshold: int = 90) -> pd.DataFrame:
    """Flag (not delete) similar names with the same phone or very similar address."""
    df["possible_duplicate_of"] = ""
    names = df["business_name"].str.lower().tolist()
    addrs = df["address"].fillna("").str.lower().tolist()
    phones = df["business_phone"].fillna("").tolist()
    for i in range(len(df)):
        for j in range(i):
            same_phone = phones[i] and phones[i] == phones[j]
            similar = fuzz.token_sort_ratio(names[i], names[j]) >= threshold and \
                      fuzz.partial_ratio(addrs[i], addrs[j]) >= 85
            if same_phone or similar:
                df.at[i, "possible_duplicate_of"] = df.at[j, "source_id"]
                break
    return df


def score(df: pd.DataFrame) -> pd.DataFrame:
    """Transparent rules so a human can see why a row ranks where it does."""
    def row_score(r) -> int:
        s = CATEGORY_WEIGHT.get(r["category"], 1)
        s += 2 if r["business_phone"] else 0
        s += 1 if r["website"] else 0
        s += 1 if (r["rating_count"] or 0) >= 20 else 0
        s -= 3 if r["possible_duplicate_of"] else 0
        return int(s)

    df["score"] = df.apply(row_score, axis=1)
    return df.sort_values("score", ascending=False).reset_index(drop=True)


# ----------------------------------------------------------------------------
# 5. TeleCRM push - DISABLED until endpoints are confirmed from your account
# ----------------------------------------------------------------------------

TELECRM_BASE_URL = ""      # fill from GemLab's TeleCRM API documentation
TELECRM_API_KEY = os.getenv("TELECRM_API_KEY", "")


def push_to_telecrm(df: pd.DataFrame) -> None:
    """
    Only rows where review_status == APPROVED, opted_out is False and
    contact_permission is not UNKNOWN should ever be sent.
    Map the fields to TeleCRM's real schema before enabling - the endpoint
    names and payload shape below are placeholders, not verified.
    """
    if not TELECRM_BASE_URL or not TELECRM_API_KEY:
        raise RuntimeError("Set TELECRM_BASE_URL and TELECRM_API_KEY from TeleCRM's docs first.")

    ready = df[(df["review_status"] == "APPROVED") & (~df["opted_out"].astype(bool))
               & (df["contact_permission"] != "UNKNOWN")]
    print(f"{len(ready)} approved leads ready to push (test pipeline first).")
    # TODO: 1) search TeleCRM for an existing lead by phone,
    #       2) create/update with the documented endpoint,
    #       3) log success/failure per row and retry temporary errors.


# ----------------------------------------------------------------------------
# 6. CLI
# ----------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--city", required=True)
    ap.add_argument("--out", default="leads_review.csv")
    ap.add_argument("--push", metavar="REVIEWED_CSV", help="push approved rows from a reviewed CSV")
    args = ap.parse_args()

    if args.push:
        push_to_telecrm(pd.read_csv(args.push))
        return

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        sys.exit("Set GOOGLE_PLACES_API_KEY first.")

    df = to_dataframe(collect(args.city, api_key))
    if df.empty:
        sys.exit("No results.")
    df = score(flag_fuzzy_duplicates(df))
    df.to_csv(args.out, index=False)
    print(f"Saved {len(df)} leads to {args.out}. Sales team: set review_status to APPROVED/REJECTED.")


if __name__ == "__main__":
    main()
