from leadcollector import categories
from leadcollector.http import HttpClient
from leadcollector.sources.base import SearchSpec
from leadcollector.sources.csv_import import CsvSource
from leadcollector.sources.osm_overpass import build_query, parse_elements
from leadcollector.sources.overture import OvertureSource
from leadcollector.stats import Stats
from conftest import EXAMPLE_PHONE


def test_overture_local_parquet(cfg, overture_parquet):
    cfg.overture_path = overture_parquet
    src = OvertureSource(cfg, HttpClient("t"), Stats())
    spec = SearchSpec("Testville", "", categories.resolve("jewellers"), bbox=(30.0, 75.0, 31.5, 76.5))
    leads = list(src.collect(spec, 50))
    names = {l.business_name for l in leads}
    assert len(leads) == 3                       # closed, restaurant and out-of-area rows excluded
    assert "Sample Closed Shop (synthetic)" not in names
    first = next(l for l in leads if l.source_id == "id-1")
    assert first.phone == EXAMPLE_PHONE and first.website == "https://www.example.com"
    assert "Overture Maps" in first.attribution


def test_overpass_query_and_parse():
    q = build_query(["shop=jewelry"], city="Ludhiana")
    assert 'area["name"="Ludhiana"]' in q and 'nwr(area.a)["shop"="jewelry"]["name"]' in q
    assert "out tags center" in build_query(["amenity=fuel"], bbox=(1, 2, 3, 4))
    els = [{"type": "node", "id": 1, "lat": 1.0, "lon": 2.0,
            "tags": {"name": "A Jewellers", "contact:phone": EXAMPLE_PHONE, "website": "a.example.com"}},
           {"type": "way", "id": 2, "center": {"lat": 1, "lon": 2}, "tags": {"shop": "jewelry"}}]
    leads = parse_elements(els, "Jewellers", "Ludhiana")
    assert len(leads) == 1 and leads[0].phone == EXAMPLE_PHONE and leads[0].source_id == "node/1"


def test_csv_source_autodetects_columns(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("Company,Mobile,Site\nAcme Traders,12345,acme.example.com\n", "utf-8")
    spec = SearchSpec("X", "", categories.resolve("wholesalers"), csv_path=str(f))
    leads = list(CsvSource(None, None, Stats()).collect(spec, 10))
    assert leads[0].business_name == "Acme Traders" and leads[0].website == "acme.example.com"


def test_google_requires_explicit_acceptance(cfg):
    from leadcollector.sources.google_places import GooglePlacesSource
    import pytest
    spec = SearchSpec("X", "", categories.resolve("jewellers"))
    with pytest.raises(PermissionError):
        list(GooglePlacesSource(cfg, HttpClient("t"), Stats()).collect(spec, 5))


def test_category_resolution_and_custom():
    assert categories.resolve("Jewellery").key == "jewellers"
    c = categories.resolve("Gem Testing Labs")
    assert c.overture == ["gem_testing_labs"] and c.osm == []
