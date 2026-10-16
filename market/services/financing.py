"""NegoMotor financing / cicilan estimator — pure calculator, no lender API.

Typical Indonesian used-motorcycle (motor bekas) multipurpose financing uses a
*flat* annual rate quoted against principal, or an *effective* (annuity) rate.
Defaults are env-tunable via Django settings; nothing here is an approval.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Optional

from django.conf import settings

IDR = Decimal("1")
PCT = Decimal("0.0001")


def _d(value, default: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(IDR, rounding=ROUND_HALF_UP)


def default_flat_rate() -> Decimal:
    return _d(getattr(settings, "FINANCING_DEFAULT_FLAT_RATE", "0.14"))


def default_effective_rate() -> Decimal:
    return _d(getattr(settings, "FINANCING_DEFAULT_EFFECTIVE_RATE", "0.24"))


def default_dp_pct() -> Decimal:
    return _d(getattr(settings, "FINANCING_DEFAULT_DP_PCT", "0.20"))


def default_tenor_months() -> int:
    return int(getattr(settings, "FINANCING_DEFAULT_TENOR_MONTHS", 24))


def admin_fee_idr() -> Decimal:
    return _money(_d(getattr(settings, "FINANCING_ADMIN_FEE_IDR", "250000")))


# Sensible UX bounds for used bikes ~Rp8–25jt (knobs still clamp outside slightly).
DP_PCT_MIN = Decimal("0.10")
DP_PCT_MAX = Decimal("0.50")
TENOR_CHOICES = (12, 18, 24, 30, 36)
FLAT_RATE_SAMPLE = (Decimal("0.10"), Decimal("0.14"), Decimal("0.18"))
EFFECTIVE_RATE_SAMPLE = (Decimal("0.18"), Decimal("0.24"), Decimal("0.30"))


@dataclass(frozen=True)
class FinancingEstimate:
    otr: Decimal
    dp_pct: Decimal
    dp_amount: Decimal
    tenor_months: int
    rate_mode: str  # "flat" | "effective"
    annual_rate: Decimal
    principal: Decimal
    interest_total: Decimal
    admin_fee: Decimal
    angsuran: Decimal
    total_bayar: Decimal
    plafon: Decimal
    eligible_ltv: Decimal
    eligible_ok: bool
    assumptions: dict

    def as_dict(self) -> dict:
        data = asdict(self)
        # Keep Decimal values; templates format via currency_idr / floatformat.
        return data


def eligible_ltv(
    otr: Decimal,
    condition: Optional[str] = None,
    condition_grade: Optional[str] = None,
) -> Decimal:
    """Max financed share of OTR based on price band + optional grade/condition.

    Does not hard-depend on auction fields — grade/condition are optional.
    """
    otr = _d(otr)
    # Base LTV by price band (used bikes ~8–25jt sweet spot).
    if otr <= 0:
        base = Decimal("0.70")
    elif otr < Decimal("8000000"):
        base = Decimal("0.70")  # very cheap units: tighter
    elif otr <= Decimal("25000000"):
        base = Decimal("0.85")
    elif otr <= Decimal("40000000"):
        base = Decimal("0.80")
    else:
        base = Decimal("0.75")

    grade = (condition_grade or "").strip().upper()
    if grade == "A":
        base += Decimal("0.05")
    elif grade == "C":
        base -= Decimal("0.10")

    cond = (condition or "").strip().lower()
    if cond == "excellent":
        base += Decimal("0.02")
    elif cond == "poor":
        base -= Decimal("0.08")
    elif cond == "fair":
        base -= Decimal("0.03")

    return max(Decimal("0.50"), min(Decimal("0.90"), base))


def _flat_interest(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    years = Decimal(months) / Decimal(12)
    return _money(principal * annual_rate * years)


def _annuity_payment(principal: Decimal, annual_rate: Decimal, months: int) -> Decimal:
    """Monthly payment for effective (compound) annual rate."""
    if months <= 0:
        return _money(principal)
    if annual_rate <= 0:
        return _money(principal / Decimal(months))
    r = annual_rate / Decimal(12)
    factor = (Decimal(1) + r) ** months
    payment = principal * r * factor / (factor - Decimal(1))
    return _money(payment)


def simulate(
    otr,
    *,
    dp_pct=None,
    tenor_months=None,
    rate_mode: str = "flat",
    annual_rate=None,
    condition: Optional[str] = None,
    condition_grade: Optional[str] = None,
    admin_fee=None,
) -> FinancingEstimate:
    """Estimate DP, angsuran, total bayar, and plafon for a given OTR/ask."""
    otr_m = _money(_d(otr))
    if otr_m < 0:
        otr_m = Decimal("0")

    dp = _d(dp_pct, str(default_dp_pct()))
    if dp > 1:
        dp = dp / Decimal(100)
    dp = max(DP_PCT_MIN, min(DP_PCT_MAX, dp))

    months = int(tenor_months if tenor_months is not None else default_tenor_months())
    months = max(6, min(48, months))

    mode = (rate_mode or "flat").strip().lower()
    if mode not in ("flat", "effective"):
        mode = "flat"

    if annual_rate is None:
        rate = default_flat_rate() if mode == "flat" else default_effective_rate()
    else:
        rate = _d(annual_rate)
        if rate > 1:
            rate = rate / Decimal(100)
    rate = max(Decimal("0"), min(Decimal("0.60"), rate))

    fee = _money(_d(admin_fee, str(admin_fee_idr()))) if admin_fee is not None else admin_fee_idr()
    ltv = eligible_ltv(otr_m, condition=condition, condition_grade=condition_grade)
    plafon = _money(otr_m * ltv)

    dp_amount = _money(otr_m * dp)
    principal = _money(otr_m - dp_amount)
    if principal < 0:
        principal = Decimal("0")

    # Cap financed principal at plafon (eligible range).
    eligible_ok = principal <= plafon + Decimal("1")  # 1 rupiah slack
    financed = min(principal, plafon)

    if mode == "flat":
        interest = _flat_interest(financed, rate, months)
        angsuran = _money((financed + interest) / Decimal(months)) if months else financed
        interest_total = interest
    else:
        angsuran = _annuity_payment(financed, rate, months)
        interest_total = _money(angsuran * Decimal(months) - financed)

    total_bayar = _money(dp_amount + (angsuran * Decimal(months)) + fee)

    assumptions = {
        "otr_label": "OTR / harga ask listing",
        "dp_range": "10–50% (default 20%)",
        "tenor_range": "12–36 bulan tipikal motor bekas",
        "flat_note": "Bunga flat tahunan × pokok × tahun, dibagi tenor",
        "effective_note": "Anuitas efektif (compound bulanan)",
        "sample_flat": [str(r) for r in FLAT_RATE_SAMPLE],
        "sample_effective": [str(r) for r in EFFECTIVE_RATE_SAMPLE],
        "plafon_note": "Plafon ≈ OTR × LTV (grade/kondisi/price band)",
        "not_approval": True,
    }

    return FinancingEstimate(
        otr=otr_m,
        dp_pct=dp,
        dp_amount=dp_amount,
        tenor_months=months,
        rate_mode=mode,
        annual_rate=rate,
        principal=financed,
        interest_total=interest_total,
        admin_fee=fee,
        angsuran=angsuran,
        total_bayar=total_bayar,
        plafon=plafon,
        eligible_ltv=ltv,
        eligible_ok=eligible_ok,
        assumptions=assumptions,
    )


def parse_query(params: Any) -> dict:
    """Normalize GET/POST knobs for the financing view."""
    get = params.get if hasattr(params, "get") else lambda k, d=None: d

    # Allow Indonesian-style "15000000" or "15.000.000": strip thousand dots.
    def _idr(key, default=None):
        raw = get(key)
        if raw is None or raw == "":
            return default
        s = str(raw).strip().replace("Rp", "").replace("rp", "").replace(" ", "")
        if "." in s and "," not in s:
            parts = s.split(".")
            if all(p.isdigit() for p in parts) and (
                len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3)
            ):
                s = "".join(parts)
        s = s.replace(",", "")
        try:
            return Decimal(s)
        except Exception:
            return default

    mode = (get("rate_mode") or "flat").strip().lower()
    if mode not in ("flat", "effective"):
        mode = "flat"

    tenor_raw = get("tenor") or get("tenor_months")
    try:
        tenor = int(tenor_raw) if tenor_raw not in (None, "") else None
    except (TypeError, ValueError):
        tenor = None

    dp_raw = get("dp_pct")
    dp = None
    if dp_raw not in (None, ""):
        try:
            dp = Decimal(str(dp_raw))
            if dp > 1:
                dp = dp / Decimal(100)
        except Exception:
            dp = None

    rate_raw = get("rate") or get("annual_rate")
    rate = None
    if rate_raw not in (None, ""):
        try:
            rate = Decimal(str(rate_raw))
            if rate > 1:
                rate = rate / Decimal(100)
        except Exception:
            rate = None

    listing_id = get("listing") or get("id")
    try:
        listing_id = int(listing_id) if listing_id not in (None, "") else None
    except (TypeError, ValueError):
        listing_id = None

    return {
        "listing_id": listing_id,
        "otr": _idr("otr") or _idr("price") or _idr("ask"),
        "make": (get("make") or "").strip() or None,
        "model_name": (get("model") or get("model_name") or "").strip() or None,
        "year": get("year") or None,
        "dp_pct": dp,
        "tenor_months": tenor,
        "rate_mode": mode,
        "annual_rate": rate,
        "condition": (get("condition") or "").strip() or None,
        "condition_grade": (get("grade") or get("condition_grade") or "").strip() or None,
    }
