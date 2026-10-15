"""Listing trust / anomaly signals for marketplace quality.

Rule-based and model-backed checks (not a fraud classifier). Designed to be
transparent to buyers and useful as an ops triage score.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ANCHOR_YEAR = 2026
EXPECTED_KM_PER_YEAR = 7800
HIGH_KM_PER_YEAR = 16000
LOW_KM_PER_YEAR = 1200


@dataclass
class TrustFlag:
    code: str
    severity: str  # info | watch | alert
    message: str


@dataclass
class TrustReport:
    score: int
    label: str  # high_trust | review | caution
    flags: list[TrustFlag] = field(default_factory=list)
    completeness: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _age_years(year: int | None) -> float | None:
    if year is None:
        return None
    return max(float(ANCHOR_YEAR - int(year)), 0.25)


def assess_listing(
    *,
    make: str | None,
    model_name: str | None,
    year: int | None,
    mileage_km: int | None,
    condition: str | None,
    city: str | None,
    owners_count: int | None,
    asking_price: float | None,
    predicted_price: float | None = None,
    deal_score: float | None = None,
    engine_cc: int | None = None,
    has_image: bool = False,
    description: str | None = None,
) -> TrustReport:
    """Return a 0–100 trust score and human-readable flags."""
    flags: list[TrustFlag] = []
    score = 100.0

    required = {
        "make": make,
        "model": model_name,
        "year": year,
        "mileage": mileage_km,
        "city": city,
        "condition": condition,
        "ask": asking_price,
    }
    present = sum(1 for v in required.values() if v not in (None, "", 0))
    completeness = present / len(required)
    if completeness < 1:
        missing = [k for k, v in required.items() if v in (None, "", 0)]
        flags.append(
            TrustFlag(
                "incomplete_fields",
                "watch",
                f"Missing or empty fields: {', '.join(missing)}.",
            )
        )
        score -= 12 * (1 - completeness)

    if not has_image:
        flags.append(TrustFlag("no_photo", "watch", "No listing photo uploaded."))
        score -= 8

    if description is not None and len(description.strip()) < 40:
        flags.append(TrustFlag("thin_description", "info", "Description is very short."))
        score -= 4

    age = _age_years(year)
    if year is not None and (year < 2008 or year > ANCHOR_YEAR):
        flags.append(TrustFlag("year_out_of_range", "alert", f"Year {year} is outside the expected book."))
        score -= 25

    if age is not None and mileage_km is not None and mileage_km >= 0:
        km_per_year = mileage_km / age
        if km_per_year >= HIGH_KM_PER_YEAR:
            flags.append(
                TrustFlag(
                    "high_mileage_rate",
                    "watch",
                    f"About {int(km_per_year):,} km/year — high for a typical Indonesian scooter.",
                )
            )
            score -= 10
        elif age >= 1.5 and km_per_year <= LOW_KM_PER_YEAR:
            flags.append(
                TrustFlag(
                    "low_mileage_rate",
                    "watch",
                    f"About {int(km_per_year):,} km/year — unusually low; verify the odometer.",
                )
            )
            score -= 12

    if owners_count is not None and owners_count >= 4:
        flags.append(TrustFlag("many_owners", "watch", f"{owners_count} recorded owners."))
        score -= 8

    if asking_price is not None and asking_price <= 0:
        flags.append(TrustFlag("invalid_ask", "alert", "Asking price is not positive."))
        score -= 30

    if deal_score is not None:
        if deal_score >= 22:
            flags.append(
                TrustFlag(
                    "extreme_deal",
                    "alert",
                    f"Ask is ~{deal_score:.0f}% under model fair value — verify before bidding.",
                )
            )
            score -= 18
        elif deal_score <= -22:
            flags.append(
                TrustFlag(
                    "extreme_premium",
                    "watch",
                    f"Ask is ~{abs(deal_score):.0f}% over model fair value.",
                )
            )
            score -= 8

    if (
        predicted_price
        and asking_price
        and condition == "poor"
        and asking_price >= predicted_price * 0.95
    ):
        flags.append(
            TrustFlag(
                "condition_price_mismatch",
                "watch",
                "Poor condition priced near model fair value for a typical good bike.",
            )
        )
        score -= 10

    if engine_cc is not None and engine_cc > 0 and asking_price and predicted_price:
        # Soft check already covered by deal_score; keep score floor clean.
        pass

    score_i = int(max(0, min(100, round(score))))
    if score_i >= 80 and not any(f.severity == "alert" for f in flags):
        label = "high_trust"
    elif score_i >= 55:
        label = "review"
    else:
        label = "caution"

    return TrustReport(score=score_i, label=label, flags=flags, completeness=round(completeness, 2))
