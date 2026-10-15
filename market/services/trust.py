"""Django adapter for listing trust assessment."""

from __future__ import annotations

from market.models import ListingPrediction, Motorcycle
from ml.trust import TrustReport, assess_listing


def listing_trust(bike: Motorcycle) -> TrustReport:
    try:
        prediction = bike.prediction
    except ListingPrediction.DoesNotExist:
        prediction = None
    except Exception:
        prediction = None

    return assess_listing(
        make=bike.make,
        model_name=bike.model_name,
        year=bike.year,
        mileage_km=bike.mileage_km,
        condition=bike.condition,
        city=bike.city,
        owners_count=bike.owners_count,
        asking_price=float(bike.start_price) if bike.start_price is not None else None,
        predicted_price=float(prediction.predicted_price) if prediction else None,
        deal_score=float(prediction.deal_score) if prediction else None,
        engine_cc=bike.engine_cc,
        has_image=bool(bike.image),
        description=bike.description,
    )


TRUST_COPY = {
    "high_trust": "Looks consistent with the book and the price model.",
    "review": "A few signals to check before you bid or buy.",
    "caution": "Several risk signals — verify the bike and papers carefully.",
}
