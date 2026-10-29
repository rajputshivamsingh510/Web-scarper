"""JSONL checkpoints (resume), CSV export and optional PostgreSQL."""
from __future__ import annotations

import json
import threading
from dataclasses import asdict
from pathlib import Path

import pandas as pd

from .models import CSV_COLUMNS, Lead


def write_jsonl(path: Path, leads: list[Lead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for l in leads:
            fh.write(json.dumps(asdict(l), ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[Lead]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return [Lead.from_dict(json.loads(line)) for line in fh if line.strip()]


class EnrichmentCheckpoint:
    """Append-only file of enriched leads keyed by their pre-enrichment key."""

    def __init__(self, path: Path, resume: bool):
        self.path = path
        self._lock = threading.Lock()
        self.done: dict[str, Lead] = {}
        if resume and path.exists():
            with path.open(encoding="utf-8") as fh:
                for line in fh:
                    if line.strip():
                        rec = json.loads(line)
                        self.done[rec["key"]] = Lead.from_dict(rec["lead"])
        elif path.exists():
            path.unlink()

    def save(self, key: str, lead: Lead) -> None:
        with self._lock:
            self.done[key] = lead
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"key": key, "lead": asdict(lead)}, ensure_ascii=False) + "\n")


def write_csv(path: Path, leads: list[Lead]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([l.to_row() for l in leads], columns=CSV_COLUMNS)
    df.to_csv(path, index=False, encoding="utf-8-sig")  # utf-8-sig opens cleanly in Excel on Windows


def upsert_postgres(dsn: str, leads: list[Lead], schema_path: Path) -> int:
    try:
        import psycopg
    except ImportError as exc:
        raise SystemExit("Install PostgreSQL support: pip install -r requirements-optional.txt") from exc
    cols = [c for c in CSV_COLUMNS if c != "lead_key"]
    sql = (
        f"INSERT INTO business_leads (lead_key, {', '.join(cols)}) "
        f"VALUES (%s, {', '.join(['%s'] * len(cols))}) "
        "ON CONFLICT (lead_key) DO UPDATE SET "
        + ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c != "collected_at")
        + ", last_seen = now()"
    )
    rows = []
    for l in leads:
        row = l.to_row()
        rows.append([row["lead_key"]] + [row[c] or None for c in cols])
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(schema_path.read_text("utf-8"))
            cur.executemany(sql, rows)
    return len(rows)
