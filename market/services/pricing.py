from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.utils import timezone

from market.models import ListingPrediction, Motorcycle
from ml.catalog import CATALOG
from ml.score import ModelNotTrainedError, deal_label, deal_score, predict_prices


def listing_to_record(bike: Motorcycle) -> dict:
    segment = bike.segment
    if not segment:
        match = next(
            (row for row in CATALOG if row["make"] == bike.make and row["model_name"] == bike.model_name),
            None,
        )
        segment = match["segment"] if match else "scooter"
    return {
        "listing_id": str(bike.pk),
        "make": bike.make or "Honda",
        "model_name": bike.model_name or "BeAT",
        "segment": segment,
        "year": int(bike.year or 2020),
        "mileage_km": int(bike.mileage_km or 0),
        "engine_cc": int(bike.engine_cc or 150),
        "fuel_type": bike.fuel_type or "petrol",
        "transmission": bike.transmission or "automatic",
        "condition": bike.condition or "good",
        "city": bike.city or "Jakarta",
        "owners_count": int(bike.owners_count or 1),
        "asking_price": float(bike.start_price),
    }


def listings_frame(qs=None) -> pd.DataFrame:
    qs = qs if qs is not None else Motorcycle.objects.all()
    records = [listing_to_record(bike) for bike in qs]
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)


def score_listing(bike: Motorcycle) -> ListingPrediction | None:
    try:
        pred = float(predict_prices(pd.DataFrame([listing_to_record(bike)]))[0])
    except ModelNotTrainedError:
        return None
    asking = float(bike.start_price)
    score = deal_score(asking, pred)
    label = deal_label(score)
    obj, _ = ListingPrediction.objects.update_or_create(
        motorcycle=bike,
        defaults={
            "predicted_price": Decimal(str(round(pred, 0))),
            "deal_score": round(score, 2),
            "deal_label": label,
            "scored_at": timezone.now(),
            "features": listing_to_record(bike),
        },
    )
    return obj


def score_queryset(qs=None) -> int:
    qs = qs if qs is not None else Motorcycle.objects.all()
    count = 0
    for bike in qs:
        if score_listing(bike):
            count += 1
    return count
