"""Phone / URL / name normalisation. Pure functions, no network."""
from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import phonenumbers

SOCIAL_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com",
    "youtube.com", "wa.me", "wa.link", "tiktok.com", "t.me", "pinterest.com", "bit.ly",
}
# Directory/aggregator sites: a listing there is not the business's own website.
AGGREGATOR_DOMAINS = {
    "justdial.com", "indiamart.com", "sulekha.com", "tripadvisor.com", "zomato.com",
    "swiggy.com", "yahoo.in", "yahoo.com", "gmail.com", "outlook.com", "hotmail.com", "google.com", "goo.gl", "business.site", "linktr.ee",
}
_NAME_STOPWORDS = {"pvt", "ltd", "private", "limited", "llp", "the", "and", "co", "company", "inc"}
_TRACKING = ("utm_", "fbclid", "gclid", "mc_", "ref")


def normalize_phones(raw, region: str = "IN") -> list[str]:
    """Return every valid number found in `raw` as E.164 (no duplicates)."""
    if not raw:
        return []
    if isinstance(raw, (list, tuple)):
        raw = ";".join(str(x) for x in raw if x)
    out: list[str] = []
    for part in re.split(r"[;,/|]|\bor\b", str(raw)):
        part = part.strip()
        if not part:
            continue
        try:
            num = phonenumbers.parse(part, region)
        except phonenumbers.NumberParseException:
            continue
        if phonenumbers.is_valid_number(num):
            e164 = phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)
            if e164 not in out:
                out.append(e164)
    return out


def normalize_phone(raw, region: str = "IN") -> tuple[str, str]:
    """-> (e164 or "", status). Status is about FORMAT only, never activity."""
    if not raw or (isinstance(raw, (list, tuple)) and not any(raw)):
        return "", "missing"
    phones = normalize_phones(raw, region)
    if phones:
        return phones[0], "format_valid"
    return "", "invalid_format"


def normalize_url(raw) -> str:
    if not raw:
        return ""
    raw = str(raw).strip()
    if not raw or " " in raw:
        return ""
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    try:
        parts = urlsplit(raw)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return ""
    if not host or "." not in host:
        return ""
    netloc = host + (f":{port}" if port else "")
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query)
                       if not k.lower().startswith(_TRACKING)])
    path = "" if parts.path in ("", "/") else parts.path.rstrip("/")
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def domain_of(url: str) -> str:
    if not url:
        return ""
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _matches(domain: str, group: set[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in group)


def is_social(url: str) -> bool:
    return _matches(domain_of(url), SOCIAL_DOMAINS)


def is_aggregator(url: str) -> bool:
    return _matches(domain_of(url), AGGREGATOR_DOMAINS)


def normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.lower().replace("&", " and ")
    s = re.sub(r"[^\w\s]", " ", s)
    return " ".join(t for t in s.split() if t not in _NAME_STOPWORDS)
