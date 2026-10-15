from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from ml.features import to_model_frame
from ml.paths import PRICE_MODEL_PATH


class ModelNotTrainedError(FileNotFoundError):
    pass


@lru_cache(maxsize=1)
def load_bundle(path: str | None = None):
    model_path = Path(path) if path else PRICE_MODEL_PATH
    if not model_path.exists():
        raise ModelNotTrainedError(
            f"No price model at {model_path}. Run `python -m ml train` first."
        )
    return joblib.load(model_path)


def clear_model_cache() -> None:
    load_bundle.cache_clear()


def predict_prices(df: pd.DataFrame, model_path: str | None = None) -> np.ndarray:
    bundle = load_bundle(str(model_path) if model_path else None)
    frame = to_model_frame(df)
    return np.asarray(bundle["model"].predict(frame), dtype=float)


def deal_score(asking_price: float, predicted_price: float) -> float:
    """Percent the bike is under the model's fair value. Positive = cheaper than predicted."""
    if predicted_price <= 0:
        return 0.0
    return float((predicted_price - asking_price) / predicted_price * 100)


def deal_label(score: float) -> str:
    if score >= 12:
        return "great_deal"
    if score >= 5:
        return "good_deal"
    if score <= -12:
        return "overpriced"
    if score <= -5:
        return "rich"
    return "fair"


def score_frame(df: pd.DataFrame, asking_col: str = "asking_price") -> pd.DataFrame:
    out = df.copy()
    preds = predict_prices(out)
    out["predicted_price"] = np.round(preds, 0)
    out["deal_score"] = [
        round(deal_score(float(ask), float(pred)), 2)
        for ask, pred in zip(out[asking_col], out["predicted_price"])
    ]
    out["deal_label"] = [deal_label(s) for s in out["deal_score"]]
    return out
