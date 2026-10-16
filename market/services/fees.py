"""Platform fee (buyer success fee) helpers — configurable via Django settings."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings


def fee_rate() -> Decimal:
    return Decimal(str(getattr(settings, "PLATFORM_FEE_RATE", "0.03")))


def fee_min_idr() -> Decimal:
    return Decimal(str(getattr(settings, "PLATFORM_FEE_MIN_IDR", "150000")))


def fee_max_idr() -> Decimal:
    return Decimal(str(getattr(settings, "PLATFORM_FEE_MAX_IDR", "2500000")))


def compute_platform_fee(basis_amount) -> Decimal:
    """3% of ask/winning bid, clamped to min/max IDR."""
    basis = Decimal(str(basis_amount or 0))
    if basis <= 0:
        return fee_min_idr()
    raw = (basis * fee_rate()).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(fee_min_idr(), min(fee_max_idr(), raw))


def fee_basis_for_listing(motorcycle) -> Decimal:
    """Prefer highest bid, else starting ask."""
    highest = motorcycle.bids.order_by("-amount").first()
    if highest:
        return Decimal(str(highest.amount))
    return Decimal(str(motorcycle.start_price))


def fee_summary(motorcycle) -> dict:
    basis = fee_basis_for_listing(motorcycle)
    fee = compute_platform_fee(basis)
    return {
        "basis": basis,
        "fee": fee,
        "rate_pct": float(fee_rate() * 100),
        "min_idr": fee_min_idr(),
        "max_idr": fee_max_idr(),
    }
