# Low-Cost Business Lead Collector

Collects business **name, phone, website, category, city/address and source** for a city + category,
cleans and de-duplicates them, optionally reads publicly listed phone numbers from each business's own
website, and exports a CSV (and optionally PostgreSQL). Built to cost ~Rs 0 for a prototype and to stay
inside each source's terms.

**What it deliberately does not do:** scrape Google Maps pages, bypass logins/CAPTCHAs/robots.txt, invent
data, or claim a phone number is active. Phone status is a *format check only*.

## Which source should I use?

| Source | Cost | Phone/website coverage | Notes |
|---|---|---|---|
| `overture` (default) | Free | Varies by country - **measure in the pilot** | Open dataset, attribution required. Best zero-cost start. |
| `osm` | Free | Often thin in India - measure | Public server has fair-use limits. ODbL licence. |
| `csv` | Depends | Depends | Import a licensed provider's export or your own list. |
| `google` | Pay-per-request after a small free cap | High for phone/website | **Optional.** Terms restrict storing/using the data. Off unless `--accept-google-terms`. Read `docs/SOURCES.md`. |

Details, links and verified-vs-estimated notes: `docs/SOURCES.md`. Costs for 1,000 / 5,000 / 10,000 records: `docs/COSTS.md`.

## Flowchart

```mermaid
flowchart TD
    A[CLI input: city, category, target, source] --> B{Source}
    B -->|overture| C1[Overture Maps via DuckDB]
    B -->|osm| C2[Overpass API]
    B -->|csv| C3[Licensed/own CSV export]
    B -->|google, optional, capped| C4[Places API]
    C1 & C2 & C3 & C4 --> D[Normalise: E.164 phones, clean URLs, names]
    D --> E[Deduplicate: phone, domain, name + location]
    E --> F[(stage1_collected.jsonl checkpoint)]
    F --> G{Website known and robots.txt allows?}
    G -->|yes| H[Fetch homepage + up to 2 contact pages, extract tel: numbers]
    G -->|no| I[Mark status: missing / robots_disallowed / social]
    H --> J[(stage2_enriched.jsonl checkpoint)]
    I --> J
    J --> K[Validate: phone format, URL reachability]
    K --> L[Deduplicate again + filters]
    L --> M[leads.csv]
    L --> N[(PostgreSQL, optional)]
    L --> O[report.json / report.md: coverage, duplicates, failures, cost]
```

## Quick start on Windows (PowerShell)

1. Install Python 3.10+ from python.org (tick "Add Python to PATH").
2. In the project folder:
   ```powershell
   py -m venv .venv
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   copy .env.example .env
   notepad .env        # set CONTACT_EMAIL to your real email
   ```
   If activation is blocked: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.
3. Run the tests (no internet needed):
   ```powershell
   pip install pytest
   python -m pytest -q
   ```
4. **Pilot** (about 150 businesses, with pass/fail against your quality targets):
   ```powershell
   python -m leadcollector run --source overture --city Ludhiana --state Punjab --category jewellers --pilot
   ```
   Output goes to `data\<run-name>\leads.csv` plus `report.md`. The first Overture run reads from the
   public S3 release and needs internet; if the release name in `.env` is out of date, pick a current one at
   https://docs.overturemaps.org/ and set `OVERTURE_RELEASE`.
5. Scale up only if the pilot report meets your targets:
   ```powershell
   python -m leadcollector run --source overture --city Ludhiana --state Punjab --category jewellers --target 2000 --require-phone
   ```

### Other useful commands

```powershell
python -m leadcollector categories                                   # built-in categories
python -m leadcollector overture-categories --city Ludhiana --state Punjab   # real category names in the area
python -m leadcollector run --source osm --city Chandigarh --category restaurants
python -m leadcollector run --source overture,osm --city Mohali --category real_estate    # combine and dedupe
python -m leadcollector run --source csv --csv-file provider_export.csv --city Punjab --category manufacturers
python -m leadcollector run ... --no-enrich            # never visit business websites
python -m leadcollector run ... --check-urls-only      # check sites respond; do not read phones
python -m leadcollector run ... --resume --run-name <same name>   # continue after an interruption
python -m leadcollector run ... --postgres             # also upsert into PostgreSQL
python -m leadcollector costs --usd-inr 90             # cost table
```

