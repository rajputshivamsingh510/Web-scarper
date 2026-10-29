"""Source registry. To add a source: subclass Source and add it here."""
from .csv_import import CsvSource
from .google_places import GooglePlacesSource
from .osm_overpass import OverpassSource
from .overture import OvertureSource

REGISTRY = {s.name: s for s in (OvertureSource, OverpassSource, GooglePlacesSource, CsvSource)}


def get_source(name: str):
    try:
        return REGISTRY[name]
    except KeyError:
        raise SystemExit(f"Unknown source '{name}'. Choose from: {', '.join(REGISTRY)}")
