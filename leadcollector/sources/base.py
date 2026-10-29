from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..categories import Category
from ..config import Config
from ..http import HttpClient
from ..models import Lead
from ..stats import Stats


@dataclass
class SearchSpec:
    city: str
    state: str
    category: Category
    bbox: tuple[float, float, float, float] | None = None  # south, west, north, east
    localities: list[str] = field(default_factory=list)
    min_confidence: float = 0.0
    csv_path: str = ""
    csv_map: dict = field(default_factory=dict)
    accept_google_terms: bool = False


class Source:
    """Add a new data source by subclassing this and registering it in sources/__init__.py."""

    name = ""

    def __init__(self, cfg: Config, client: HttpClient, stats: Stats):
        self.cfg, self.client, self.stats = cfg, client, stats

    def collect(self, spec: SearchSpec, limit: int) -> Iterable[Lead]:
        raise NotImplementedError
