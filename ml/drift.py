"""Population Stability Index between training gold and live inventory."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

from ml.paths import DRIFT_PATH, ensure_dirs

WATCH_NUMERIC = ["year", "mileage_km", "engine_cc", "asking_price"]


def psi(expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
    expected = np.asarray(expected, dtype=float)
    actual = np.asarray(actual, dtype=float)
    quantiles = np.linspace(0, 100, bins + 1)
    cuts = np.unique(np.percentile(expected, quantiles))
    if len(cuts) < 3:
        return 0.0
    e_counts, _ = np.histogram(expected, bins=cuts)
    a_counts, _ = np.histogram(actual, bins=cuts)
    e_pct = np.clip(e_counts / max(e_counts.sum(), 1), 1e-4, 1)
    a_pct = np.clip(a_counts / max(a_counts.sum(), 1), 1e-4, 1)
    return float(np.sum((a_pct - e_pct) * np.log(a_pct / e_pct)))


def compare_distributions(train_df: pd.DataFrame, live_df: pd.DataFrame) -> dict:
    ensure_dirs()
    report = {"psi": {}, "flagged": []}
    for col in WATCH_NUMERIC:
        if col not in train_df.columns or col not in live_df.columns:
            continue
        value = psi(train_df[col].dropna().to_numpy(), live_df[col].dropna().to_numpy())
        report["psi"][col] = round(value, 4)
        if value >= 0.2:
            report["flagged"].append(col)
    report["status"] = "shift" if report["flagged"] else "stable"
    DRIFT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report
