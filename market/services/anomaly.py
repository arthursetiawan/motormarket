"""Django adapter: build market peer index and score listing anomalies."""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from market.models import Motorcycle
from ml.anomaly import AnomalyReport, MarketIndex, assess_market_anomaly
from ml.generate import generate_sold_listings
from ml.paths import DATA_GOLD
from ml.trust import TrustFlag, TrustReport


def _load_sold_frame() -> pd.DataFrame:
    gold = DATA_GOLD / "sold_listings.csv"
    if gold.exists():
        try:
            return pd.read_csv(gold)
        except Exception:
            pass
    # Synthetic sold book when gold extract is absent (portfolio / fresh clone).
    return generate_sold_listings(n=1200, seed=42)


@lru_cache(maxsize=4)
def _cached_index(live_signature: str, sold_mtime: float) -> MarketIndex:
    del live_signature, sold_mtime  # cache key only
    from market.services.pricing import listings_frame

    live = listings_frame(Motorcycle.objects.filter(is_sold=False))
    sold = _load_sold_frame()
    return MarketIndex(live=live, sold=sold)


def clear_market_index_cache() -> None:
    _cached_index.cache_clear()


def market_index(*, refresh: bool = False) -> MarketIndex:
    if refresh:
        clear_market_index_cache()
    qs = Motorcycle.objects.filter(is_sold=False)
    agg = qs.order_by("-id").values_list("id", flat=True).first()
    count = qs.count()
    live_sig = f"{count}:{agg or 0}"
    gold = DATA_GOLD / "sold_listings.csv"
    sold_mtime = gold.stat().st_mtime if gold.exists() else 0.0
    return _cached_index(live_sig, sold_mtime)


def listing_anomaly(
    bike: Motorcycle,
    *,
    predicted_price: float | None = None,
    deal_score: float | None = None,
    index: MarketIndex | None = None,
) -> AnomalyReport:
    from market.services.pricing import listing_to_record

    idx = index or market_index()
    record = listing_to_record(bike)
    peer = idx.peer_for(
        make=bike.make,
        model_name=bike.model_name,
        segment=bike.segment or record.get("segment"),
        exclude_listing_id=str(bike.pk),
    )
    if predicted_price is None or deal_score is None:
        try:
            prediction = bike.prediction
            if predicted_price is None:
                predicted_price = float(prediction.predicted_price)
            if deal_score is None:
                deal_score = float(prediction.deal_score)
        except Exception:
            pass
    return assess_market_anomaly(
        make=bike.make,
        model_name=bike.model_name,
        segment=bike.segment or record.get("segment"),
        year=bike.year,
        mileage_km=bike.mileage_km,
        engine_cc=bike.engine_cc,
        asking_price=float(bike.start_price) if bike.start_price is not None else None,
        predicted_price=predicted_price,
        deal_score=deal_score,
        peer=peer,
        listing_id=str(bike.pk),
    )


def anomaly_from_prediction(prediction) -> AnomalyReport | None:
    if prediction is None or not getattr(prediction, "anomaly_label", None):
        return None
    flags = []
    for row in prediction.anomaly_flags or []:
        if isinstance(row, dict) and {"code", "severity", "message"} <= set(row):
            flags.append(TrustFlag(code=row["code"], severity=row["severity"], message=row["message"]))
    return AnomalyReport(
        score=int(prediction.anomaly_score or 0),
        label=prediction.anomaly_label,
        flags=flags,
        confidence=float(getattr(prediction, "anomaly_confidence", 0) or 0),
        peer_n=int(getattr(prediction, "anomaly_peer_n", 0) or 0),
        peer_source=getattr(prediction, "anomaly_peer_source", "") or "none",
        peer_price_p50=None,
    )


ANOMALY_COPY = {
    "ok": "Harga & spek konsisten dengan komparasi pasar NegoMotor.",
    "waspada": "Ada sinyal outlier vs buku pasar — cek fisik & komparasi sebelum tawar.",
    "waspada_tinggi": "Beberapa sinyal pasar kuat (waspada) — verifikasi odo, harga, dan surat dengan teliti.",
}


def fold_anomaly_flags(trust: TrustReport, anomaly: AnomalyReport) -> TrustReport:
    """Append market flags not already present on the trust report."""
    seen = {f.code for f in trust.flags}
    merged = list(trust.flags)
    for flag in anomaly.flags:
        if flag.code not in seen:
            merged.append(flag)
            seen.add(flag.code)
    trust.flags = merged
    return trust
