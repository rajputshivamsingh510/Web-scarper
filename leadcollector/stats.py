"""Thread-safe counters used for the final report."""
from __future__ import annotations

import threading
from dataclasses import dataclass, fields


@dataclass
class Stats:
    requests: int = 0
    failed_requests: int = 0
    google_requests: int = 0
    raw_collected: int = 0
    duplicates_merged: int = 0
    urls_checked: int = 0
    urls_unreachable: int = 0
    robots_skipped: int = 0
    candidates: int = 0
    candidates_with_phone: int = 0
    candidates_with_website: int = 0
    candidates_with_both: int = 0

    def __post_init__(self) -> None:
        self._lock = threading.Lock()

    def add(self, name: str, n: int = 1) -> None:
        with self._lock:
            setattr(self, name, getattr(self, name) + n)

    def as_dict(self) -> dict:
        return {f.name: getattr(self, f.name) for f in fields(self)}
