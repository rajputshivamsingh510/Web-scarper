-- Optional PostgreSQL schema (used by --postgres; created automatically if missing).
CREATE TABLE IF NOT EXISTS business_leads (
    lead_key            TEXT PRIMARY KEY,
    business_name       TEXT NOT NULL,
    phone               TEXT,
    website             TEXT,
    category            TEXT,
    city                TEXT,
    address             TEXT,
    source              TEXT,
    source_id           TEXT,
    source_url          TEXT,
    attribution         TEXT,
    phone_status        TEXT,
    website_status      TEXT,
    verification_status TEXT,
    phone_source        TEXT,
    extra_phones        TEXT,
    collected_at        TIMESTAMPTZ,
    first_seen          TIMESTAMPTZ DEFAULT now(),
    last_seen           TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_leads_phone ON business_leads (phone);
CREATE INDEX IF NOT EXISTS idx_leads_city_category ON business_leads (city, category);
