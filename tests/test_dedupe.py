from leadcollector.dedupe import dedupe
from leadcollector.models import Lead
from conftest import EXAMPLE_PHONE


def L(**kw):
    return Lead(**kw)


def test_same_phone_similar_name_merges_and_fills_blanks():
    a = L(business_name="Sample Jewellers", phone=EXAMPLE_PHONE, source="s1", source_id="1")
    b = L(business_name="Sample Jewellers Pvt Ltd", website="https://example.com", source="s2", source_id="9")
    c = L(business_name="Sample Jewellers", phone=EXAMPLE_PHONE, website="https://example.com", address="1 Road")
    out, merged = dedupe([a, b, c])
    assert merged >= 1
    best = max(out, key=lambda l: l.completeness())
    assert best.website == "https://example.com" and best.phone == EXAMPLE_PHONE


def test_different_branches_are_not_merged():
    a = L(business_name="City Jewellers", phone="+911612000001", website="https://chain.example", address="Mall Road", lat=30.9, lon=75.8)
    b = L(business_name="City Jewellers", phone="+911612000002", website="https://chain.example", address="Station Road", lat=30.95, lon=75.9)
    out, merged = dedupe([a, b])
    assert merged == 0 and len(out) == 2


def test_same_name_without_corroboration_is_kept():
    a = L(business_name="HP Petrol Pump")
    b = L(business_name="HP Petrol Pump")
    assert dedupe([a, b])[1] == 0


def test_close_by_same_name_merges():
    a = L(business_name="Gupta Clinic", lat=30.9000, lon=75.8000, source="osm", source_id="1")
    b = L(business_name="Gupta Clinic", lat=30.9005, lon=75.8001, source="overture", source_id="2")
    out, merged = dedupe([a, b])
    assert merged == 1 and out[0].source == "osm;overture"
