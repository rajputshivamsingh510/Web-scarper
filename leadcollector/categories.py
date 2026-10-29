"""Business categories and how each one maps onto every data source.

Mappings are starting points. Verify them with the pilot run and extend freely:
  * OSM tags:   https://wiki.openstreetmap.org/wiki/Map_features
  * Overture:   run `python -m leadcollector overture-categories --city <city>`
Unknown category names still work with Google (as a search phrase) and Overture
(as a category substring); for OSM pass --osm-filter key=value explicitly.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Category:
    key: str
    label: str
    osm: list[str] = field(default_factory=list)       # "key=value" selectors
    overture: list[str] = field(default_factory=list)  # substrings of the category name
    google: list[str] = field(default_factory=list)    # text-search phrases


BUILTIN = [
    Category("jewellers", "Jewellers", ["shop=jewelry"], ["jewel"], ["jewellery shop", "jewellers"]),
    Category("restaurants", "Restaurants", ["amenity=restaurant"], ["restaurant"], ["restaurants"]),
    Category("manufacturers", "Manufacturers", ["industrial=factory", "man_made=works"],
             ["manufactur", "factory"], ["manufacturer", "factory"]),
    Category("real_estate", "Real estate agencies", ["office=estate_agent"],
             ["real_estate"], ["real estate agency", "property dealer"]),
    Category("doctors", "Doctors / clinics", ["amenity=doctors", "amenity=clinic", "healthcare=doctor"],
             ["doctor", "clinic", "physician"], ["doctor", "clinic"]),
    Category("hospitals", "Hospitals", ["amenity=hospital"], ["hospital"], ["hospital"]),
    Category("petrol_pumps", "Petrol pumps", ["amenity=fuel"], ["gas_station", "fuel"],
             ["petrol pump", "fuel station"]),
    Category("hotels", "Hotels", ["tourism=hotel"], ["hotel"], ["hotel"]),
    Category("car_showrooms", "Car showrooms", ["shop=car"], ["car_dealer"], ["car showroom"]),
    Category("wholesalers", "Wholesalers", ["shop=wholesale"], ["wholesale"], ["wholesale trader"]),
]

_ALIASES = {
    "jewelers": "jewellers", "jewellery": "jewellers", "jewelry": "jewellers", "jeweller": "jewellers",
    "restaurant": "restaurants", "manufacturer": "manufacturers", "real_estate_agencies": "real_estate",
    "realestate": "real_estate", "real_estate_agency": "real_estate", "doctor": "doctors",
    "clinics": "doctors", "hospital": "hospitals", "petrol_pump": "petrol_pumps", "fuel_stations": "petrol_pumps",
    "hotel": "hotels", "car_showroom": "car_showrooms", "wholesaler": "wholesalers",
}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def resolve(name: str, osm=None, overture=None, google=None) -> Category:
    key = _slug(name)
    key = _ALIASES.get(key, key)
    base = next((c for c in BUILTIN if c.key == key), None)
    cat = Category(base.key, base.label, list(base.osm), list(base.overture), list(base.google)) if base \
        else Category(key, name.strip(), [], [key], [name.strip()])
    if osm:
        cat.osm = list(osm)
    if overture:
        cat.overture = list(overture)
    if google:
        cat.google = list(google)
    return cat
