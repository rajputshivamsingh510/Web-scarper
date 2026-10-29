"""Configuration from environment variables (optionally a .env file)."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv is optional at runtime
    load_dotenv = None

log = logging.getLogger("leadcollector.config")


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return float(default)


@dataclass
class Config:
    contact_email: str
    user_agent: str
    google_key: str
    google_max_requests: int
    overpass_url: str
    overture_release: str
    overture_path: str
    postgres_dsn: str
    timeout: float
    max_retries: int
    rate_limit_seconds: float
    workers: int
    data_dir: Path
    usd_inr: float
    tax_rate: float
    min_phone_pct: float
    min_website_pct: float
    min_both_pct: float
    max_invalid_url_pct: float


def load_config() -> Config:
    if load_dotenv:
        load_dotenv()
    email = os.getenv("CONTACT_EMAIL", "").strip()
    if not email or email.endswith("@example.com"):
        log.warning("CONTACT_EMAIL is not set. Set it in .env so servers can contact you.")
    ua = os.getenv("USER_AGENT") or f"LeadCollector/1.0 (+mailto:{email or 'set-CONTACT_EMAIL'})"
    return Config(
        contact_email=email,
        user_agent=ua,
        google_key=os.getenv("GOOGLE_PLACES_API_KEY", ""),
        google_max_requests=int(_f("GOOGLE_MAX_REQUESTS", 900)),
        overpass_url=os.getenv("OVERPASS_URL", "https://overpass-api.de/api/interpreter"),
        overture_release=os.getenv("OVERTURE_RELEASE", "2026-09-23.1"),
        overture_path=os.getenv("OVERTURE_PATH", ""),
        postgres_dsn=os.getenv("POSTGRES_DSN", ""),
        timeout=_f("REQUEST_TIMEOUT", 20),
        max_retries=int(_f("MAX_RETRIES", 4)),
        rate_limit_seconds=_f("RATE_LIMIT_SECONDS", 1.0),
        workers=int(_f("WORKERS", 6)),
        data_dir=Path(os.getenv("DATA_DIR", "data")),
        usd_inr=_f("USD_INR", 90),
        tax_rate=_f("TAX_RATE", 0.18),
        min_phone_pct=_f("MIN_PHONE_PCT", 40),
        min_website_pct=_f("MIN_WEBSITE_PCT", 30),
        min_both_pct=_f("MIN_BOTH_PCT", 20),
        max_invalid_url_pct=_f("MAX_INVALID_URL_PCT", 25),
    )
