from __future__ import annotations

import json
from typing import Any

import pandas as pd

from ml.paths import FEATURE_SPEC_PATH

NUM_FEATURES = ["year", "age", "mileage_km", "engine_cc", "owners_count", "km_per_year", "is_premium"]
CAT_FEATURES = ["make", "model_name", "segment", "condition", "city", "fuel_type", "transmission"]
TARGET = "sold_price"
ANCHOR_YEAR = 2026


def engineer(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["year"] = out["year"].astype(int)
    out["age"] = ANCHOR_YEAR - out["year"]
    out["km_per_year"] = out["mileage_km"].astype(float) / out["age"].clip(lower=1)
    out["is_premium"] = out["segment"].isin(
        ["premium_scooter", "maxiscooter", "supersport", "naked", "sport"]
    ).astype(int)
    return out


def feature_columns() -> tuple[list[str], list[str]]:
    return list(NUM_FEATURES), list(CAT_FEATURES)


def to_model_frame(df: pd.DataFrame) -> pd.DataFrame:
    engineered = engineer(df)
    nums, cats = feature_columns()
    frame = engineered[nums + cats].copy()
    for col in cats:
        frame[col] = frame[col].astype("category")
    return frame


def build_training_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    sold = df.loc[df["sold_price"].notna()].copy()
    x = to_model_frame(sold)
    y = sold[TARGET].astype(float)
    return x, y


def dump_feature_spec(path=FEATURE_SPEC_PATH) -> dict[str, Any]:
    nums, cats = feature_columns()
    spec = {"numeric": nums, "categorical": cats, "target": TARGET, "anchor_year": ANCHOR_YEAR}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec, indent=2), encoding="utf-8")
    return spec