Any category name works: for OSM add `--osm-filter key=value` (see the OSM Map Features wiki); for Overture
use `overture-categories` to see real names and pass `--overture-term`.

## Output columns

`business_name, phone, website, category, city, address, source, source_id, source_url, attribution,
phone_status, website_status, verification_status, phone_source, extra_phones, collected_at, lead_key`

- `phone` is E.164 (`+91...`). Blank means not found - nothing is guessed.
- `phone_source` says where the number came from (`overture`, `osm`, `website:<domain>`, ...).
- `website_status`: `reachable`, `unreachable`, `error_<code>`, `robots_disallowed`, `social_or_directory_page`, `missing`, `not_checked`.
- `verification_status` always ends with `ownership_and_active_status_not_verified`.
- Keep the `attribution` column (Overture/OSM require credit when you publish or share the data).

A labelled example: `samples/sample_output_ILLUSTRATIVE.csv` (synthetic records, not real businesses).

## Project layout

```
leadcollector/
  cli.py          command line               pipeline.py   orchestration + checkpoints
  sources/        overture, osm_overpass, google_places, csv_import (add new ones here)
  normalize.py    phones/URLs/names           dedupe.py     conservative duplicate merging
  enrich.py       website enrichment          validate.py   status fields
  http.py         retries, backoff, rate limits, robots.txt
  storage.py      JSONL checkpoints, CSV, PostgreSQL       report.py / costs.py
sql/schema.sql    PostgreSQL schema           tests/        offline test-suite
```

**Adding a source:** subclass `Source` (see `sources/base.py`), yield `Lead` objects, register it in
`sources/__init__.py`. Nothing else changes.

## PostgreSQL (optional)

```powershell
pip install -r requirements-optional.txt
# in .env: POSTGRES_DSN=postgresql://user:password@localhost:5432/leads
python -m leadcollector run ... --postgres
```
The table (`sql/schema.sql`) is created automatically; rows are upserted on `lead_key`, so re-runs update
rather than duplicate.

## Reliability, errors and resuming

- Every HTTP call has a timeout, up to `MAX_RETRIES` retries with exponential backoff + jitter, and honours `Retry-After`.
- Requests to the same host are spaced by `RATE_LIMIT_SECONDS`; different sites are processed in parallel (`WORKERS`).
- A site that fails never stops the run. Failures are counted in the report (`failed_requests`).
- Collection and enrichment are checkpointed in `data\<run>\*.jsonl`; use `--resume --run-name <name>`.
- Logs: `data\<run>\run.log`. URLs are logged without query strings; API keys are only read from environment variables and are never written to logs or output.

## Pilot, quality control and scaling

Run `--pilot` first. The report shows: businesses found, % with phone, % with website, % with both,
duplicate rate, invalid-URL rate, and cost per record with a phone. Targets come from `.env`
(`MIN_PHONE_PCT`, ...) - the defaults are examples, set your own. Scale only after the pilot passes.

Scaling notes:
- 1,000-10,000 records works on one PC; enrichment is the slow part (roughly one request per site per second per host, parallel across sites).
- For OSM at scale, do not loop the public Overpass server over many small areas; use one query per city, or a regional extract / your own Overpass instance.
- For Overture, widen the bounding box or run several cities; data is read directly from the open release.
- Re-check each source's current terms before commercial use; `docs/SOURCES.md` lists what was and was not verified.

## Legal and ethical notes

Public availability is not consent to be marketed to. Use leads that are *business* contact details, honour opt-outs, and confirm the lawful basis and channel rules (calls, SMS, WhatsApp) before outreach. This tool does not provide legal advice.

## Web interface (optional)

```powershell
python server.py
```
Opens http://127.0.0.1:8000. Pick source, state, city, category and limits, start a search, watch the live log and
progress, then browse, filter, sort and download the CSV. The left column lists saved datasets (folders in `data\`)
with a delete button. The server only listens on your own computer and runs one search at a time.
