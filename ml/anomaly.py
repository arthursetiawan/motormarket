"""Market-dataset anomaly detection for NegoMotor listings.

Uses peer bands from sold/live comps (IQR / percentiles) plus catalog priors.
Practical rules — not a heavy unsupervised stack. Flags are transparent for buyers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from ml.catalog import CATALOG
from ml.trust import ANCHOR_YEAR, TrustFlag


MIN_PEER_N = 5
SPARSE_N = 3


@dataclass
class PeerBand:
    key: str
    n: int
    source: str  # model_live | model_sold | segment_live | segment_sold | none
    price_p25: float | None = None
    price_p50: float | None = None
    price_p75: float | None = None
    km_year_p25: float | None = None
    km_year_p50: float | None = None
    km_year_p75: float | None = None
    year_p10: float | None = None
    year_p90: float | None = None

    @property
    def confidence(self) -> float:
        if self.n <= 0:
            return 0.0
        if self.n < SPARSE_N:
            return 0.25
        if self.n < MIN_PEER_N:
            return 0.55
        return min(1.0, 0.55 + 0.05 * (self.n - MIN_PEER_N))


@dataclass
class AnomalyReport:
    score: int  # 0–100, higher = more normal / less anomalous
    label: str  # ok | waspada | waspada_tinggi
    flags: list[TrustFlag] = field(default_factory=list)
    confidence: float = 0.0
    peer_n: int = 0
    peer_source: str = "none"
    peer_price_p50: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _age_years(year: int | None) -> float | None:
    if year is None:
        return None
    return max(float(ANCHOR_YEAR - int(year)), 0.25)


def _price_col(df: pd.DataFrame) -> str | None:
    if "sold_price" in df.columns and df["sold_price"].notna().any():
        return "sold_price"
    if "asking_price" in df.columns:
        return "asking_price"
    return None


def _km_per_year_series(df: pd.DataFrame) -> pd.Series:
    years = df["year"].astype(float)
    age = (ANCHOR_YEAR - years).clip(lower=0.25)
    return df["mileage_km"].astype(float) / age


def _band_from_frame(df: pd.DataFrame, key: str, source: str) -> PeerBand:
    if df is None or len(df) == 0:
        return PeerBand(key=key, n=0, source="none")
    price_col = _price_col(df)
    prices = df[price_col].dropna().astype(float) if price_col else pd.Series(dtype=float)
    km_year = _km_per_year_series(df.dropna(subset=["year", "mileage_km"]))
    years = df["year"].dropna().astype(float)
    band = PeerBand(key=key, n=len(df), source=source)
    if len(prices):
        band.price_p25 = float(np.percentile(prices, 25))
        band.price_p50 = float(np.percentile(prices, 50))
        band.price_p75 = float(np.percentile(prices, 75))
    if len(km_year):
        band.km_year_p25 = float(np.percentile(km_year, 25))
        band.km_year_p50 = float(np.percentile(km_year, 50))
        band.km_year_p75 = float(np.percentile(km_year, 75))
    if len(years):
        band.year_p10 = float(np.percentile(years, 10))
        band.year_p90 = float(np.percentile(years, 90))
    return band


class MarketIndex:
    """Peer bands keyed by make|model and segment, built from market DataFrames."""

    def __init__(self, live: pd.DataFrame | None = None, sold: pd.DataFrame | None = None):
        self.live = live if live is not None else pd.DataFrame()
        self.sold = sold if sold is not None else pd.DataFrame()
        self._model_live: dict[str, PeerBand] = {}
        self._model_sold: dict[str, PeerBand] = {}
        self._segment_live: dict[str, PeerBand] = {}
        self._segment_sold: dict[str, PeerBand] = {}
        self._build()

    def _build(self) -> None:
        for frame, store, tag in (
            (self.live, self._model_live, "model_live"),
            (self.sold, self._model_sold, "model_sold"),
        ):
            if frame is None or frame.empty or "make" not in frame.columns:
                continue
            grouped = frame.groupby(["make", "model_name"], dropna=False)
            for (make, model), chunk in grouped:
                key = f"{make}|{model}".lower()
                store[key] = _band_from_frame(chunk, key, tag)

        for frame, store, tag in (
            (self.live, self._segment_live, "segment_live"),
            (self.sold, self._segment_sold, "segment_sold"),
        ):
            if frame is None or frame.empty or "segment" not in frame.columns:
                continue
            for segment, chunk in frame.groupby("segment", dropna=False):
                key = str(segment or "scooter").lower()
                store[key] = _band_from_frame(chunk, key, tag)

    def peer_for(
        self,
        *,
        make: str | None,
        model_name: str | None,
        segment: str | None,
        exclude_listing_id: str | None = None,
    ) -> PeerBand:
        """Prefer same-model live peers, then sold, then segment fallbacks."""
        key = f"{make or ''}|{model_name or ''}".lower()
        live = self.live
        if exclude_listing_id and live is not None and not live.empty and "listing_id" in live.columns:
            live = live[live["listing_id"].astype(str) != str(exclude_listing_id)]
            # rebuild just this model band from filtered live
            if not live.empty and make and model_name:
                chunk = live[
                    (live["make"].astype(str).str.lower() == str(make).lower())
                    & (live["model_name"].astype(str).str.lower() == str(model_name).lower())
                ]
                band = _band_from_frame(chunk, key, "model_live")
                if band.n >= SPARSE_N:
                    return band

        for store in (self._model_live, self._model_sold):
            band = store.get(key)
            if band and band.n >= SPARSE_N:
                return band

        seg = (segment or "scooter").lower()
        for store in (self._segment_live, self._segment_sold):
            band = store.get(seg)
            if band and band.n >= MIN_PEER_N:
                return band

        # Return best available even if sparse
        for store in (self._model_live, self._model_sold, self._segment_live, self._segment_sold):
            band = store.get(key) or store.get(seg)
            if band and band.n > 0:
                return band
        return PeerBand(key=key or seg, n=0, source="none")


def _catalog_row(make: str | None, model_name: str | None) -> dict | None:
    if not make or not model_name:
        return None
    return next(
        (
            row
            for row in CATALOG
            if row["make"].lower() == make.lower() and row["model_name"].lower() == model_name.lower()
        ),
        None,
    )


def assess_market_anomaly(
    *,
    make: str | None,
    model_name: str | None,
    segment: str | None = None,
    year: int | None,
    mileage_km: int | None,
    engine_cc: int | None = None,
    asking_price: float | None,
    predicted_price: float | None = None,
    deal_score: float | None = None,
    peer: PeerBand | None = None,
    listing_id: str | None = None,
) -> AnomalyReport:
    """Flag outliers vs peer bands, fair value, and catalog priors."""
    flags: list[TrustFlag] = []
    score = 100.0
    catalog = _catalog_row(make, model_name)
    seg = segment or (catalog["segment"] if catalog else "scooter")
    peer = peer or PeerBand(key=f"{make}|{model_name}", n=0, source="none")

    if peer.n < SPARSE_N:
        flags.append(
            TrustFlag(
                "sparse_comps",
                "watch",
                f"Komparasi tipis ({peer.n} unit) untuk {make or '?'} {model_name or '?'} — kepercayaan rendah.",
            )
        )
        score -= 12
    elif peer.n < MIN_PEER_N:
        flags.append(
            TrustFlag(
                "thin_comps",
                "info",
                f"Hanya {peer.n} komparasi ({peer.source.replace('_', ' ')}) — baca harga dengan hati-hati.",
            )
        )
        score -= 5

    # Price vs peer IQR fence
    if (
        asking_price
        and peer.price_p25 is not None
        and peer.price_p75 is not None
        and peer.n >= SPARSE_N
    ):
        iqr = max(peer.price_p75 - peer.price_p25, 1.0)
        low = peer.price_p25 - 1.5 * iqr
        high = peer.price_p75 + 1.5 * iqr
        if asking_price < low:
            flags.append(
                TrustFlag(
                    "price_below_peer_band",
                    "alert",
                    f"Ask jauh di bawah pita peer (p25 {peer.price_p25:,.0f}) — waspada harga tidak wajar.",
                )
            )
            score -= 22
        elif asking_price > high:
            flags.append(
                TrustFlag(
                    "price_above_peer_band",
                    "watch",
                    f"Ask di atas pita peer (p75 {peer.price_p75:,.0f}).",
                )
            )
            score -= 12

    # Fair-value outlier (market model)
    if deal_score is not None:
        if deal_score >= 25:
            flags.append(
                TrustFlag(
                    "fair_value_deep_discount",
                    "alert",
                    f"~{deal_score:.0f}% di bawah fair value model — cek odometer & surat (waspada).",
                )
            )
            score -= 18
        elif deal_score <= -25:
            flags.append(
                TrustFlag(
                    "fair_value_steep_premium",
                    "watch",
                    f"~{abs(deal_score):.0f}% di atas fair value model vs buku pasar.",
                )
            )
            score -= 10

    # Ask vs peer median gap when we have a solid band
    if asking_price and peer.price_p50 and peer.n >= MIN_PEER_N:
        gap = (asking_price - peer.price_p50) / peer.price_p50 * 100
        if gap <= -30:
            flags.append(
                TrustFlag(
                    "ask_vs_peer_median",
                    "alert",
                    f"Ask ~{abs(gap):.0f}% di bawah median peer (Rp {peer.price_p50:,.0f}).",
                )
            )
            score -= 14
        elif gap >= 35:
            flags.append(
                TrustFlag(
                    "ask_vs_peer_median_high",
                    "watch",
                    f"Ask ~{gap:.0f}% di atas median peer (Rp {peer.price_p50:,.0f}).",
                )
            )
            score -= 8

    # km/year vs peer band
    age = _age_years(year)
    if age is not None and mileage_km is not None and peer.km_year_p25 is not None and peer.n >= SPARSE_N:
        km_year = mileage_km / age
        iqr = max((peer.km_year_p75 or km_year) - peer.km_year_p25, 1.0)
        low = peer.km_year_p25 - 1.5 * iqr
        high = (peer.km_year_p75 or peer.km_year_p25) + 1.5 * iqr
        if km_year < max(low, 500) and age >= 1.5:
            flags.append(
                TrustFlag(
                    "km_rate_below_peers",
                    "alert",
                    f"~{int(km_year):,} km/tahun di bawah peer (median ~{int(peer.km_year_p50 or 0):,}) — waspada odo.",
                )
            )
            score -= 16
        elif km_year > high:
            flags.append(
                TrustFlag(
                    "km_rate_above_peers",
                    "watch",
                    f"~{int(km_year):,} km/tahun di atas peer band — unit kerja berat?",
                )
            )
            score -= 8

    # Catalog / segment oddities
    if catalog is None and make and model_name:
        flags.append(
            TrustFlag(
                "unknown_catalog_model",
                "watch",
                f"{make} {model_name} tidak ada di katalog NegoMotor — komparasi terbatas.",
            )
        )
        score -= 8
    elif catalog is not None:
        if engine_cc and abs(int(engine_cc) - int(catalog["engine_cc"])) >= 40:
            flags.append(
                TrustFlag(
                    "engine_cc_mismatch",
                    "watch",
                    f"CC listing {engine_cc} vs katalog {catalog['engine_cc']} — cek spesifikasi.",
                )
            )
            score -= 10
        if segment and catalog["segment"] and segment != catalog["segment"]:
            flags.append(
                TrustFlag(
                    "segment_mismatch",
                    "info",
                    f"Segment '{segment}' beda dari katalog ('{catalog['segment']}').",
                )
            )
            score -= 4
        if asking_price and asking_price > catalog["msrp_idr"] * 1.08:
            flags.append(
                TrustFlag(
                    "ask_above_msrp",
                    "alert",
                    f"Ask di atas MSRP katalog (~Rp {catalog['msrp_idr']:,}) untuk motor bekas — waspada.",
                )
            )
            score -= 20

    if year is not None and peer.year_p10 is not None and peer.year_p90 is not None and peer.n >= MIN_PEER_N:
        if year < peer.year_p10 - 2 or year > peer.year_p90 + 1:
            flags.append(
                TrustFlag(
                    "year_outside_peer_range",
                    "watch",
                    f"Tahun {year} di luar kisaran peer tipikal ({peer.year_p10:.0f}–{peer.year_p90:.0f}).",
                )
            )
            score -= 8

    score_i = int(max(0, min(100, round(score))))
    has_alert = any(f.severity == "alert" for f in flags)
    has_watch = any(f.severity == "watch" for f in flags)
    if has_alert or score_i < 55:
        label = "waspada_tinggi"
    elif has_watch or score_i < 80:
        label = "waspada"
    else:
        label = "ok"

    return AnomalyReport(
        score=score_i,
        label=label,
        flags=flags,
        confidence=round(peer.confidence, 2),
        peer_n=peer.n,
        peer_source=peer.source,
        peer_price_p50=peer.price_p50,
    )


def merge_anomaly_into_trust_score(trust_score: int, anomaly: AnomalyReport) -> tuple[int, str]:
    """Pull market alerts into the trust score/label without double-counting mild infos."""
    penalty = 0
    for flag in anomaly.flags:
        if flag.severity == "alert":
            penalty += 8
        elif flag.severity == "watch" and flag.code in {
            "sparse_comps",
            "price_above_peer_band",
            "km_rate_above_peers",
            "engine_cc_mismatch",
            "unknown_catalog_model",
        }:
            penalty += 4
    score = int(max(0, min(100, trust_score - penalty)))
    if score >= 80 and anomaly.label == "ok":
        label = "high_trust"
    elif score >= 55 and anomaly.label != "waspada_tinggi":
        label = "review"
    else:
        label = "caution"
    return score, label
