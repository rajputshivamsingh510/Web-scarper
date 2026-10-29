from leadcollector.enrich import contact_links, enrich_lead, extract_phones
from leadcollector.http import HttpClient, RobotsCache
from leadcollector.models import Lead
from conftest import EXAMPLE_PHONE


def test_extract_phones_from_tel_and_text():
    html = f'<a href="tel:{EXAMPLE_PHONE}">x</a><p>Office: {EXAMPLE_PHONE[3:]}</p><script>1234567890</script>'
    assert extract_phones(html) == [EXAMPLE_PHONE]


def test_contact_links_same_domain_only():
    html = '<a href="/contact">Contact</a><a href="https://other.com/contact">Contact</a>'
    assert contact_links(html, "https://example.com") == ["https://example.com/contact"]


def test_enrich_follows_contact_page(local_site):
    client = HttpClient("LeadCollector/test", timeout=5, max_retries=0, min_interval=0)
    robots = RobotsCache(client)
    lead = enrich_lead(Lead(business_name="Test", website=local_site), client, robots)
    assert lead.website_status == "reachable"
    assert lead.phone == EXAMPLE_PHONE and lead.phone_source.startswith("website:")


def test_robots_disallow_is_respected(local_site):
    client = HttpClient("LeadCollector/test", timeout=5, max_retries=0, min_interval=0)
    lead = enrich_lead(Lead(business_name="T", website=local_site + "/private"), client, RobotsCache(client))
    assert lead.website_status == "robots_disallowed" and not lead.phone


def test_unreachable_site_is_reported():
    client = HttpClient("LeadCollector/test", timeout=2, max_retries=0, min_interval=0)
    lead = enrich_lead(Lead(business_name="T", website="http://127.0.0.1:9"), client, RobotsCache(client))
    assert lead.website_status == "unreachable"


def test_social_pages_are_not_visited():
    client = HttpClient("LeadCollector/test", max_retries=0, min_interval=0)
    lead = enrich_lead(Lead(business_name="T", website="https://facebook.com/x"), client, RobotsCache(client))
    assert lead.website_status == "social_or_directory_page" and client.stats.requests == 0
