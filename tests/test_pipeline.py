import csv

from leadcollector.pipeline import RunOptions, run_pipeline
from conftest import EXAMPLE_PHONE


def test_end_to_end_overture_offline(cfg, overture_parquet):
    cfg.overture_path = overture_parquet
    opt = RunOptions(sources=["overture"], category="jewellers", city="Testville",
                     bbox=(30.0, 75.0, 31.5, 76.5), target=10, enrich=False, pilot=True,
                     run_name="t1")
    rep = run_pipeline(cfg, opt)
    rows = list(csv.DictReader(open(rep["run"]["csv"], encoding="utf-8-sig")))
    assert rep["raw_records_collected"] == 3 and rep["duplicates_merged"] == 1
    assert len(rows) == 2
    merged = next(r for r in rows if r["phone"] == EXAMPLE_PHONE)
    assert merged["website"] == "https://www.example.com"
    assert "ownership_and_active_status_not_verified" in merged["verification_status"]
    assert "pilot_passed" in rep and rep["estimated_cost_inr"] == 0


def test_resume_skips_collection(cfg, overture_parquet):
    cfg.overture_path = overture_parquet
    opt = RunOptions(sources=["overture"], category="jewellers", city="Testville",
                     bbox=(30.0, 75.0, 31.5, 76.5), target=10, enrich=False, run_name="t2")
    run_pipeline(cfg, opt)
    cfg.overture_path = "/nonexistent/*.parquet"   # would fail if collection ran again
    opt.resume = True
    assert run_pipeline(cfg, opt)["total_records"] == 2


def test_enrichment_stage_with_local_site(cfg, local_site, tmp_path):
    f = tmp_path / "in.csv"
    f.write_text(f"name,website\nTest Shop,{local_site}\nNo Site,\n", "utf-8")
    opt = RunOptions(sources=["csv"], category="wholesalers", city="X", csv_file=str(f), target=5, run_name="t3")
    rep = run_pipeline(cfg, opt)
    assert rep["records_with_phone"] == 1 and rep["websites_checked"] == 1 and rep["invalid_url_count"] == 0
