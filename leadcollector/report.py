"""Run summary: quality metrics, failures and cost."""
from __future__ import annotations

import json
from pathlib import Path

from .config import Config
from .costs import google_cost_inr
from .models import Lead
from .stats import Stats
from .validate import is_invalid_url_status, was_checked


def _pct(a: int, b: int) -> float:
    return round(100 * a / b, 1) if b else 0.0


def build_report(leads: list[Lead], stats: Stats, cfg: Config, meta: dict, pilot: bool) -> dict:
    total = len(leads)
    with_phone = sum(bool(l.phone) for l in leads)
    with_site = sum(bool(l.website) for l in leads)
    both = sum(bool(l.phone and l.website) for l in leads)
    checked = sum(was_checked(l.website_status) for l in leads)
    invalid = sum(is_invalid_url_status(l.website_status) for l in leads)
    cost = round(google_cost_inr(stats.google_requests, cfg.usd_inr, cfg.tax_rate), 2) if stats.google_requests else 0.0
    rep = {
        "run": meta,
        "total_records": total,
        "records_with_phone": with_phone, "pct_with_phone": _pct(with_phone, total),
        "records_with_website": with_site, "pct_with_website": _pct(with_site, total),
        "complete_records_name_phone_website": both, "pct_complete": _pct(both, total),
        "missing_phone": total - with_phone, "missing_website": total - with_site,
        "websites_checked": checked, "invalid_url_count": invalid,
        "invalid_url_rate_pct": _pct(invalid, checked),
        "raw_records_collected": stats.raw_collected,
        "duplicates_merged": stats.duplicates_merged,
        "duplicate_rate_pct": _pct(stats.duplicates_merged, stats.raw_collected),
        "http_requests": stats.requests, "failed_requests": stats.failed_requests,
        "robots_disallowed_sites": stats.robots_skipped,
        "google_requests": stats.google_requests,
        "estimated_cost_inr": cost,
        "cost_per_record_with_phone_inr": round(cost / with_phone, 2) if with_phone else None,
        "coverage_before_trimming": {
            "candidates_after_dedupe": stats.candidates,
            "pct_with_phone": _pct(stats.candidates_with_phone, stats.candidates),
            "pct_with_website": _pct(stats.candidates_with_website, stats.candidates),
            "pct_with_both": _pct(stats.candidates_with_both, stats.candidates),
        },
        "note": "Phone status is a format check only; numbers are not verified as active or owned.",
    }
    if pilot:
        cov = rep["coverage_before_trimming"] if stats.candidates else {
            "pct_with_phone": rep["pct_with_phone"], "pct_with_website": rep["pct_with_website"],
            "pct_with_both": rep["pct_complete"]}
        rep["pilot_basis"] = "coverage of all candidates BEFORE keeping the best ones" if stats.candidates else "final records"
        checks = {
            "phone": cov["pct_with_phone"] >= cfg.min_phone_pct,
            "website": cov["pct_with_website"] >= cfg.min_website_pct,
            "both": cov["pct_with_both"] >= cfg.min_both_pct,
            "invalid_urls": rep["invalid_url_rate_pct"] <= cfg.max_invalid_url_pct,
        }
        rep["pilot_targets"] = {"min_phone_pct": cfg.min_phone_pct, "min_website_pct": cfg.min_website_pct,
                                "min_both_pct": cfg.min_both_pct, "max_invalid_url_pct": cfg.max_invalid_url_pct}
        rep["pilot_checks"] = checks
        rep["pilot_passed"] = all(checks.values())
    return rep


def write_report(run_dir: Path, rep: dict) -> str:
    (run_dir / "report.json").write_text(json.dumps(rep, indent=2), "utf-8")
    lines = ["# Run report", ""]
    for k, v in rep.items():
        if isinstance(v, dict):
            lines.append(f"- **{k}**: `{json.dumps(v)}`")
        else:
            lines.append(f"- **{k}**: {v}")
    text = "\n".join(lines)
    (run_dir / "report.md").write_text(text, "utf-8")
    return text
