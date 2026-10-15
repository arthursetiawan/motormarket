from __future__ import annotations

from decimal import Decimal

import pandas as pd
from django.utils import timezone

from market.models import ListingPrediction, Motorcycle
from market.services.trust import assess_bike
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


def form_to_record(data: dict, asking_price: float | None = None) -> dict:
    """Build a model row from form-cleaned data or request query params."""
    make = (data.get("make") or "Honda").strip()
    model_name = (data.get("model_name") or "BeAT").strip()
    match = next(
        (row for row in CATALOG if row["make"].lower() == make.lower() and row["model_name"].lower() == model_name.lower()),
        None,
    )
    ask = asking_price
    if ask is None:
        raw = data.get("start_price") or data.get("asking_price")
        ask = float(raw) if raw not in (None, "") else 0.0
    return {
        "listing_id": "draft",
        "make": make,
        "model_name": model_name,
        "segment": (match["segment"] if match else data.get("segment")) or "scooter",
        "year": int(data.get("year") or 2020),
        "mileage_km": int(data.get("mileage_km") or 0),
        "engine_cc": int(data.get("engine_cc") or (match["engine_cc"] if match else 150)),
        "fuel_type": data.get("fuel_type") or (match["fuel_type"] if match else "petrol"),
        "transmission": data.get("transmission") or (match["transmission"] if match else "automatic"),
        "condition": data.get("condition") or "good",
        "city": (data.get("city") or "Jakarta").strip(),
        "owners_count": int(data.get("owners_count") or 1),
        "asking_price": float(ask or 0),
    }


def listings_frame(qs=None) -> pd.DataFrame:
    qs = qs if qs is not None else Motorcycle.objects.all()
    records = [listing_to_record(bike) for bike in qs]
    if not records:
        return pd.DataFrame()
    return pd.DataFrame.from_records(records)


def suggest_fair_value(data: dict, asking_price: float | None = None) -> dict | None:
    """Return fair value (+ deal vs ask when provided) for the create-listing flow."""
    record = form_to_record(data, asking_price=asking_price)
    try:
        pred = float(predict_prices(pd.DataFrame([record]))[0])
    except ModelNotTrainedError:
        return None
    asking = float(record["asking_price"] or 0)
    score = deal_score(asking, pred) if asking > 0 else None
    return {
        "predicted_price": int(round(pred, 0)),
        "asking_price": int(round(asking, 0)) if asking > 0 else None,
        "deal_score": round(score, 2) if score is not None else None,
        "deal_label": deal_label(score) if score is not None else None,
        "currency": "IDR",
    }


def score_listing(bike: Motorcycle) -> ListingPrediction | None:
    try:
        pred = float(predict_prices(pd.DataFrame([listing_to_record(bike)]))[0])
    except ModelNotTrainedError:
        return None
    asking = float(bike.start_price)
    score = deal_score(asking, pred)
    label = deal_label(score)
    trust = assess_bike(
        bike,
        predicted_price=pred,
        deal_score=score,
    )
    obj, _ = ListingPrediction.objects.update_or_create(
        motorcycle=bike,
        defaults={
            "predicted_price": Decimal(str(round(pred, 0))),
            "deal_score": round(score, 2),
            "deal_label": label,
            "scored_at": timezone.now(),
            "features": listing_to_record(bike),
            "trust_score": trust.score,
            "trust_label": trust.label,
            "trust_flags": [flag.__dict__ for flag in trust.flags],
            "trust_completeness": trust.completeness,
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
