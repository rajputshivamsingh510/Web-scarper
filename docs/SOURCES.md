# Data sources: comparison, terms and links

Researched 28 Oct 2026. **Verified** = read in the provider's own documentation or in multiple consistent sources.
**Third-party/unverified** = reported by blogs or marketplaces; confirm before budgeting. Prices and terms change.

## A. Google Places API (optional; not recommended as your own lead database)

- Pricing model (verified in Google's SKU categories, consistent across several sources): per-SKU free monthly caps since March 2025 - Essentials 10,000, Pro 5,000, Enterprise 1,000 events. https://developers.google.com/maps/billing-and-pricing/pricing-categories
- Phone number and website are **Enterprise-tier** fields (billed at the highest SKU of the fields you request). Third-party price tables list Text Search Enterprise at **USD 35 per 1,000 requests** (Pro: USD 32; Place Details Pro: USD 17). Confirm on Google's pricing page before relying on them. https://openplacesapi.com/blog/google-places-api-pricing
- A text search returns up to 20 places per request and at most 60 results per query (third-party-reported).
- Terms: Google's Service Specific Terms allow caching of `place_id` values and only temporary caching (up to 30 days) of latitude/longitude from the Places API; they also require attribution when Places content is shown without a Google map. https://cloud.google.com/maps-platform/terms/maps-service-terms/ . Google's general terms also restrict exporting or storing Maps content for use outside Google's services - **a free allowance is not permission to build an independent lead database.** Read the current terms and, if unsure, ask Google or a lawyer.
- No India-specific price list or INR rate was found in Google's public docs during research; this project converts USD at an editable assumption.
- In this project: off by default, requires `--accept-google-terms`, stops at `GOOGLE_MAX_REQUESTS` (default 900, below the Enterprise free cap).

## B. OpenStreetMap + Overpass API (free)

- Overpass guidance (verified, OSM wiki): fine for one-off use under about 10,000 queries/day and 1 GB/day; if used regularly, divide by 100; no parallel scripts; commercial use should use self-hosted or paid servers; cache and use extracts for large data. https://wiki.openstreetmap.org/wiki/Overpass_API and https://dev.overpass-api.de/overpass-doc/en/preface/commons.html
- Tags used: `name`, `phone`, `contact:phone`, `contact:mobile`, `website`, `contact:website`, `shop`, `office`, `amenity`, `industrial`, `tourism`.
- Coverage: **not verified for Ludhiana/Punjab.** Phone and website tags are volunteer-entered and usually incomplete; the pilot report will show the real percentage.
- Licence: ODbL 1.0 - keep "(c) OpenStreetMap contributors" attribution and check share-alike rules for derived databases. https://www.openstreetmap.org/copyright (not re-fetched during this research).
- Nominatim (used once per city for a bounding box): max 1 request/second, identify yourself. https://operations.osmfoundation.org/policies/nominatim/ (not re-fetched).

## C. Website enrichment with requests + BeautifulSoup (free)

- Visits only the business's own site; honours robots.txt; max 3 pages per site; no logins/CAPTCHA bypass; skips social and directory pages.
- Playwright (`--js-fallback`) only when a page needs JavaScript, and only where robots.txt allows it.
- Each website's own terms still apply; the tool cannot read them for you.

## D. Open dataset: Overture Maps Places (free) - recommended first source

- Open places dataset with names, categories, phones, websites, addresses, confidence and operating status; released monthly. https://docs.overturemaps.org/guides/places
- Licence: mostly CDLA-Permissive-2.0 (Meta, Microsoft and others), some sources Apache-2.0 or CC0; attribution to Overture required. https://docs.overturemaps.org/attribution/
- Read directly from the public release with DuckDB; no API key, no per-request fee.
- Field coverage varies by country (reported by third parties as strong in North America/Western Europe). **India coverage is not verified - measure with the pilot.**
- Do not mix with OSM data in one published database without checking ODbL share-alike (Overture's own docs warn about this).

## E. Licensed providers / paid datasets

- Foursquare Places API: a third-party article reports pay-as-you-go pricing, free for the first ~500 calls then about USD 15 per 1,000 for Pro endpoints (https://apiserpent.com/blog/free-google-maps-api). **Unverified**, and phone/website may sit in a higher tier. Check https://foursquare.com/ pricing.
- Indian directories (JustDial, IndiaMART, Sulekha) have no open API in this research; scraping them breaks their terms. Use a licensed export through `--source csv` if you buy one.
- When comparing providers ask: price per *useful* record, export/commercial-use rights, freshness, India coverage, API limits.

## Recommendation (lowest-cost compliant architecture)

1. Pilot with **Overture** (free, exportable) for the city/category.
2. Add **OSM** for gaps; enrich missing phones from **official business websites**.
3. If the pilot's phone coverage is too low, buy a **licensed export** and load it with `--source csv`.
4. Use **Google** only for small verification checks, within its terms and the capped budget.
