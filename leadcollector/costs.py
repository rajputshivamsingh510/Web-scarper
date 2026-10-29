"""Cost model. Numbers marked ASSUMPTION are not verified prices."""
from __future__ import annotations

# Verified from Google's published pricing categories/SKU tables (see docs/SOURCES.md):
GOOGLE_TEXT_SEARCH_ENTERPRISE_USD_PER_1000 = 35.0   # phone + website fields
GOOGLE_ENTERPRISE_FREE_PER_MONTH = 1000
GOOGLE_RESULTS_PER_REQUEST = 20
# ASSUMPTION: with overlapping queries only about half of each page is new to us.
GOOGLE_NEW_RECORD_EFFICIENCY = 0.5
# Third-party reported (unverified), phone/website may need a higher tier:
FOURSQUARE_PRO_USD_PER_1000 = 15.0
FOURSQUARE_FREE_CALLS = 500


def google_cost_inr(requests: int, usd_inr: float, tax_rate: float, already_used: int = 0) -> float:
    billable = max(0, requests - max(0, GOOGLE_ENTERPRISE_FREE_PER_MONTH - already_used))
    return billable / 1000 * GOOGLE_TEXT_SEARCH_ENTERPRISE_USD_PER_1000 * usd_inr * (1 + tax_rate)


def estimate_table(usd_inr: float, tax_rate: float, sizes=(1000, 5000, 10000)) -> list[dict]:
    rows = []
    for n in sizes:
        g_req = int(n / (GOOGLE_RESULTS_PER_REQUEST * GOOGLE_NEW_RECORD_EFFICIENCY)) + 1
        fsq_calls = n  # ASSUMPTION: roughly one billable call per record returned
        fsq_usd = max(0, fsq_calls - FOURSQUARE_FREE_CALLS) / 1000 * FOURSQUARE_PRO_USD_PER_1000
        rows.append({
            "records": n,
            "overture_inr": 0.0,
            "osm_overpass_inr": 0.0,
            "website_enrichment_inr": 0.0,
            "google_requests": g_req,
            "google_inr": round(google_cost_inr(g_req, usd_inr, tax_rate)),
            "licensed_provider_example_inr": round(fsq_usd * usd_inr * (1 + tax_rate)),
        })
    return rows


def format_table(rows: list[dict], usd_inr: float, tax_rate: float) -> str:
    out = [f"Assumptions: 1 USD = Rs {usd_inr}, tax {tax_rate:.0%} (both ASSUMPTIONS - edit .env).",
           "| Records | Overture | OSM/Overpass | Site enrichment | Google (requests -> Rs) | Licensed provider example (Rs) |",
           "|---|---|---|---|---|---|"]
    for r in rows:
        out.append(f"| {r['records']:,} | Rs 0 | Rs 0 | Rs 0 (own PC) | {r['google_requests']} -> Rs {r['google_inr']:,} | Rs {r['licensed_provider_example_inr']:,} |")
    return "\n".join(out)
