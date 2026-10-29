"""Command line interface.  Run:  python -m leadcollector --help"""
from __future__ import annotations

import argparse
import json
import logging
import sys

from . import categories
from .config import load_config
from .costs import estimate_table, format_table
from .pipeline import RunOptions, run_pipeline


def _bbox(text: str | None):
    if not text:
        return None
    s, w, n, e = (float(x) for x in text.split(","))
    return s, w, n, e


def _kv(pairs: list[str] | None) -> dict:
    return dict(p.split("=", 1) for p in (pairs or []))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="leadcollector", description="Low-cost business lead collector")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="collect, enrich and export leads")
    r.add_argument("--source", default="overture", help="comma list: overture,osm,google,csv (default overture)")
    r.add_argument("--city", default="")
    r.add_argument("--state", default="")
    r.add_argument("--category", required=True, help="e.g. jewellers, restaurants, manufacturers, real_estate, doctors")
    r.add_argument("--target", type=int, default=None, help="max records (default 200; --pilot default 150)")
    r.add_argument("--bbox", help="south,west,north,east (skips geocoding)")
    r.add_argument("--osm-filter", action="append", help="OSM key=value (repeatable); overrides category default")
    r.add_argument("--overture-term", action="append", help="Overture category substring (repeatable)")
    r.add_argument("--google-query", action="append")
    r.add_argument("--locality", action="append", help="neighbourhood names to widen Google searches")
    r.add_argument("--csv-file")
    r.add_argument("--csv-map", action="append", help="field=column, e.g. business_name=Company")
    r.add_argument("--min-confidence", type=float, default=0.0, help="Overture confidence 0-1")
    r.add_argument("--no-enrich", action="store_true", help="skip all website visits")
    r.add_argument("--check-urls-only", action="store_true", help="check sites respond, do not read phones")
    r.add_argument("--js-fallback", action="store_true", help="use Playwright when a page needs JavaScript")
    r.add_argument("--require-phone", action="store_true")
    r.add_argument("--require-website", action="store_true")
    r.add_argument("--resume", action="store_true", help="continue an interrupted run with the same name")
    r.add_argument("--run-name")
    r.add_argument("--out", help="also copy the CSV to this path")
    r.add_argument("--postgres", action="store_true")
    r.add_argument("--accept-google-terms", action="store_true")
    r.add_argument("--pilot", action="store_true", help="small run + pass/fail against quality targets")

    sub.add_parser("categories", help="list built-in categories")

    o = sub.add_parser("overture-categories", help="show the most common Overture categories in an area")
    o.add_argument("--city", default="")
    o.add_argument("--state", default="")
    o.add_argument("--bbox")

    c = sub.add_parser("costs", help="print the cost comparison table")
    c.add_argument("--usd-inr", type=float)
    c.add_argument("--tax-rate", type=float)
    return p


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    cfg = load_config()

    if args.cmd == "categories":
        for c in categories.BUILTIN:
            print(f"{c.key:15} OSM={c.osm}  Overture={c.overture}")
        return
    if args.cmd == "costs":
        usd = args.usd_inr or cfg.usd_inr
        tax = cfg.tax_rate if args.tax_rate is None else args.tax_rate
        print(format_table(estimate_table(usd, tax), usd, tax))
        return
    if args.cmd == "overture-categories":
        from .geocode import bbox_for
        from .http import HttpClient
        from .sources.overture import list_categories
        bbox = _bbox(args.bbox) or bbox_for(HttpClient(cfg.user_agent), args.city, args.state, cfg.data_dir / "cache")
        for name, n in list_categories(cfg, bbox):
            print(f"{n:6}  {name}")
        return

    if not (args.city or args.bbox or args.csv_file):
        sys.exit("Provide --city (or --bbox / --csv-file).")
    target = args.target or (150 if args.pilot else 200)
    opt = RunOptions(
        sources=[s.strip() for s in args.source.split(",") if s.strip()], category=args.category,
        city=args.city, state=args.state, target=target, bbox=_bbox(args.bbox),
        osm_filters=args.osm_filter or [], overture_terms=args.overture_term or [],
        google_queries=args.google_query or [], localities=args.locality or [],
        csv_file=args.csv_file or "", csv_map=_kv(args.csv_map), min_confidence=args.min_confidence,
        enrich=not args.no_enrich, check_urls_only=args.check_urls_only, js_fallback=args.js_fallback,
        require_phone=args.require_phone, require_website=args.require_website, resume=args.resume,
        run_name=args.run_name or "", out=args.out or "", postgres=args.postgres,
        accept_google_terms=args.accept_google_terms, pilot=args.pilot)
    rep = run_pipeline(cfg, opt)
    print(json.dumps(rep, indent=2))
    if args.pilot:
        print("\nPILOT", "PASSED" if rep.get("pilot_passed") else "NOT PASSED - review before scaling up")
