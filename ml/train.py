from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.features import build_training_xy, dump_feature_spec, feature_columns
from ml.generate import write_raw_extract
from ml.paths import (
    DATA_GOLD,
    DATA_STAGING,
    IMPORTANCE_PATH,
    METRICS_PATH,
    MODEL_CARD_PATH,
    PRICE_MODEL_PATH,
    ensure_dirs,
)
from ml.quality import run_quality_checks, report_to_dict


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean(np.abs((y_true - y_pred) / np.clip(y_true, 1, None))) * 100)


def time_split(df: pd.DataFrame, frac: float = 0.8) -> tuple[pd.DataFrame, pd.DataFrame]:
    ordered = df.sort_values("listed_at")
    cut = int(len(ordered) * frac)
    return ordered.iloc[:cut], ordered.iloc[cut:]


def train_price_model(n: int = 4000, seed: int = 42) -> dict:
    ensure_dirs()
    raw = write_raw_extract(n=n, seed=seed)
    quality = run_quality_checks(raw, require_sold=True)
    if not quality.passed:
        raise ValueError(f"quality gates failed: {quality.failures}")

    staging_path = DATA_STAGING / "sold_listings_clean.csv"
    raw.to_csv(staging_path, index=False)

    train_df, test_df = time_split(raw)
    x_train, y_train = build_training_xy(train_df)
    x_test, y_test = build_training_xy(test_df)
    nums, cats = feature_columns()
    cat_idx = [x_train.columns.get_loc(c) for c in cats]

    model = HistGradientBoostingRegressor(
        loss="squared_error",
        max_depth=6,
        learning_rate=0.08,
        max_iter=250,
        l2_regularization=0.1,
        min_samples_leaf=20,
        categorical_features=cat_idx,
        random_state=seed,
    )
    model.fit(x_train, y_train)
    pred = model.predict(x_test)

    mae = float(mean_absolute_error(y_test, pred))
    rmse = float(np.sqrt(mean_squared_error(y_test, pred)))
    r2 = float(r2_score(y_test, pred))
    mape = _mape(y_test.to_numpy(), pred)

    perm = permutation_importance(model, x_test, y_test, n_repeats=8, random_state=seed, scoring="neg_mean_absolute_error")
    importance = sorted(
        [
            {"feature": col, "importance": float(imp)}
            for col, imp in zip(x_train.columns, perm.importances_mean)
        ],
        key=lambda row: row["importance"],
        reverse=True,
    )

    residuals = (y_test.to_numpy() - pred)
    metrics = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "mae_idr": round(mae, 0),
        "rmse_idr": round(rmse, 0),
        "mape_pct": round(mape, 2),
        "r2": round(r2, 4),
        "residual_p50": float(np.percentile(residuals, 50)),
        "residual_p90_abs": float(np.percentile(np.abs(residuals), 90)),
        "quality": report_to_dict(quality),
        "split": "time-based 80/20 by listed_at",
        "algorithm": "HistGradientBoostingRegressor",
    }

    joblib.dump({"model": model, "numeric": nums, "categorical": cats}, PRICE_MODEL_PATH)
    dump_feature_spec()
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    IMPORTANCE_PATH.write_text(json.dumps(importance, indent=2), encoding="utf-8")

    gold = train_df.copy()
    gold["split"] = "train"
    test_marked = test_df.copy()
    test_marked["split"] = "test"
    pd.concat([gold, test_marked], ignore_index=True).to_csv(DATA_GOLD / "sold_features.csv", index=False)

    MODEL_CARD_PATH.write_text(_model_card(metrics, importance), encoding="utf-8")
    return metrics


def _model_card(metrics: dict, importance: list[dict]) -> str:
    top = "\n".join(f"- `{row['feature']}`: {row['importance']:.4f}" for row in importance[:8])
    return f"""# Model card — motorcycle sold-price regressor

## Intent
Estimate a fair **sold price in IDR** for used motorcycles listed on MotorMarket so buyers can see
whether an asking price is a deal, fair, or rich.

## Algorithm
`sklearn.ensemble.HistGradientBoostingRegressor` with native categorical features.

## Training data
Synthetic but structurally realistic Indonesian market history (`ml/generate.py`).
The generator encodes depreciation, mileage, condition, city premia, and owner count —
the model has to recover those effects from tabular features only.

## Split
{metrics["split"]}
- train rows: {metrics["n_train"]}
- test rows: {metrics["n_test"]}

## Holdout metrics
- MAE: Rp {metrics["mae_idr"]:,.0f}
- RMSE: Rp {metrics["rmse_idr"]:,.0f}
- MAPE: {metrics["mape_pct"]}%
- R²: {metrics["r2"]}

## Top permutation importances (test MAE)
{top}

## Limitations
- Not live scraped listings (legal/ToS-safe for a public portfolio).
- City and condition are coarse categories.
- Does not yet include photo quality, accident history, or service records.

## How to retrain
```bash
python -m ml train --n 4000
```
"""
