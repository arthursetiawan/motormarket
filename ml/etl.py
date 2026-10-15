"""Bronze → silver → gold style ETL for the synthetic market extract."""

from __future__ import annotations

import json

from ml.generate import generate_live_listings, write_raw_extract
from ml.paths import DATA_GOLD, DATA_STAGING, ensure_dirs
from ml.quality import report_to_dict, run_quality_checks


def run_etl(n_sold: int = 4000, n_live: int = 120, seed: int = 42) -> dict:
    ensure_dirs()
    sold = write_raw_extract(n=n_sold, seed=seed)
    live = generate_live_listings(n=n_live, seed=seed + 3)
    sold_q = run_quality_checks(sold, require_sold=True)
    live_q = run_quality_checks(live, require_sold=False)
    if not sold_q.passed:
        raise ValueError(sold_q.failures)

    sold.to_csv(DATA_STAGING / "sold_listings_clean.csv", index=False)
    live.to_csv(DATA_STAGING / "live_listings_clean.csv", index=False)
    sold.assign(table="sold").to_csv(DATA_GOLD / "sold_listings.csv", index=False)
    live.assign(table="live").to_csv(DATA_GOLD / "live_listings.csv", index=False)

    summary = {
        "sold_rows": int(len(sold)),
        "live_rows": int(len(live)),
        "sold_quality": report_to_dict(sold_q),
        "live_quality": report_to_dict(live_q),
    }
    (DATA_GOLD / "etl_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
