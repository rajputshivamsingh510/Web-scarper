"""Orchestration: collect -> normalise -> dedupe -> enrich -> validate -> store -> report."""
from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from . import categories
from .config import Config
from .dedupe import dedupe
from .enrich import enrich_lead
from .http import HttpClient, RobotsCache
from .models import Lead
from .normalize import normalize_phone, normalize_url
from .report import build_report, write_report
from .sources import get_source
from .sources.base import SearchSpec
from .stats import Stats
from .storage import EnrichmentCheckpoint, read_jsonl, upsert_postgres, write_csv, write_jsonl
from .validate import finalize

log = logging.getLogger("leadcollector.pipeline")
SCHEMA = Path(__file__).resolve().parent.parent / "sql" / "schema.sql"


@dataclass
class RunOptions:
    sources: list[str]
    category: str
    city: str = ""
    state: str = ""
    target: int = 200
    bbox: tuple | None = None
    osm_filters: list[str] = field(default_factory=list)
    overture_terms: list[str] = field(default_factory=list)
    google_queries: list[str] = field(default_factory=list)
    localities: list[str] = field(default_factory=list)
    csv_file: str = ""
    csv_map: dict = field(default_factory=dict)
    min_confidence: float = 0.0
    enrich: bool = True
    check_urls_only: bool = False
    js_fallback: bool = False
    require_phone: bool = False
    require_website: bool = False
    resume: bool = False
    run_name: str = ""
    out: str = ""
    postgres: bool = False
    accept_google_terms: bool = False
    pilot: bool = False


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def normalize_lead(l: Lead) -> Lead:
    l.business_name = " ".join(l.business_name.split())
    l.website = normalize_url(l.website)
    l.phone, _ = normalize_phone(l.phone) if l.phone else ("", "missing")
    l.lead_key = l.compute_key()
    return l


def _rank(l: Lead):
    return (-bool(l.phone), -bool(l.website), -(l.confidence or 0.0))


def run_pipeline(cfg: Config, opt: RunOptions) -> dict:
    stats = Stats()
    run_name = opt.run_name or _slug(f"{'+'.join(opt.sources)}-{opt.city}-{opt.category}")
    run_dir = cfg.data_dir / run_name
    run_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logging.getLogger().addHandler(fh)
    try:
        client = HttpClient(cfg.user_agent, cfg.timeout, cfg.max_retries, cfg.rate_limit_seconds, stats=stats)
        robots = RobotsCache(client)
        stage1 = run_dir / "stage1_collected.jsonl"

        # 1-3. collect -> normalise -> dedupe (checkpointed)
        if opt.resume and stage1.exists():
            leads = read_jsonl(stage1)
            log.info("Resuming: loaded %d collected leads", len(leads))
        else:
            cat = categories.resolve(opt.category, opt.osm_filters, opt.overture_terms, opt.google_queries)
            spec = SearchSpec(city=opt.city, state=opt.state, category=cat, bbox=opt.bbox,
                              localities=opt.localities, min_confidence=opt.min_confidence,
                              csv_path=opt.csv_file, csv_map=opt.csv_map,
                              accept_google_terms=opt.accept_google_terms)
            raw: list[Lead] = []
            limit = int(opt.target * 1.5) + 10
            for name in opt.sources:
                src = get_source(name)(cfg, client, stats)
                got = list(src.collect(spec, limit))
                log.info("Source %s returned %d records", name, len(got))
                raw.extend(got)
            stats.raw_collected = len(raw)
            raw = [normalize_lead(l) for l in raw]
            leads, merged = dedupe(raw)
            stats.add("duplicates_merged", merged)
            stats.candidates = len(leads)
            stats.candidates_with_phone = sum(bool(l.phone) for l in leads)
            stats.candidates_with_website = sum(bool(l.website) for l in leads)
            stats.candidates_with_both = sum(bool(l.phone and l.website) for l in leads)
            leads.sort(key=_rank)
            leads = leads[: opt.target]
            for l in leads:
                l.lead_key = l.compute_key()
            write_jsonl(stage1, leads)

        # 4. enrich websites + check URLs (resumable, polite, parallel across hosts)
        if opt.enrich or opt.check_urls_only:
            ckpt = EnrichmentCheckpoint(run_dir / "stage2_enriched.jsonl", opt.resume)
            todo = [l for l in leads if l.lead_key not in ckpt.done]
            log.info("Enriching %d leads (%d already done)", len(todo), len(leads) - len(todo))
            with ThreadPoolExecutor(max_workers=max(1, cfg.workers)) as ex:
                futs = {ex.submit(enrich_lead, l, client, robots, not opt.check_urls_only,
                                  3, opt.js_fallback): l.lead_key for l in todo}
                for fut in as_completed(futs):
                    key = futs[fut]
                    try:
                        ckpt.save(key, fut.result())
                    except Exception as exc:  # one bad site must not stop the run
                        log.warning("Enrichment error for key %s: %s", key, type(exc).__name__)
            leads = [ckpt.done.get(l.lead_key, l) for l in leads]

        # 5. validate, dedupe again (new phones can reveal duplicates), filter
        leads = [finalize(l) for l in leads]
        leads, merged = dedupe(leads)
        stats.add("duplicates_merged", merged)
        if opt.require_phone:
            leads = [l for l in leads if l.phone]
        if opt.require_website:
            leads = [l for l in leads if l.website]
        for l in leads:
            l.lead_key = l.compute_key()
            finalize(l)

        # 6. store + report
        out_csv = run_dir / "leads.csv"
        write_csv(out_csv, leads)
        if opt.out:
            write_csv(Path(opt.out), leads)
        if opt.postgres:
            if not cfg.postgres_dsn:
                raise SystemExit("Set POSTGRES_DSN in .env to use --postgres")
            log.info("Upserted %d rows into PostgreSQL", upsert_postgres(cfg.postgres_dsn, leads, SCHEMA))
        meta = {"name": run_name, "sources": opt.sources, "city": opt.city, "category": opt.category,
                "target": opt.target, "csv": str(out_csv)}
        rep = build_report(leads, stats, cfg, meta, opt.pilot)
        write_report(run_dir, rep)
        return rep
    finally:
        logging.getLogger().removeHandler(fh)
        fh.close()
