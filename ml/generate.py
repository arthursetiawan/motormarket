"""Generate a synthetic sold-listing history with a learnable pricing function."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from ml.catalog import CATALOG, CITIES, CITY_WEIGHTS, CONDITION_WEIGHTS, CONDITIONS
from ml.paths import DATA_RAW, ensure_dirs

ANCHOR_YEAR = 2026


def _realized_price(
    rng: np.random.Generator,
    msrp: float,
    age: int,
    mileage_km: int,
    condition_mult: float,
    city_mult: float,
    owners_count: int,
    engine_cc: int,
) -> float:
    """Ground-truth pricing function the model should recover."""
    annual_dep = 0.11 if engine_cc < 200 else 0.09
    depreciated = msrp * ((1 - annual_dep) ** age)
    mileage_penalty = mileage_km * (1200 if engine_cc < 200 else 1800)
    owner_penalty = (owners_count - 1) * 450000
    seasonal = 1.0 + 0.03 * np.sin(age)  # small cyclic residual
    noise = rng.normal(0, 0.045)  # 4.5% idiosyncratic noise
    price = (depreciated - mileage_penalty - owner_penalty) * condition_mult * city_mult * seasonal
    price *= 1 + noise
    return float(max(price, msrp * 0.18))


def generate_sold_listings(n: int = 4000, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows: list[dict] = []
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)

    for i in range(n):
        spec = CATALOG[int(rng.integers(0, len(CATALOG)))]
        city_idx = int(rng.choice(len(CITIES), p=CITY_WEIGHTS))
        cond_idx = int(rng.choice(len(CONDITIONS), p=CONDITION_WEIGHTS))
        city, city_mult = CITIES[city_idx]
        condition, condition_mult = CONDITIONS[cond_idx]

        max_age = min(12, ANCHOR_YEAR - 2012)
        age = int(rng.integers(0, max_age + 1))
        year = ANCHOR_YEAR - age
        owners_count = int(rng.choice([1, 2, 3, 4], p=[0.55, 0.28, 0.13, 0.04]))
        km_per_year = float(rng.normal(7800, 2200))
        mileage_km = int(max(400, km_per_year * max(age, 0.4) + rng.normal(0, 800)))

        sold_price = _realized_price(
            rng,
            spec["msrp_idr"],
            age,
            mileage_km,
            condition_mult,
            city_mult,
            owners_count,
            spec["engine_cc"],
        )
        # Asking is sold price plus a negotiated spread (sellers pad, then close).
        ask_spread = float(rng.uniform(0.02, 0.14))
        asking_price = sold_price * (1 + ask_spread)
        listed_at = start + timedelta(days=int(rng.integers(0, 900)), hours=int(rng.integers(0, 24)))

        rows.append(
            {
                "listing_id": f"hist-{i:05d}",
                "make": spec["make"],
                "model_name": spec["model_name"],
                "segment": spec["segment"],
                "year": year,
                "age": age,
                "mileage_km": mileage_km,
                "engine_cc": spec["engine_cc"],
                "fuel_type": spec["fuel_type"],
                "transmission": spec["transmission"],
                "condition": condition,
                "city": city,
                "owners_count": owners_count,
                "asking_price": round(asking_price, 0),
                "sold_price": round(sold_price, 0),
                "is_sold": True,
                "listed_at": listed_at.isoformat(),
                "source": "historical_sold",
            }
        )
    return pd.DataFrame(rows)


def generate_live_listings(n: int = 120, seed: int = 7) -> pd.DataFrame:
    """Unsold live inventory, including intentional under/over pricing."""
    rng = np.random.default_rng(seed)
    hist = generate_sold_listings(n=n, seed=seed + 99)
    hist = hist.copy()
    hist["listing_id"] = [f"live-{i:05d}" for i in range(n)]
    hist["is_sold"] = False
    hist["sold_price"] = np.nan
    hist["source"] = "live_inventory"
    # Re-ask around the latent fair price with some mispriced deals.
    fair = hist["asking_price"] / 1.07
    misprice = rng.choice([0.82, 0.90, 1.0, 1.12, 1.28], size=n, p=[0.08, 0.18, 0.48, 0.18, 0.08])
    hist["asking_price"] = (fair * misprice).round(0)
    hist["listed_at"] = [
        (datetime(2026, 8, 1, tzinfo=timezone.utc) + timedelta(days=int(d))).isoformat()
        for d in rng.integers(0, 70, size=n)
    ]
    return hist


def write_raw_extract(n: int = 4000, seed: int = 42) -> pd.DataFrame:
    ensure_dirs()
    df = generate_sold_listings(n=n, seed=seed)
    path = DATA_RAW / "sold_listings.csv"
    df.to_csv(path, index=False)
    return df
