"""Website enrichment: check the site responds and read publicly listed phone numbers.

Rules: robots.txt is honoured, one request per host per RATE_LIMIT_SECONDS, at most
`max_pages` pages per site, no logins/CAPTCHAs/bypasses. Only the business's own site
is visited (social profiles and directory listings are skipped).
"""
from __future__ import annotations

import logging
from urllib.parse import unquote, urljoin, urlsplit

import phonenumbers
from bs4 import BeautifulSoup

from .http import HttpClient, RobotsCache, RequestFailed
from .models import Lead
from .normalize import domain_of, is_aggregator, is_social, normalize_phone

log = logging.getLogger("leadcollector.enrich")


def extract_phones(html: str, region: str = "IN", limit: int = 5) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    found: list[str] = []
    for a in soup.select('a[href^="tel:"]'):
        p, _ = normalize_phone(unquote(a["href"][4:]), region)
        if p and p not in found:
            found.append(p)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ")[:300_000]
    for m in phonenumbers.PhoneNumberMatcher(text, region, leniency=phonenumbers.Leniency.VALID):
        p = phonenumbers.format_number(m.number, phonenumbers.PhoneNumberFormat.E164)
        if p not in found:
            found.append(p)
    return found[:limit]


def contact_links(html: str, base_url: str, limit: int = 2) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    base = domain_of(base_url)
    out: list[str] = []
    for a in soup.find_all("a", href=True):
        label = (a.get_text(" ") + " " + a["href"]).lower()
        if "contact" not in label:
            continue
        url = urljoin(base_url, a["href"]).split("#")[0]
        if urlsplit(url).scheme in ("http", "https") and domain_of(url) == base and url not in out and url != base_url:
            out.append(url)
        if len(out) >= limit:
            break
    return out


def _render_js(url: str, timeout_ms: int = 20000) -> str:
    """Optional: Playwright for JavaScript-rendered pages (pip install playwright; playwright install chromium)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms, wait_until="networkidle")
            return page.content()
        finally:
            browser.close()


def _is_html(resp) -> bool:
    return "html" in resp.headers.get("Content-Type", "html").lower()


def enrich_lead(lead: Lead, client: HttpClient, robots: RobotsCache, extract: bool = True,
                max_pages: int = 3, js_fallback: bool = False) -> Lead:
    stats = client.stats
    if not lead.website:
        lead.website_status = "missing"
        return lead
    if is_social(lead.website) or is_aggregator(lead.website):
        lead.website_status = "social_or_directory_page"
        return lead
    rs = robots.status(lead.website)
    if rs == "unreachable":  # http<->https mismatch is common: try the other scheme once
        alt = ("https" if lead.website.startswith("http://") else "http") + "://" + lead.website.split("://", 1)[1]
        if robots.status(alt) != "unreachable":
            lead.website, rs = alt, robots.status(alt)
    if rs == "disallowed":
        lead.website_status = "robots_disallowed"
        stats.add("robots_skipped")
        return lead
    stats.add("urls_checked")
    if rs == "unreachable":
        lead.website_status = "unreachable"
        stats.add("urls_unreachable")
        return lead
    try:
        resp = client.get(lead.website, allow_redirects=True, max_retries=1, timeout=12)
    except RequestFailed:
        lead.website_status = "unreachable"
        stats.add("urls_unreachable")
        return lead
    if resp.status_code >= 400:
        lead.website_status = f"error_{resp.status_code}"
        stats.add("urls_unreachable")
        return lead
    lead.website_status = "reachable"
    if not extract or lead.phone or not _is_html(resp):
        return lead

    pages = [(lead.website, resp.text)]
    phones = extract_phones(resp.text)
    visited = 1
    if not phones:
        for link in contact_links(resp.text, resp.url or lead.website):
            if visited >= max_pages or phones:
                break
            if robots.status(link) != "allowed":
                continue
            try:
                r = client.get(link, allow_redirects=True)
            except RequestFailed:
                continue
            visited += 1
            if r.status_code < 400 and _is_html(r):
                phones = extract_phones(r.text)
                pages.append((link, r.text))
    if not phones and js_fallback:
        try:
            phones = extract_phones(_render_js(lead.website))
        except Exception as exc:  # playwright missing or page failure
            log.warning("JS fallback failed for %s: %s", domain_of(lead.website), type(exc).__name__)
    if phones:
        lead.phone = phones[0]
        lead.phone_source = f"website:{domain_of(lead.website)}"
        lead.extra_phones = ";".join(p for p in phones[1:3] if p != lead.phone)
    return lead
