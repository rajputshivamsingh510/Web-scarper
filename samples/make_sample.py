"""Regenerates samples/sample_output_ILLUSTRATIVE.csv from a synthetic local file (no network).
All business names are fictional test records; the phone is phonenumbers' documented example number."""
import sys, shutil, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

import os
tmp = Path(tempfile.mkdtemp())
os.environ.update(DATA_DIR=str(tmp / "data"), CONTACT_EMAIL="demo@example.com")
import duckdb  # noqa
import conftest  # noqa
from leadcollector.config import load_config
from leadcollector.pipeline import RunOptions, run_pipeline

parquet = conftest.overture_parquet.__wrapped__(tmp) if hasattr(conftest.overture_parquet, "__wrapped__") else None
cfg = load_config(); cfg.overture_path = parquet
rep = run_pipeline(cfg, RunOptions(sources=["overture"], category="jewellers", city="Testville",
                                   bbox=(30.0, 75.0, 31.5, 76.5), target=10, enrich=False, run_name="sample"))
shutil.copy(rep["run"]["csv"], Path(__file__).parent / "sample_output_ILLUSTRATIVE.csv")
print("written; report:", {k: rep[k] for k in ("total_records", "duplicates_merged", "pct_with_phone")})
