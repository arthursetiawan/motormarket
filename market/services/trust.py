"""Django adapter for listing trust assessment."""

from __future__ import annotations

from market.models import ListingPrediction, Motorcycle
from ml.trust import TrustFlag, TrustReport, assess_listing


def assess_bike(
    bike: Motorcycle,
    *,
    predicted_price: float | None = None,
    deal_score: float | None = None,
) -> TrustReport:
    """Compute trust from listing fields (optionally with a fresh price prediction)."""
    if predicted_price is None or deal_score is None:
        try:
            prediction = bike.prediction
        except ListingPrediction.DoesNotExist:
            prediction = None
        except Exception:
            prediction = None
        if prediction is not None:
            if predicted_price is None:
                predicted_price = float(prediction.predicted_price)
            if deal_score is None:
                deal_score = float(prediction.deal_score)

    return assess_listing(
        make=bike.make,
        model_name=bike.model_name,
        year=bike.year,
        mileage_km=bike.mileage_km,
        condition=bike.condition,
        city=bike.city,
        owners_count=bike.owners_count,
        asking_price=float(bike.start_price) if bike.start_price is not None else None,
        predicted_price=predicted_price,
        deal_score=deal_score,
        engine_cc=bike.engine_cc,
        has_image=bool(bike.image),
        description=bike.description,
        stnk_status=getattr(bike, "stnk_status", None),
        bpkb_status=getattr(bike, "bpkb_status", None),
        pajak_mati=getattr(bike, "pajak_mati", None),
        plate_number=getattr(bike, "plate_number", None) or None,
        tax_valid_through=getattr(bike, "tax_valid_through", None),
    )


def trust_from_prediction(prediction: ListingPrediction | None) -> TrustReport | None:
    if prediction is None or not prediction.trust_label:
        return None
    flags = []
    for row in prediction.trust_flags or []:
        if isinstance(row, dict) and {"code", "severity", "message"} <= set(row):
            flags.append(TrustFlag(code=row["code"], severity=row["severity"], message=row["message"]))
    return TrustReport(
        score=int(prediction.trust_score or 0),
        label=prediction.trust_label,
        flags=flags,
        completeness=float(prediction.trust_completeness or 0),
    )


def listing_trust(bike: Motorcycle, *, prefer_stored: bool = True) -> TrustReport:
    try:
        prediction = bike.prediction
    except ListingPrediction.DoesNotExist:
        prediction = None
    except Exception:
        prediction = None

    if prefer_stored:
        stored = trust_from_prediction(prediction)
        if stored is not None:
            return stored
    return assess_bike(bike)


TRUST_COPY = {
    "high_trust": "Konsisten dengan buku & estimasi harga — aman dilanjut cek fisik.",
    "review": "Ada beberapa sinyal — cek fisik & surat-surat sebelum tawar.",
    "caution": "Beberapa risiko — wajib verifikasi unit & surat-surat dengan teliti.",
}
